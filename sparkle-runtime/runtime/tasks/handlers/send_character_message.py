"""
send_character_message handler — wrapper para o Character Runtime
com suporte a tool-use (Loja Integrada, etc.).

Fluxo:
  1. Detecta se a mensagem contém intent de e-commerce (pedido, CPF, etc.)
  2. Se sim, consulta a API da Loja Integrada via handle_loja_integrada_query
  3. Injeta o resultado como contexto extra no soul_prompt
  4. Invoca o agente do personagem via call_claude (com soul_prompt enriquecido)
  5. Retorna {message, character_slug, model}

Não usa o character_handler.send_character_message porque:
  - Precisa injetar contexto de ferramentas (Loja Integrada) ANTES da LLM
  - O character handler não suporta tool-use — é apenas LLM puro
  - Aqui fazemos: detect intent → fetch data → enrich prompt → call LLM
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.llm import call_claude

_TZ_BRASILIA = ZoneInfo("America/Sao_Paulo")

# ── Padrões para detectar intent de consulta de pedido ──────

# CPF: 123.456.789-00 ou 12345678900
_CPF_PATTERN = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")

# E-mail
_EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")

# Número de pedido: # seguido de dígitos, ou apenas sequência de 4+ dígitos
# quando no contexto de "pedido"
_ORDER_ID_PATTERN = re.compile(r"#\s*(\d{3,})")
_ORDER_CONTEXT_PATTERN = re.compile(
    r"(?:pedido|order|encomenda|compra)\s*(?:n[uú]mero|n[oº]|#)?\s*:?\s*(\d{3,})",
    re.IGNORECASE,
)
# Sequência isolada de 4+ dígitos quando a mensagem menciona pedido
_DIGITS_PATTERN = re.compile(r"\b(\d{4,})\b")

# Palavras-chave que indicam intent de consulta de pedido
_ORDER_KEYWORDS = {
    "pedido", "encomenda", "compra", "rastrear", "rastreio",
    "rastreamento", "entrega", "enviado", "status", "onde está",
    "onde esta", "meu pedido", "minha compra", "prazo",
    "acompanhar", "tracking", "track",
}


def _detect_order_intent(text: str) -> dict:
    """
    Detecta se a mensagem contém uma consulta de pedido.
    Retorna dict com cpf, email, pedido_id (os que forem encontrados).
    Retorna dict vazio se não detectar intent de e-commerce.
    """
    lower = text.lower()
    result = {}

    # Detectar CPF
    cpf_match = _CPF_PATTERN.search(text)
    if cpf_match:
        result["cpf"] = cpf_match.group()

    # Detectar e-mail
    email_match = _EMAIL_PATTERN.search(text)
    if email_match:
        result["email"] = email_match.group()

    # Detectar número de pedido
    order_match = _ORDER_ID_PATTERN.search(text)
    if order_match:
        result["pedido_id"] = order_match.group(1)
    else:
        order_ctx_match = _ORDER_CONTEXT_PATTERN.search(text)
        if order_ctx_match:
            result["pedido_id"] = order_ctx_match.group(1)

    # Se encontrou algum identificador, retorna
    if result:
        return result

    # Se tem palavras-chave de pedido + dígitos, pode ser pedido_id
    has_keyword = any(kw in lower for kw in _ORDER_KEYWORDS)
    if has_keyword:
        digits_match = _DIGITS_PATTERN.search(text)
        if digits_match:
            result["pedido_id"] = digits_match.group(1)

    return result


def _is_ecommerce_client(client_config: dict) -> bool:
    """Verifica se o cliente tem integração e-commerce habilitada."""
    btype = (client_config.get("business_type") or "").lower()
    return btype in ("ecommerce", "e-commerce", "loja", "loja_integrada")


# ── Histórico de conversa ──────────────────────────────────

async def _get_zenya_history(client_id: str, phone: str, limit: int = 6) -> list[dict]:
    """Busca histórico de conversa Zenya por client_id + phone na tabela zenya_messages."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("zenya_messages")
            .select("role,content")
            .eq("client_id", client_id)
            .eq("phone", phone)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        items = res.data or []
        return list(reversed(items))
    except Exception as e:
        print(f"[send_character_message] history fetch failed: {e}")
        return []


async def _save_zenya_history(
    client_id: str, phone: str, user_msg: str, assistant_msg: str
) -> None:
    """Salva par de mensagens no histórico de conversa Zenya em zenya_messages."""
    try:
        from datetime import timezone, timedelta
        now = datetime.now(timezone.utc)
        await asyncio.to_thread(
            lambda: supabase.table("zenya_messages").insert([
                {
                    "phone": phone,
                    "role": "user",
                    "content": user_msg,
                    "created_at": now.isoformat(),
                    "client_id": client_id,
                },
                {
                    "phone": phone,
                    "role": "assistant",
                    "content": assistant_msg,
                    "created_at": (now + timedelta(seconds=1)).isoformat(),
                    "client_id": client_id,
                },
            ]).execute()
        )
    except Exception as e:
        print(f"[send_character_message] history save failed: {e}")


# ── Handler principal ──────────────────────────────────────

