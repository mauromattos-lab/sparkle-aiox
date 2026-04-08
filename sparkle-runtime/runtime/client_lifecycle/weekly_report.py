"""
Weekly Client Report — W2-CLC-2.

Gera e envia via WhatsApp um relatório semanal automático para cada cliente Zenya ativo.
Métricas: volume de atendimentos, horário de pico, top 3 temas, variação vs. semana anterior.

Funções públicas:
  async generate_weekly_report(client_id, week_start=None) -> dict
  async send_weekly_report(client_id, dry_run=False) -> dict
  async send_all_weekly_reports(dry_run=False) -> dict
"""
from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from runtime.db import supabase
from runtime.config import settings

logger = logging.getLogger(__name__)

# Limiar mínimo de eventos para gerar relatório
_MIN_EVENTS = 10

# Limiar de health_score abaixo do qual não enviamos (Friday alerta Mauro primeiro)
_CRITICAL_HEALTH_SCORE = 30

# Stopwords básicas em português para keyword frequency fallback
_STOPWORDS = {
    "a", "as", "o", "os", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas", "por", "para", "com", "sem", "que", "e", "ou",
    "se", "eu", "tu", "ele", "ela", "eles", "elas", "nós", "você", "vocês",
    "me", "te", "lhe", "nos", "vos", "lhes", "meu", "minha", "seu", "sua",
    "não", "sim", "mais", "mas", "já", "ainda", "muito", "pouco", "bem", "mal",
    "aqui", "lá", "ali", "quando", "como", "onde", "quem", "qual",
    "olá", "oi", "bom", "boa", "dia", "tarde", "noite", "obrigado", "obrigada",
}


def _current_week_start() -> date:
    """Retorna a segunda-feira da semana atual."""
    today = date.today()
    return today - timedelta(days=today.weekday())  # weekday(): 0=segunda


def _week_range(week_start: date) -> tuple[str, str]:
    """Retorna (iso_start, iso_end) para segunda-feira até domingo da semana."""
    start = datetime(week_start.year, week_start.month, week_start.day, 0, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=7)
    return start.isoformat(), end.isoformat()


def _prev_week_range(week_start: date) -> tuple[str, str]:
    prev_start = week_start - timedelta(days=7)
    return _week_range(prev_start)


# ── Data fetching ────────────────────────────────────────────

async def _fetch_zenya_client(client_id: str) -> dict | None:
    """Busca cliente em zenya_clients (usa client_id TEXT)."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .select("id,client_id,business_name,phone_number,active,zapi_instance_id,zapi_token,zapi_client_token")
            .eq("client_id", client_id)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        return (res.data or [None])[0]
    except Exception as e:
        logger.warning("[weekly_report] fetch_zenya_client %s: %s", client_id, e)
        return None


async def _fetch_active_zenya_clients() -> list[dict]:
    """Retorna todos os clientes Zenya ativos com phone_number preenchido."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .select("id,client_id,business_name,phone_number,active")
            .eq("active", True)
            .not_.is_("phone_number", "null")
            .execute()
        )
        return [r for r in (res.data or []) if r.get("phone_number", "").strip()]
    except Exception as e:
        logger.error("[weekly_report] fetch_active_zenya_clients: %s", e)
        return []


async def _fetch_events(client_id: str, iso_start: str, iso_end: str) -> list[dict]:
    """Busca zenya_events do cliente no período. client_id em zenya_events é UUID."""
    try:
        # Tenta filtrar por client_id como UUID (zenya_events.client_id = uuid)
        res = await asyncio.to_thread(
            lambda: supabase.table("zenya_events")
            .select("id,event_type,payload,created_at")
            .eq("client_id", client_id)
            .gte("created_at", iso_start)
            .lt("created_at", iso_end)
            .order("created_at")
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.warning("[weekly_report] fetch_events %s: %s", client_id, e)
        return []


async def _fetch_health_score(client_id: str) -> Optional[float]:
    """Busca health_score atual do cliente em client_health."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("client_health")
            .select("health_score")
            .eq("client_id", client_id)
            .order("calculated_at", desc=True)
            .limit(1)
            .execute()
        )
        data = res.data or []
        return float(data[0]["health_score"]) if data else None
    except Exception as e:
        logger.warning("[weekly_report] fetch_health_score %s: %s", client_id, e)
        return None


async def _already_sent_this_week(client_id: str, week_start: date) -> bool:
    """Verifica se já enviamos relatório para este cliente nesta semana."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("weekly_report_log")
            .select("id")
            .eq("client_id", client_id)
            .eq("week_start", week_start.isoformat())
            .eq("dry_run", False)
            .limit(1)
            .execute()
        )
        return bool(res.data)
    except Exception as e:
        logger.warning("[weekly_report] already_sent check %s: %s", client_id, e)
        return False


