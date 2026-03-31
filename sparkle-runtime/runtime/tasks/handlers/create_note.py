"""
Create note handler — salva uma nota rápida do Mauro no Supabase.
Ativado quando intent = "create_note" (ex: "anota X", "lembra que Y", "registra Z").

Tenta inserir na tabela `notes`. Se não existir, trata o erro graciosamente
e retorna confirmação sem crashar o fluxo.
"""
from __future__ import annotations

from datetime import datetime, timezone

from runtime.config import settings
from runtime.db import supabase


def handle_create_note(task: dict) -> dict:
    """
    Extrai o conteúdo da nota do payload e salva no Supabase.
    Retorna {"message": "Anotado ✅ — <resumo>"}.
    """
    payload = task.get("payload", {})
    original_text: str = payload.get("original_text", "")
    summary: str = payload.get("summary", original_text[:200])

    # Limpa prefixos comuns: "anota:", "lembra que", "registra"
    note_content = _extract_note_content(original_text)

    note_record = {
        "client_id": settings.sparkle_internal_client_id,
        "agent_id": "friday",
        "task_id": task.get("id"),
        "content": note_content,
        "summary": summary,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        supabase.table("notes").insert(note_record).execute()
        saved = True
    except Exception as e:
        # Tabela pode não existir ainda — não quebra o fluxo
        saved = False
        error_hint = str(e)[:120]

    if saved:
        short = note_content[:100] + ("..." if len(note_content) > 100 else "")
        return {"message": f"Anotado \u2705 \u2014 {short}"}
    else:
        # Fallback: confirma mas avisa que persistência falhou
        short = note_content[:100]
        return {
            "message": (
                f"Recebi a nota \u2014 \u201c{short}\u201d\n"
                f"\u26a0\ufe0f N\u00e3o consegui salvar no banco ({error_hint}). "
                "Mauro, a tabela `notes` pode precisar ser criada no Supabase."
            )
        }


def _extract_note_content(text: str) -> str:
    """Remove gatilhos de intenção do início do texto para ficar só o conteúdo."""
    text = text.strip()
    prefixes = [
        "anota:", "anota ", "anotação:", "lembra que ", "lembra:", "lembre que ",
        "registra:", "registra ", "nota:", "nota ", "save:", "salva ",
    ]
    lower = text.lower()
    for prefix in prefixes:
        if lower.startswith(prefix):
            return text[len(prefix):].strip()
    return text
