"""
SYS-5: observer_gap_analysis handler — detecta gaps de conhecimento E capacidade.
Evolucao do gap_report: analisa tasks falhadas, brain queries sem resposta,
agentes indisponiveis e padroes repetitivos. Persiste em gap_reports e
envia resumo para Mauro via WhatsApp.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.llm import call_claude
from runtime.integrations.zapi import send_text


_OBSERVER_SYSTEM = """Voce e o Observer da Sparkle AIOX — analisa dados operacionais e detecta lacunas.

Voce recebera 4 fontes de dados:
1. Tasks que falharam com "handler nao encontrado" ou "agente nao disponivel"
2. Brain queries sem resposta
3. Agentes solicitados que estao em _KNOWN_AGENTS mas nao em _AVAILABLE_AGENTS
4. Padroes de conversa repetitivos do Mauro com a Friday

Sua tarefa: identificar gaps REAIS e acionaveis. Nao reporte ruido.

Para cada gap detectado, classifique:
- report_type: knowledge | capability | agent | handler
- severity: critical (bloqueia trabalho) | high (afeta frequentemente) | medium | low
- suggested_action: o que fazer para resolver (1 frase pratica)

Responda com JSON:
{"gaps": [{"report_type": "...", "summary": "...", "details": {...}, "severity": "...", "frequency": N}]}