async def _log_send(
    client_id: str,
    week_start: date,
    dry_run: bool,
    total_events: int,
    report_text: str,
) -> None:
    """Registra envio em weekly_report_log."""
    try:
        await asyncio.to_thread(
            lambda: supabase.table("weekly_report_log")
            .upsert({
                "client_id": client_id,
                "week_start": week_start.isoformat(),
                "dry_run": dry_run,
                "total_events": total_events,
                "report_text": report_text[:2000],
                "sent_at": datetime.now(timezone.utc).isoformat(),
            }, on_conflict="client_id,week_start")
            .execute()
        )
    except Exception as e:
        logger.warning("[weekly_report] log_send %s: %s", client_id, e)


# ── Analytics ────────────────────────────────────────────────

def _calc_horario_pico(events: list[dict]) -> str:
    """Calcula hora do dia com maior volume de eventos."""
    hour_counts: Counter = Counter()
    for ev in events:
        ts = ev.get("created_at", "")
        if len(ts) >= 13:
            try:
                hour = int(ts[11:13])
                hour_counts[hour] += 1
            except ValueError:
                pass
    if not hour_counts:
        return "não identificado"
    peak_hour = hour_counts.most_common(1)[0][0]
    return f"às {peak_hour}h"


def _calc_variacao(current: int, previous: int) -> str:
    """Calcula variação percentual entre semanas."""
    if previous == 0:
        return "+100%" if current > 0 else "0%"
    pct = ((current - previous) / previous) * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.0f}%"


def _extract_keywords_from_events(events: list[dict], top_n: int = 3) -> list[str]:
    """
    Fallback: extrai top keywords das mensagens nos payloads dos eventos.
    Ignora stopwords e tokens com menos de 4 chars.
    """
    word_counts: Counter = Counter()
    for ev in events:
        payload = ev.get("payload") or {}
        text = ""
        # Tenta extrair texto de campos comuns do payload
        if isinstance(payload, dict):
            text = (
                str(payload.get("message", ""))
                + " " + str(payload.get("text", ""))
                + " " + str(payload.get("content", ""))
            )
        words = re.findall(r"\b[a-záéíóúâêîôûãõàèìòùç]{4,}\b", text.lower())
        for w in words:
            if w not in _STOPWORDS:
                word_counts[w] += 1
    top = word_counts.most_common(top_n)
    return [word.capitalize() for word, _ in top] if top else []


async def _extract_top_topics_haiku(events: list[dict], top_n: int = 3) -> list[str]:
    """
    Usa Claude Haiku para extrair os top temas das mensagens dos clientes.
    Fallback para keyword frequency se Haiku falhar.
    """
    try:
        import anthropic
        all_texts = []
        for ev in events:
            payload = ev.get("payload") or {}
            if isinstance(payload, dict):
                msg = payload.get("message") or payload.get("text") or payload.get("content") or ""
                if msg and len(str(msg).strip()) > 5:
                    all_texts.append(str(msg).strip()[:200])

        if not all_texts:
            return _extract_keywords_from_events(events, top_n)

        # Limitar para não ultrapassar token limit
        sample = all_texts[:50]
        messages_text = "\n".join(f"- {t}" for t in sample)

        prompt = (
            f"Analise as mensagens abaixo de um cliente de atendimento via WhatsApp. "
            f"Identifique os {top_n} temas mais frequentes. "
            f"Retorne apenas os {top_n} temas, um por linha, em português, sem numeração, sem pontuação extra.\n\n"
            f"MENSAGENS:\n{messages_text}"
        )

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = await asyncio.to_thread(
            lambda: client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
            )
        )
        raw = response.content[0].text.strip() if response.content else ""
        topics = [line.strip().capitalize() for line in raw.splitlines() if line.strip()][:top_n]
        return topics if topics else _extract_keywords_from_events(events, top_n)

    except Exception as e:
        logger.warning("[weekly_report] Haiku topic extraction failed: %s", e)
        return _extract_keywords_from_events(events, top_n)


# ── Report generation ────────────────────────────────────────

