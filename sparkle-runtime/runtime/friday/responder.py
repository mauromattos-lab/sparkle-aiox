"""
Friday — Response builder.
Converts a completed task result into a human-friendly reply for WhatsApp.
"""
from __future__ import annotations

from typing import Optional


def build_response(task: dict) -> str:
    """
    Build a text response from a completed runtime_task.
    Falls back gracefully if result is empty or task failed.
    """
    status = task.get("status", "unknown")
    task_type = task.get("task_type", "")
    result = task.get("result") or {}
    error = task.get("error")

    if status == "failed":
        return f"Houve um erro ao processar sua solicitação: {error or 'erro desconhecido'}. Tente novamente."

    if status == "pending" or status == "running":
        return "Estou processando sua solicitação. Assim que terminar, te aviso aqui."

    # status == "done"
    message = result.get("message") or result.get("text") or result.get("summary")
    if message:
        return str(message)

    # Generic fallback for unknown task types
    return f"Tarefa '{task_type}' concluída. Resultado: {str(result)[:300]}"


def build_response_plain(task: dict) -> str:
    """
    Versão sem markdown do build_response — adequada para TTS/áudio.
    Remove asteriscos (bold/italic) e underlines para que o gTTS leia
    o texto de forma natural, sem soletrar os símbolos.
    """
    import re

    text = build_response(task)
    # Remove **bold** e *italic*
    text = re.sub(r"\*+([^*]+)\*+", r"\1", text)
    # Remove _underline_
    text = re.sub(r"_([^_]+)_", r"\1", text)
    # Remove cabeçalhos markdown (# Título)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Colapsa múltiplos espaços/quebras de linha excessivas
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_error_response(exc: Exception) -> str:
    return f"Erro interno: {str(exc)[:200]}. Mauro, verifica os logs."
