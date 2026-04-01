"""
Gera sumário de conversa e dispara análise de aprendizado (learn_from_conversation).

Disparado quando uma conversa é considerada concluída — sem mensagem por X minutos,
detectado por health_alert ou trigger manual.

Pipeline:
1. Recebe phone + client_id
2. Busca últimas mensagens de conversation_history
3. Cria task learn_from_conversation com a conversa completa
"""
from __future__ import annotations

from runtime.db import supabase


async def handle_conversation_summary(task: dict) -> dict:
    """
    Busca histórico de conversa de um número e cria task de aprendizado.

    Payload esperado:
    - phone: número do cliente final
    - client_id: UUID do cliente Sparkle
    - client_name: nome do cliente Sparkle
    """
    payload = task.get("payload", {})
    phone = payload.get("phone", "")
    client_id = payload.get("client_id", "sparkle-internal")
    client_name = payload.get("client_name", "Sparkle")

    if not phone:
        return {"message": "Payload inválido: campo 'phone' obrigatório.", "learned": 0}

    # Buscar últimas mensagens da conversa
    try:
        res = (
            supabase.table("conversation_history")
            .select("role,content,created_at")
            .eq("phone", phone)
            .order("created_at", desc=False)
            .limit(20)
            .execute()
        )
        rows = res.data or []
    except Exception as e:
        print(f"[conv_summary] Falha ao buscar histórico de {phone}: {e}")
        return {"message": f"Erro ao buscar histórico: {e}", "learned": 0}

    conversation = [{"role": r["role"], "content": r["content"]} for r in rows]

    if len(conversation) < 2:
        print(f"[conv_summary] Conversa de {phone} muito curta ({len(conversation)} msgs) — ignorando")
        return {"message": "Conversa muito curta para aprender.", "learned": 0}

    conversation_id = f"{phone}_{len(conversation)}msgs"

    # Criar task de aprendizado
    try:
        new_task = supabase.table("runtime_tasks").insert({
            "agent_id": "friday",
            "client_id": client_id,
            "task_type": "learn_from_conversation",
            "payload": {
                "client_id": client_id,
                "client_name": client_name,
                "conversation": conversation,
                "conversation_id": conversation_id,
            },
            "status": "pending",
            "priority": 3,
        }).execute()

        task_id = new_task.data[0]["id"]
        print(f"[conv_summary] Task learn_from_conversation criada: {task_id} ({len(conversation)} msgs de {phone})")
        return {
            "message": f"Análise de {len(conversation)} mensagens iniciada.",
            "task_id": task_id,
            "conversation_id": conversation_id,
        }
    except Exception as e:
        print(f"[conv_summary] Falha ao criar task de aprendizado: {e}")
        return {"message": f"Erro ao criar task: {e}", "learned": 0}
