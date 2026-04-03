"""
Analisa uma conversa concluida e extrai aprendizados para o KB do cliente.
Disparado automaticamente apos cada conversa finalizada.

Supports two payload formats:
1. Legacy (Zenya/manual): conversation = list of {role, content} messages
2. Auto-trigger (BRAIN-1): conversation = {task_type, payload, result, response_text, timestamp}

Pipeline:
1. Recebe conversa completa (historico de mensagens)
2. Claude Haiku analisa se ha informacoes novas relevantes
3. Se sim, insere no KB do cliente via tabela knowledge_base
4. Retorna o que foi aprendido (ou "nada novo" se nao houver)

R-T4 Isolation:
- owner_type=mauro -> Friday conversations -> Mauro Brain
- owner_type=client -> Zenya conversations -> Client Brain
"""
from __future__ import annotations

import json

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.llm import call_claude

EXTRACT_SYSTEM = (
    "Voce eh um extrator de conhecimento para o KB de um negocio.\n"
    "Analise a conversa e extraia APENAS informacoes novas e relevantes sobre o negocio do cliente.\n"
    "\n"
    "Exemplos do que capturar:\n"
    "- Produto ou servico mencionado que nao eh obvio\n"
    "- Preferencia revelada por cliente frequente\n"
    "- Horario ou condicao especial mencionada\n"
    "- Pergunta frequente que revela lacuna no KB\n"
    "- Reclamacao ou elogio sobre algo especifico\n"
    "- Decisao estrategica ou de negocio tomada\n"
    "- Insight sobre processo, ferramenta ou operacao\n"
    "- Informacao sobre cliente, prospect ou parceiro\n"
    "\n"
    "Responda com JSON:\n"
    '{"insights": [{"type": "produto|preferencia|horario|faq|feedback|decisao|processo|cliente", '
    '"content": "descricao concisa", "relevance": "alta|media|baixa"}], '
    '"summary": "resumo em 1 linha do que foi aprendido"}\n'
    "\n"
    'Se nao ha nada novo, responda: {"insights": [], "summary": "nada novo"}'
)


def _ensure_knowledge_base_table() -> None:
    """Garante que a tabela knowledge_base existe no Supabase."""
    try:
        supabase.table("knowledge_base").select("id").limit(1).execute()
    except Exception:
        try:
            supabase.rpc("execute_ddl", {"sql": """
                CREATE TABLE IF NOT EXISTS knowledge_base (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    client_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT DEFAULT 'manual',
                    conversation_id TEXT,
                    relevance TEXT DEFAULT 'media',
                    owner_type TEXT DEFAULT 'client',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """}).execute()
            print("[learn] knowledge_base table created via RPC")
        except Exception as e:
            print(f"[learn] could not create knowledge_base table: {e}")


def _format_auto_trigger_conversation(conversation: dict) -> str:
    """Format auto-trigger payload (BRAIN-1) into readable text for Claude."""
    task_type = conversation.get("task_type", "unknown")
    payload = conversation.get("payload", {})
    result = conversation.get("result", {})
    response_text = conversation.get("response_text", "")

    parts = [f"Tipo de tarefa: {task_type}"]

    # Extract user message
    user_msg = (
        payload.get("original_text", "")
        or payload.get("message", "")
        or payload.get("prompt", "")
    )
    if user_msg:
        parts.append(f"Mauro disse: {user_msg}")

    # Extract extra payload context
    for key in ("business_name", "client_name", "site_url", "extra_info"):
        if payload.get(key):
            parts.append(f"{key}: {payload[key]}")

    # Extract result/response
    if isinstance(result, dict):
        result_msg = result.get("message", "") or result.get("response", "")
        if result_msg:
            parts.append(f"Resultado: {result_msg}")
    elif isinstance(result, str) and result:
        parts.append(f"Resultado: {result}")

    if response_text and response_text not in str(result):
        parts.append(f"Resposta Friday: {response_text[:500]}")

    return "\n".join(parts)


def _format_legacy_conversation(conversation: list) -> str:
    """Format legacy payload (list of messages) into readable text."""
    lines = []
    for m in conversation:
        role_label = "Cliente" if m.get("role") == "user" else "Atendente"
        lines.append(f"{role_label}: {m.get('content', '')}")
    return "\n".join(lines)


