"""
gap_report handler — relatório semanal de gaps do Brain.

O que faz:
  - Busca tasks da última semana em runtime_tasks onde o resultado
    indica que o Brain não tinha resposta
  - Busca registros recentes em knowledge_base com source = "conversation_learning"
  - Usa Claude Haiku para analisar padrões: temas perguntados que o Brain não sabe
  - Gera lista priorizada (máximo 5 temas)
  - Envia via WhatsApp para MAURO_WHATSAPP

Acionado manualmente ("gaps do brain", "o que o brain não sabe") ou via cron
toda segunda-feira às 11h UTC (8h Brasília).
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.llm import call_claude

# Frases que indicam que o Brain não tinha resposta
_GAP_INDICATORS = [
    "ainda não tenho conhecimento",
    "brain ainda não tem",
    "não encontrei informação",
    "não tenho essa informação",
    "não foi encontrado no brain",
    "sem resultados no brain",
]

_ANALYZE_SYSTEM = """Você é um analista de lacunas de conhecimento do Brain da Sparkle AIOX.

Você receberá:
1. Lista de resultados de tasks brain_query onde o Brain não tinha resposta
2. Lista de tópicos aprendidos recentemente via conversation_learning (o que chegou novo)

Sua tarefa: identificar os GAPS REAIS — temas que as pessoas perguntam mas o Brain ainda não sabe responder.

Regras:
- Liste no máximo 5 gaps, do mais crítico ao menos crítico
- Cada gap deve ter: tema curto (3-6 palavras), frequência estimada e recomendação de ação
- Seja direto e prático
- Em português

Responda APENAS com JSON válido:
{"gaps": [{"tema": "X", "frequencia": "alta|media|baixa", "acao": "descrição breve do que adicionar ao Brain"}], "resumo": "1 linha resumindo a situação geral dos gaps"}