async def generate_weekly_report(
    client_id: str,
    week_start: Optional[date] = None,
) -> dict:
    """
    Gera o relatório semanal para um cliente.

    Retorna:
      { client_id, business_name, total_events, horario_pico, top_topics,
        variacao, report_text, skipped, skip_reason }
    """
    if week_start is None:
        week_start = _current_week_start()

    iso_start, iso_end = _week_range(week_start)
    prev_start, prev_end = _prev_week_range(week_start)

    # Buscar dados em paralelo
    (client, events, prev_events, health_score) = await asyncio.gather(
        _fetch_zenya_client(client_id),
        _fetch_events(client_id, iso_start, iso_end),
        _fetch_events(client_id, prev_start, prev_end),
        _fetch_health_score(client_id),
    )

    if not client:
        return {"client_id": client_id, "skipped": True, "skip_reason": "cliente não encontrado em zenya_clients"}

    business_name = client.get("business_name") or "você"
    total = len(events)
    prev_total = len(prev_events)

    # AC-5: Pular se health_score crítico
    if health_score is not None and health_score < _CRITICAL_HEALTH_SCORE:
        return {
            "client_id": client_id,
            "business_name": business_name,
            "skipped": True,
            "skip_reason": f"health_score crítico ({health_score:.0f}) — Friday deve alertar Mauro primeiro",
        }

    # AC-1: Dados insuficientes
    if total < _MIN_EVENTS:
        return {
            "client_id": client_id,
            "business_name": business_name,
            "skipped": True,
            "skip_reason": f"dados insuficientes ({total} eventos < {_MIN_EVENTS} mínimo)",
        }

    horario_pico = _calc_horario_pico(events)
    variacao = _calc_variacao(total, prev_total)
    top_topics = await _extract_top_topics_haiku(events, top_n=3)

    # AC-2: Formatar mensagem WhatsApp
    topics_lines = "\n".join(
        f"{i+1}. {t}" for i, t in enumerate(top_topics)
    ) if top_topics else "Não identificados"

    variacao_line = f"*Variação:* {variacao} vs semana anterior"
    if not top_topics:
        topics_section = "🔝 *Temas mais frequentes:*\nDados insuficientes para análise"
    else:
        topics_section = f"🔝 *Temas mais frequentes:*\n{topics_lines}"

    report_text = (
        f"📊 *Relatório semanal da sua Zenya*\n\n"
        f"Oi {business_name}! Aqui está o resumo desta semana:\n\n"
        f"✅ *{total} atendimentos* realizados\n"
        f"⏰ *Horário de pico:* {horario_pico}\n"
        f"📈 {variacao_line}\n\n"
        f"{topics_section}\n\n"
        f"Qualquer dúvida, é só falar! 🚀"
    )

    return {
        "client_id": client_id,
        "business_name": business_name,
        "total_events": total,
        "prev_total_events": prev_total,
        "horario_pico": horario_pico,
        "top_topics": top_topics,
        "variacao": variacao,
        "report_text": report_text,
        "phone_number": client.get("phone_number"),
        "skipped": False,
        "week_start": week_start.isoformat(),
    }


async def send_weekly_report(client_id: str, dry_run: bool = False) -> dict:
    """
    Gera e (opcionalmente) envia o relatório semanal via Z-API.

    Args:
        client_id: ID do cliente
        dry_run: Se True, retorna texto sem enviar

    Returns:
        { sent, dry_run, report, error? }
    """
    week_start = _current_week_start()

    # Anti-spam: verificar se já enviado esta semana
    if not dry_run and await _already_sent_this_week(client_id, week_start):
        return {
            "sent": False,
            "dry_run": dry_run,
            "skipped": True,
            "skip_reason": "relatório já enviado esta semana",
            "client_id": client_id,
        }

    report = await generate_weekly_report(client_id, week_start)

    if report.get("skipped"):
        logger.warning("[CLC] Relatório semanal pulado: %s — %s", client_id, report.get("skip_reason"))
        return {"sent": False, "dry_run": dry_run, "report": report}

    report_text = report["report_text"]
    phone = report.get("phone_number", "")

    if dry_run:
        await _log_send(client_id, week_start, dry_run=True, total_events=report["total_events"], report_text=report_text)
        return {"sent": False, "dry_run": True, "report": report}

    # Envio via Z-API
    if not phone:
        return {"sent": False, "dry_run": False, "error": "phone_number não configurado", "report": report}

    try:
        from runtime.integrations.zapi import send_text
        await asyncio.to_thread(send_text, phone, report_text)
        await _log_send(client_id, week_start, dry_run=False, total_events=report["total_events"], report_text=report_text)
        logger.info(
            "[CLC] Relatório semanal enviado: %s (%s) — %d atendimentos",
            client_id, report.get("business_name"), report["total_events"],
        )
        return {"sent": True, "dry_run": False, "report": report}
    except Exception as e:
        logger.error("[CLC] Falha ao enviar relatório para %s: %s", client_id, e)
        return {"sent": False, "dry_run": False, "error": str(e)[:200], "report": report}


async def send_all_weekly_reports(dry_run: bool = False) -> dict:
    """
    Envia relatórios semanais para todos os clientes Zenya ativos.
    Falha em um cliente não interrompe os demais.

    Returns:
        { total_clients, sent, skipped, failed, results }
    """
    clients = await _fetch_active_zenya_clients()
    if not clients:
        logger.info("[CLC] send_all_weekly_reports: nenhum cliente Zenya ativo encontrado")
        return {"total_clients": 0, "sent": 0, "skipped": 0, "failed": 0, "results": []}

    results = []
    sent = skipped = failed = 0

    for client in clients:
        client_id = client.get("client_id") or str(client.get("id", ""))
        if not client_id:
            continue
        try:
            result = await send_weekly_report(client_id, dry_run=dry_run)
            results.append(result)
            if result.get("sent"):
                sent += 1
            elif result.get("skipped") or result.get("report", {}).get("skipped"):
                skipped += 1
            else:
                failed += 1
        except Exception as e:
            logger.error("[CLC] Erro inesperado para cliente %s: %s", client_id, e)
            results.append({"client_id": client_id, "error": str(e)[:200]})
            failed += 1

    logger.info("[CLC] send_all_weekly_reports: %d total, %d enviados, %d pulados, %d falhos",
                len(clients), sent, skipped, failed)
    return {
        "total_clients": len(clients),
        "sent": sent,
        "skipped": skipped,
        "failed": failed,
        "results": results,
    }