async def handle_send_character_message(task: dict) -> dict:
    """
    Processa mensagem para um personagem Zenya com suporte a tool-use.

    Payload esperado:
    {
        "character": "zenya",
        "message": "texto do cliente",
        "phone": "5511999999999",
        "soul_prompt": "...",
        "lore": "...",
        "client_name": "Fun Personalize",
        "client_id": "fun-personalize"  (via task.client_id)
    }
    """
    payload = task.get("payload", {})
    client_id = task.get("client_id", "")
    message = payload.get("message", "").strip()
    phone = payload.get("phone", "")
    soul_prompt = payload.get("soul_prompt", "")
    lore = payload.get("lore", "")
    client_name = payload.get("client_name", "")

    if not message:
        return {"message": "Recebi uma mensagem vazia. Pode repetir?"}

    # ── 1. Buscar config do cliente para checar se tem e-commerce ─────
    client_config = None
    if client_id:
        try:
            res = await asyncio.to_thread(
                lambda: supabase.table("zenya_clients")
                .select("*")
                .eq("client_id", client_id)
                .maybe_single()
                .execute()
            )
            client_config = res.data if res else None
        except Exception:
            pass

    # ── 2. Detectar intent de e-commerce (Loja Integrada) ─────────────
    tool_context = ""
    if client_config and _is_ecommerce_client(client_config):
        order_params = _detect_order_intent(message)
        if order_params:
            try:
                from runtime.tasks.handlers.loja_integrada_query import (
                    handle_loja_integrada_query,
                )
                li_task = {
                    "payload": order_params,
                    "id": task.get("id"),
                }
                li_result = await handle_loja_integrada_query(li_task)
                li_message = li_result.get("message", "")
                total = li_result.get("total_encontrado", 0)

                if total > 0:
                    tool_context = (
                        f"\n\n--- DADOS REAIS DO PEDIDO (consulta automática) ---\n"
                        f"{li_message}\n"
                        f"--- FIM DOS DADOS DO PEDIDO ---\n"
                        f"Use estas informações reais para responder o cliente. "
                        f"NÃO invente dados diferentes dos listados acima."
                    )
                elif li_result.get("error"):
                    tool_context = (
                        f"\n\n--- CONSULTA DE PEDIDO ---\n"
                        f"Tentei consultar mas houve um problema: {li_result['error']}\n"
                        f"Informe o cliente de forma amigável e sugira tentar novamente.\n"
                        f"--- FIM ---"
                    )
                else:
                    tool_context = (
                        f"\n\n--- CONSULTA DE PEDIDO ---\n"
                        f"Não encontrei pedidos para os dados informados. "
                        f"Peça ao cliente para verificar se o dado está correto.\n"
                        f"--- FIM ---"
                    )
            except Exception as e:
                print(f"[send_character_message] Loja Integrada query failed: {e}")
                # Non-fatal: Zenya responde sem dados do pedido

    # ── 2.5. C2-B3: Inject sparkle-lore context for character ──────────
    lore_context = ""
    try:
        from runtime.brain.namespace_context import fetch_namespace_context
        lore_context = await fetch_namespace_context("sparkle-lore", message)
    except Exception as e:
        print(f"[send_character_message] C2-B3 namespace context injection failed (non-fatal): {e}")

    # ── 3. Montar system prompt enriquecido ───────────────────────────
    now = datetime.now(_TZ_BRASILIA)
    date_str = now.strftime("%d/%m/%Y %H:%M")

    system_prompt = ""
    # C2-B3: Lore context from Brain appears BEFORE other context (AC-14)
    if lore_context:
        system_prompt += lore_context + "\n\n"
    system_prompt += soul_prompt or ""
    if lore:
        system_prompt += f"\n\n--- Contexto adicional ---\n{lore}"
    if tool_context:
        system_prompt += tool_context
    system_prompt += f"\n\nData e hora atual: {date_str} (horário de Brasília)"
    system_prompt += f"\nNúmero do cliente: {phone}"

    # ── 4. Buscar histórico de conversa ───────────────────────────────
    history = await _get_zenya_history(client_id, phone)
    history_text = ""
    for msg in history:
        role_label = "Cliente" if msg.get("role") == "user" else "Zenya"
        history_text += f"{role_label}: {msg.get('content', '')}\n"

    if history_text:
        prompt_with_history = f"{history_text}Cliente: {message}\nZenya:"
    else:
        prompt_with_history = message

    # ── 5. Chamar Claude ──────────────────────────────────────────────
    response = await call_claude(
        prompt=prompt_with_history,
        system=system_prompt,
        model="claude-haiku-4-5-20251001",
        client_id=client_id or settings.sparkle_internal_client_id,
        task_id=task.get("id"),
        agent_id="zenya",
        purpose="zenya_chat",
        max_tokens=512,
    )

    # ── 6. Salvar no histórico ────────────────────────────────────────
    await _save_zenya_history(client_id, phone, message, response)

    return {
        "message": response,
        "character_slug": "zenya",
        "model": "claude-haiku-4-5-20251001",
        "client_id": client_id,
        "client_name": client_name,
        "had_tool_context": bool(tool_context),
    }