async def handle_learn_from_conversation(task: dict) -> dict:
    """
    Extrai aprendizados de uma conversa e insere no KB do cliente.

    Payload esperado (auto-trigger BRAIN-1):
    - conversation: {task_type, payload, result, response_text, timestamp}
    - owner_type: "mauro" | "client"
    - client_id: UUID do cliente
    - relevance_score: float
    - source_task_id: str

    Payload esperado (legacy):
    - client_id: UUID do cliente
    - client_name: nome do cliente
    - conversation: list of {role, content}
    - conversation_id: str
    """
    payload = task.get("payload", {})
    client_id = payload.get("client_id", "sparkle-internal")
    owner_type = payload.get("owner_type", "client")
    conversation = payload.get("conversation", [])
    conversation_id = (
        payload.get("conversation_id") or payload.get("source_task_id", "unknown")
    )
    task_id = task.get("id")

    # R-T4 Guard: validate isolation
    if owner_type == "mauro" and client_id not in (
        "sparkle-internal",
        settings.sparkle_internal_client_id,
    ):
        print(
            f"[learn] R-T4 WARNING: owner_type=mauro but client_id={client_id}"
            " -- forcing sparkle-internal"
        )
        client_id = "sparkle-internal"

    # Determine payload format and build conversation text
    if isinstance(conversation, list):
        # Legacy format
        if len(conversation) < 2:
            return {
                "message": "Conversa muito curta para extrair aprendizados.",
                "learned": 0,
            }
        client_name = payload.get("client_name", "Cliente")
        conv_text = _format_legacy_conversation(conversation)
    elif isinstance(conversation, dict):
        # Auto-trigger format (BRAIN-1)
        if owner_type == "mauro":
            client_name = "Mauro (Friday)"
        else:
            client_name = payload.get("client_name", "Cliente")
        conv_text = _format_auto_trigger_conversation(conversation)
        if len(conv_text) < 30:
            return {
                "message": "Conversa muito curta para extrair aprendizados.",
                "learned": 0,
            }
    else:
        return {"message": "Formato de conversa nao reconhecido.", "learned": 0}

    prompt = f"Negocio: {client_name}\nOwner: {owner_type}\n\nConversa:\n{conv_text}"

    print(
        f"[learn] Analisando conversa {conversation_id} para"
        f" {client_name} (owner={owner_type})"
    )

    raw = await call_claude(
        prompt=prompt,
        system=EXTRACT_SYSTEM,
        model="claude-haiku-4-5-20251001",
        client_id=client_id,
        task_id=task_id,
        agent_id="friday",
        purpose="conversation_learning",
        max_tokens=512,
    )

    # Parse JSON
    try:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        result = json.loads(clean.strip())
    except (json.JSONDecodeError, IndexError) as e:
        print(f"[learn] JSON parse error: {e} | raw: {raw[:200]}")
        return {
            "message": "Erro ao interpretar resposta do modelo.",
            "learned": 0,
            "raw": raw[:300],
        }

    insights = result.get("insights", [])
    summary = result.get("summary", "nada novo")

    if not insights:
        print(f"[learn] Nada novo para {client_name} -- {summary}")
        return {"message": summary, "learned": 0}

    # Filter only high/medium relevance
    relevant = [i for i in insights if i.get("relevance") in ("alta", "media")]

    if not relevant:
        print(
            f"[learn] {len(insights)} insight(s) de baixa relevancia"
            f" descartados para {client_name}"
        )
        return {
            "message": summary,
            "learned": 0,
            "discarded_low_relevance": len(insights),
        }

    # Ensure table exists
    _ensure_knowledge_base_table()

    # Insert into KB with R-T4 isolation
    inserted = 0
    for insight in relevant:
        try:
            supabase.table("knowledge_base").insert({
                "client_id": client_id,
                "type": insight.get("type", "faq"),
                "content": insight.get("content", ""),
                "source": "conversation_learning",
                "conversation_id": conversation_id,
                "relevance": insight.get("relevance", "media"),
                "owner_type": owner_type,
            }).execute()
            inserted += 1
            print(
                f"[learn] KB inserido (owner={owner_type}):"
                f" [{insight.get('type')}] {insight.get('content', '')[:80]}"
            )
        except Exception as e:
            print(f"[learn] Falha ao inserir insight no KB: {e}")

    print(
        f"[learn] {inserted}/{len(relevant)} insights salvos"
        f" para {client_name} (owner={owner_type})"
    )
    return {
        "message": summary,
        "learned": inserted,
        "total_insights": len(insights),
        "relevant_insights": len(relevant),
        "owner_type": owner_type,
        "insights": [
            {
                "type": i.get("type"),
                "content": i.get("content"),
                "relevance": i.get("relevance"),
            }
            for i in relevant
        ],
    }