Se não houver gaps relevantes: {"gaps": [], "resumo": "Brain está bem coberto — sem gaps críticos esta semana"}"""


async def handle_gap_report(task: dict) -> dict:
    """
    Gera relatório de gaps do Brain e envia via WhatsApp para Mauro.
    Retorna {"message": "Gap report enviado para Mauro"}.
    """
    texto = await _build_gap_report_text(task)

    if settings.mauro_whatsapp:
        try:
            from runtime.integrations.zapi import send_text
            await asyncio.to_thread(send_text, settings.mauro_whatsapp, texto)
        except Exception as e:
            print(f"[gap_report] failed to send WhatsApp: {e}")

    return {"message": "Gap report enviado para Mauro"}


# ── Builder ────────────────────────────────────────────────────────────────────

async def _build_gap_report_text(task: dict) -> str:
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("America/Sao_Paulo")
    now_brt = datetime.now(tz)
    cutoff_utc = datetime.now(timezone.utc) - timedelta(days=7)
    cutoff_iso = cutoff_utc.isoformat()

    lines: list[str] = [
        f"*Gap Report — Brain Sparkle AIOX* — {now_brt.strftime('%d/%m/%Y')}",
        "",
    ]

    # ── 1. Buscar tasks brain_query sem resposta na última semana ──────────────
    unanswered_queries: list[str] = []
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("payload,result,created_at")
            .eq("task_type", "brain_query")
            .eq("status", "done")
            .gte("created_at", cutoff_iso)
            .execute()
        )
        tasks_data = res.data or []

        for t in tasks_data:
            result = t.get("result") or {}
            # result pode ser dict ou string
            result_str = (
                json.dumps(result) if isinstance(result, dict) else str(result)
            ).lower()
            is_gap = any(indicator in result_str for indicator in _GAP_INDICATORS)
            if is_gap:
                payload = t.get("payload") or {}
                query = payload.get("query") or payload.get("original_text") or ""
                if query:
                    unanswered_queries.append(query)

        print(f"[gap_report] {len(unanswered_queries)} queries sem resposta encontradas")
    except Exception as e:
        print(f"[gap_report] erro ao buscar brain_query tasks: {e}")

    # ── 2. Buscar registros conversation_learning da última semana ────────────
    learned_topics: list[str] = []
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("knowledge_base")
            .select("type,content,client_id,relevance,created_at")
            .eq("source", "conversation_learning")
            .gte("created_at", cutoff_iso)
            .order("created_at", desc=True)
            .execute()
        )
        kb_data = res.data or []
        for row in kb_data:
            learned_topics.append(
                f"[{row.get('type', '?')}|{row.get('relevance', '?')}] {row.get('content', '')}"
            )

        print(f"[gap_report] {len(learned_topics)} registros conversation_learning encontrados")
    except Exception as e:
        print(f"[gap_report] erro ao buscar knowledge_base: {e}")

    # ── 3. Seção de sumário bruto no relatório ─────────────────────────────────
    lines.append(f"*Queries sem resposta (7 dias):* {len(unanswered_queries)}")
    lines.append(f"*Novos aprendizados via conversas:* {len(learned_topics)}")
    lines.append("")

    # ── 4. Análise Claude Haiku — identificar padrões de gaps ─────────────────
    gap_analysis: dict = {}
    try:
        if not unanswered_queries and not learned_topics:
            gap_analysis = {
                "gaps": [],
                "resumo": "Nenhuma query sem resposta e nenhum aprendizado novo — sem dados suficientes para análise.",
            }
        else:
            prompt_parts = []
            if unanswered_queries:
                prompt_parts.append(
                    "=== QUERIES QUE O BRAIN NÃO SOUBE RESPONDER ===\n"
                    + "\n".join(f"- {q}" for q in unanswered_queries[:30])
                )
            if learned_topics:
                prompt_parts.append(
                    "=== NOVOS APRENDIZADOS (conversation_learning) ===\n"
                    + "\n".join(f"- {t}" for t in learned_topics[:30])
                )

            prompt = "\n\n".join(prompt_parts)
            task_id = task.get("id")

            raw = await call_claude(
                prompt=prompt,
                system=_ANALYZE_SYSTEM,
                model="claude-haiku-4-5-20251001",
                client_id=settings.sparkle_internal_client_id,
                task_id=task_id,
                agent_id="friday",
                purpose="gap_report_analysis",
                max_tokens=512,
            )

            # Parse JSON
            clean = raw.strip()
            if clean.startswith("```"):
                lines_raw = clean.splitlines()
                lines_raw = [l for l in lines_raw if not l.strip().startswith("```")]
                clean = "\n".join(lines_raw).strip()
            gap_analysis = json.loads(clean)

    except json.JSONDecodeError as e:
        print(f"[gap_report] JSON parse error: {e}")
        gap_analysis = {"gaps": [], "resumo": "Erro ao analisar padrões — verifique os logs."}
    except Exception as e:
        print(f"[gap_report] erro na análise Claude: {e}")
        gap_analysis = {"gaps": [], "resumo": f"Erro na análise: {e}"}

    # ── 5. Formatar gaps no relatório ──────────────────────────────────────────
    gaps = gap_analysis.get("gaps", [])
    resumo = gap_analysis.get("resumo", "")

    if gaps:
        lines.append(f"*Top {len(gaps)} Gaps do Brain:*")
        for i, gap in enumerate(gaps[:5], 1):
            tema = gap.get("tema", "?")
            freq = gap.get("frequencia", "?")
            acao = gap.get("acao", "")
            lines.append(f"  {i}. *{tema}* (freq: {freq})")
            if acao:
                lines.append(f"     → {acao}")
        lines.append("")
    else:
        lines.append("*Gaps:* Nenhum gap crítico identificado esta semana.")
        lines.append("")

    if resumo:
        lines.append(f"_{resumo}_")
        lines.append("")

    lines.append("_Sparkle AIOX — Gap Report semanal automático_")

    return "\n".join(lines)