Maximo 7 gaps. Se nao houver gaps relevantes: {"gaps": []}"""


def _parse_json_response(raw: str) -> dict | None:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


async def _get_failed_tasks_last_week() -> list[str]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    result = await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks")
        .select("task_type,payload,result,status")
        .eq("status", "failed")
        .gte("created_at", cutoff)
        .limit(50)
        .execute()
    )
    items = []
    for t in (result.data or []):
        result_str = str(t.get("result", "")).lower()
        if "handler" in result_str or "not found" in result_str or "nao encontrado" in result_str:
            items.append(f"task_type={t['task_type']}: {result_str[:200]}")
    return items


async def _get_unanswered_brain_queries() -> list[str]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    result = await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks")
        .select("payload,result")
        .eq("task_type", "brain_query")
        .eq("status", "done")
        .gte("created_at", cutoff)
        .limit(50)
        .execute()
    )
    items = []
    for t in (result.data or []):
        result_str = str(t.get("result", "")).lower()
        if "nenhum" in result_str or "sem resultado" in result_str or "not found" in result_str:
            payload = t.get("payload", {})
            query = payload.get("query", payload.get("original_text", "?"))
            items.append(f"query='{query[:100]}': sem resposta no Brain")
    return items


async def _get_unavailable_agent_requests() -> list[str]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    result = await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks")
        .select("payload,result")
        .eq("task_type", "activate_agent")
        .eq("status", "done")
        .gte("created_at", cutoff)
        .limit(50)
        .execute()
    )
    items = []
    for t in (result.data or []):
        result_str = str(t.get("result", "")).lower()
        if "nao tem execucao autonoma" in result_str or "nao reconhecido" in result_str:
            payload = t.get("payload", {})
            agent = payload.get("agent", "?")
            items.append(f"@{agent}: solicitado mas sem subagent implementado")
    return items


async def _get_repeated_patterns() -> list[str]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    result = await asyncio.to_thread(
        lambda: supabase.table("conversation_history")
        .select("content")
        .eq("role", "user")
        .gte("created_at", cutoff)
        .limit(100)
        .execute()
    )
    items = []
    for c in (result.data or []):
        content = c.get("content", "")
        if content and len(content) > 5:
            items.append(content[:150])
    return items


async def _find_similar_gap(summary: str) -> dict | None:
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("gap_reports")
            .select("id,summary,frequency")
            .eq("status", "pending")
            .limit(50)
            .execute()
        )
        summary_lower = summary.lower()
        for gap in (result.data or []):
            existing_lower = gap.get("summary", "").lower()
            # Simple similarity: check if core words overlap significantly
            words_new = set(summary_lower.split())
            words_existing = set(existing_lower.split())
            if len(words_new & words_existing) >= min(3, len(words_new) // 2):
                return gap
    except Exception:
        pass
    return None


async def _increment_gap_frequency(gap_id: str, increment: int = 1) -> None:
    try:
        gap = await asyncio.to_thread(
            lambda: supabase.table("gap_reports")
            .select("frequency")
            .eq("id", gap_id)
            .single()
            .execute()
        )
        current = gap.data.get("frequency", 1) if gap.data else 1
        await asyncio.to_thread(
            lambda: supabase.table("gap_reports")
            .update({"frequency": current + increment, "updated_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", gap_id)
            .execute()
        )
    except Exception as e:
        print(f"[observer] falha ao incrementar frequencia: {e}")


async def _insert_gap_report(gap: dict) -> None:
    try:
        await asyncio.to_thread(
            lambda: supabase.table("gap_reports").insert({
                "report_type": gap.get("report_type", "knowledge"),
                "summary": gap.get("summary", ""),
                "details": gap.get("details", {}),
                "frequency": gap.get("frequency", 1),
                "severity": gap.get("severity", "medium"),
                "status": "pending",
            }).execute()
        )
    except Exception as e:
        print(f"[observer] falha ao inserir gap: {e}")


def _format_gap_whatsapp(gaps: list[dict]) -> str:
    today = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    lines = [f"*Observer Report — Sparkle AIOX* — {today}\n"]
    lines.append(f"*{len(gaps)} gaps detectados esta semana:*\n")

    for i, gap in enumerate(gaps, 1):
        rtype = gap.get("report_type", "?").upper()
        severity = gap.get("severity", "media")
        summary = gap.get("summary", "")
        details = gap.get("details", {})
        action = details.get("suggested_action", "") or details.get("suggested_handler", "")
        lines.append(f"{i}. [{rtype}|{severity}] {summary}")
        if action:
            lines.append(f"   → {action}")
        lines.append(f'   _Responda: "aprova {i}" para implementar_\n')

    lines.append('_Responda "aprova 1,3" ou "rejeita 2" — ou "aprova todos"_')
    return "\n".join(lines)


def _count_by_type(gaps: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for g in gaps:
        t = g.get("report_type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return counts


async def handle_observer_gap_analysis(task: dict) -> dict:
    """
    Evolucao do gap_report: detecta gaps de conhecimento E capacidade.
    Persiste em gap_reports. Envia resumo para Mauro via WhatsApp.
    """
    task_id = task.get("id")

    # 1. Coletar dados das 4 fontes
    failed_tasks, unanswered_queries, unavailable_agents, repeated_patterns = await asyncio.gather(
        _get_failed_tasks_last_week(),
        _get_unanswered_brain_queries(),
        _get_unavailable_agent_requests(),
        _get_repeated_patterns(),
    )

    # 2. Montar prompt com os dados
    prompt_parts = []
    if failed_tasks:
        prompt_parts.append(
            "=== TASKS FALHADAS (handler nao encontrado) ===\n"
            + "\n".join(f"- {t}" for t in failed_tasks[:20])
        )
    if unanswered_queries:
        prompt_parts.append(
            "=== BRAIN QUERIES SEM RESPOSTA ===\n"
            + "\n".join(f"- {q}" for q in unanswered_queries[:20])
        )
    if unavailable_agents:
        prompt_parts.append(
            "=== AGENTES SOLICITADOS SEM SUBAGENT ===\n"
            + "\n".join(f"- {a}" for a in unavailable_agents[:10])
        )
    if repeated_patterns:
        prompt_parts.append(
            "=== PADROES REPETITIVOS DE CONVERSA ===\n"
            + "\n".join(f"- {p}" for p in repeated_patterns[:15])
        )

    if not prompt_parts:
        return {"message": "Observer: nenhum dado para analisar esta semana", "gaps": []}

    prompt = "\n\n".join(prompt_parts)

    # 3. Claude Sonnet analisa
    raw = await call_claude(
        prompt=prompt,
        system=_OBSERVER_SYSTEM,
        model="claude-sonnet-4-6",
        client_id=settings.sparkle_internal_client_id,
        task_id=task_id,
        agent_id="observer",
        purpose="observer_gap_analysis",
        max_tokens=2048,
    )

    # 4. Parse e persistir gaps
    analysis = _parse_json_response(raw)
    gaps = analysis.get("gaps", []) if analysis else []

    persisted = 0
    for gap in gaps:
        existing = await _find_similar_gap(gap.get("summary", ""))
        if existing:
            await _increment_gap_frequency(existing["id"], gap.get("frequency", 1))
        else:
            await _insert_gap_report(gap)
            persisted += 1

    # 5. Enviar resumo para Mauro via WhatsApp
    if gaps and settings.mauro_whatsapp:
        text = _format_gap_whatsapp(gaps)
        try:
            await asyncio.to_thread(send_text, settings.mauro_whatsapp, text)
        except Exception as e:
            print(f"[observer] falha ao enviar WhatsApp: {e}")

    return {
        "message": f"Observer: {len(gaps)} gaps detectados, {persisted} novos",
        "gaps_total": len(gaps),
        "gaps_new": persisted,
        "gaps_by_type": _count_by_type(gaps),
    }
