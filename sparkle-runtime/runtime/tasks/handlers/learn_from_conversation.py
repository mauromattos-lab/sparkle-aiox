"""
Analisa uma conversa concluída e extrai aprendizados para o KB do cliente.
Disparado automaticamente após cada conversa finalizada.

Pipeline:
1. Recebe conversa completa (histórico de mensagens)
2. Claude Haiku analisa se há informações novas relevantes
3. Se sim, insere no KB do cliente via tabela `knowledge_base`
4. Retorna o que foi aprendido (ou "nada novo" se não houver)
"""
from __future__ import annotations

import json

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.llm import call_claude

EXTRACT_SYSTEM = """Você é um extrator de conhecimento para o KB de um negócio.
Analise a conversa e extraia APENAS informações novas e relevantes sobre o negócio do cliente.

Exemplos do que capturar:
- Produto ou serviço mencionado que não é óbvio
- Preferência revelada por cliente frequente
- Horário ou condição especial mencionada
- Pergunta frequente que revela lacuna no KB
- Reclamação ou elogio sobre algo específico

Responda com JSON:
{"insights": [{"type": "produto|preferencia|horario|faq|feedback", "content": "descrição concisa", "relevance": "alta|media|baixa"}], "summary": "resumo em 1 linha do que foi aprendido"}

Se não há nada novo, responda: {"insights": [], "summary": "nada novo"}
"""


def _ensure_knowledge_base_table() -> None:
    """Garante que a tabela knowledge_base existe no Supabase."""
    try:
        supabase.table("knowledge_base").select("id").limit(1).execute()
    except Exception:
        # Tabela não existe — criar via SQL
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
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """}).execute()
            print("[learn] knowledge_base table created via RPC")
        except Exception as e:
            print(f"[learn] could not create knowledge_base table: {e}")


async def handle_learn_from_conversation(task: dict) -> dict:
    """
    Extrai aprendizados de uma conversa e insere no KB do cliente.

    Payload esperado:
    - client_id: UUID do cliente
    - client_name: nome do cliente
    - conversation: lista de {"role": "user/assistant", "content": "..."}
    - conversation_id: identificador da conversa
    """
    payload = task.get("payload", {})
    client_id = payload.get("client_id", "sparkle-internal")
    client_name = payload.get("client_name", "Cliente")
    conversation = payload.get("conversation", [])
    conversation_id = payload.get("conversation_id", "unknown")
    task_id = task.get("id")

    if len(conversation) < 2:
        return {"message": "Conversa muito curta para extrair aprendizados.", "learned": 0}

    # Formatar conversa para o prompt
    conv_text = "\n".join(
        f"{'Cliente' if m['role'] == 'user' else 'Atendente'}: {m['content']}"
        for m in conversation
    )

    prompt = f"Negócio: {client_name}\n\nConversa:\n{conv_text}"

    print(f"[learn] Analisando conversa {conversation_id} para {client_name} ({len(conversation)} msgs)")

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

    # Parse do JSON retornado pelo modelo
    try:
        # Remover markdown code fences se presentes
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        result = json.loads(clean.strip())
    except (json.JSONDecodeError, IndexError) as e:
        print(f"[learn] JSON parse error: {e} | raw: {raw[:200]}")
        return {"message": "Erro ao interpretar resposta do modelo.", "learned": 0, "raw": raw[:300]}

    insights = result.get("insights", [])
    summary = result.get("summary", "nada novo")

    if not insights:
        print(f"[learn] Nada novo para {client_name} — {summary}")
        return {"message": summary, "learned": 0}

    # Filtrar apenas relevância alta ou media
    relevant = [i for i in insights if i.get("relevance") in ("alta", "media")]

    if not relevant:
        print(f"[learn] {len(insights)} insight(s) de baixa relevância descartados para {client_name}")
        return {"message": summary, "learned": 0, "discarded_low_relevance": len(insights)}

    # Garantir tabela existe antes de inserir
    _ensure_knowledge_base_table()

    # Inserir no KB
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
            }).execute()
            inserted += 1
            print(f"[learn] KB inserido: [{insight.get('type')}] {insight.get('content', '')[:80]}")
        except Exception as e:
            print(f"[learn] Falha ao inserir insight no KB: {e}")

    print(f"[learn] {inserted}/{len(relevant)} insights salvos para {client_name}")
    return {
        "message": summary,
        "learned": inserted,
        "total_insights": len(insights),
        "relevant_insights": len(relevant),
        "insights": [{"type": i.get("type"), "content": i.get("content"), "relevance": i.get("relevance")} for i in relevant],
    }
