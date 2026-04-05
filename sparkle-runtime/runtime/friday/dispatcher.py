"""
Friday — Intent dispatcher.
Takes a transcribed message and creates a runtime_task.
Uses Claude Haiku for intent classification (cheap + fast).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.llm import call_claude

logger = logging.getLogger(__name__)

# Intent enum — add new intents here as Friday grows
INTENTS = [
    "status_report",         # "como estão os agentes?", "status", "agentes"
    "status_mrr",            # "qual o MRR?", "faturamento", "quanto tô faturando"
    "chat",                  # conversa livre, perguntas, dúvidas, qualquer coisa não estruturada
    "create_note",           # "anota X", "lembra que Y", "registra Z", "salva isso"
    "activate_agent",        # "ativa o @dev pra fazer X", "chama o arquiteto"
    "weekly_briefing",       # "resumo da semana", "o que rolou essa semana"
    "onboard_client",        # "onborda [nome] site:[url] tipo:[tipo]" — Sprint 8
    "brain_query",           # "brain, o que você sabe sobre X?", "consulta o brain sobre Y"
    "brain_ingest",          # "brain, aprende isso: X", "brain, salva: Y", "registra no brain"
    "loja_integrada_query",  # "consulta pedido", "status do pedido", "meu pedido", "rastrear pedido" — Fun Personalize
    "gap_report",            # "gaps do brain", "o que o brain não sabe", "relatório de gaps"
    "generate_content",      # "gera um post sobre X", "cria carrossel sobre Y", "escreve story"
    "repurpose_audio",       # "transforma esse áudio em post", "usa meu áudio pra criar conteúdo"
    "conclave",              # deliberação multi-agente — pergunta multi-domínio ou decisão complexa
    "echo",                  # teste — retorna o que foi dito
]

# Domain enum — domínios de especialização para roteamento especializado
DOMAINS = [
    "trafego_pago",   # Meta Ads, Google Ads, campanhas, criativos, métricas de anúncios
    "zenya_config",   # configuração de Zenya para cliente, atendimento, fluxo de conversa
    "conteudo",       # Instagram, posts, carrosseis, legendas, stories
    "estrategia",     # proposta comercial, pitch, estratégia de cliente, precificação
    "brain_ops",      # queries ao brain, ingestão, gaps
    "tech",           # código, deploy, infraestrutura, erros técnicos
    "financeiro",     # MRR, faturamento, cobranças, clientes ativos
    "geral",          # padrão quando não se encaixa em nenhum domínio
]

_CLASSIFY_SYSTEM = """Classifique a mensagem do Mauro em uma dessas intencoes: status_report, status_mrr, chat, create_note, activate_agent, weekly_briefing, onboard_client, brain_query, brain_ingest, loja_integrada_query, gap_report, generate_content, repurpose_audio, conclave, echo

REGRAS DE CLASSIFICACAO (intent):
- status_mrr: menciona MRR, faturamento, quanto fatura, receita mensal
- create_note: comeca ou contem "anota", "lembra que", "registra", "salva isso"
- status_report: pergunta sobre agentes, status do sistema, tasks pendentes
- chat: conversa livre, saudacoes, perguntas sobre clientes, duvidas, qualquer outra coisa
- activate_agent: ativa @agente para fazer algo — extrai params: agent (nome do agente com @, ex: "@analyst"), request (a tarefa solicitada, sem o nome do agente)
- weekly_briefing: resumo da semana, o que rolou essa semana
- onboard_client: "onborda", "onboard", "configura zenya para", "cria cliente", "novo cliente zenya" — extrai params: business_name, site_url, business_type, phone
- brain_query: "brain", "o que voce sabe sobre", "consulta o brain", "o que o brain sabe", "brain me fala" — extrai param: query (o que quer saber)
- brain_ingest: "brain, aprende", "brain, salva", "brain, registra", "ensina o brain", "adiciona ao brain", "aprende isso", "precisamos aprender isso", "coloca no brain", "joga no brain", "ingere isso", "absorve isso" — extrai param: content (o conteudo a salvar)
- loja_integrada_query: "consulta pedido", "status do pedido", "meu pedido", "rastrear pedido", "onde esta meu pedido", "situacao do pedido", "acompanhar pedido" — extrai params: cpf, email ou pedido_id conforme disponivel no texto
- gap_report: "gaps do brain", "o que o brain nao sabe", "relatorio de gaps", "brain tem gaps", "quais gaps do brain", "o que falta no brain", "lacunas do brain"
- generate_content: "gera um post", "cria um carrossel", "escreve uma legenda", "faz um story", "cria conteudo sobre", "gera conteudo para instagram" — extrai params: topic, format (instagram_post|carousel|story|thread), persona (zenya|finch|mauro)
- repurpose_audio: "transforma em post", "usa esse audio", "faz um post desse audio", "repurpose", "transforma meu audio em conteudo" — para quando o audio foi transcrito e deve virar conteudo
- conclave: pergunta que envolve multiplos dominios simultaneamente, decisao estrategica complexa, "o que devo fazer com X considerando Y e Z", analise completa de situacao, planejamento de proximos passos amplo, quando a pergunta cruzar trafego+conteudo, negocio+estrategia, financeiro+crescimento ou qualquer combinacao de 2+ dominios distintos
- echo: apenas para testes com a palavra "echo"

CLASSIFICACAO DE DOMINIO (domain) — classifique SEMPRE, mesmo quando intent != chat:
- trafego_pago: Meta Ads, Google Ads, campanhas, criativos, metricas de anuncios, ROI, CPM, CTR, ROAS, trafego pago
- zenya_config: configuracao de Zenya, atendimento automatizado, fluxo de conversa, bot de whatsapp para cliente
- conteudo: Instagram, posts, carrosseis, legendas, stories, reels, criacao de conteudo para redes sociais
- estrategia: proposta comercial, pitch, estrategia de cliente, precificacao, posicionamento, plano de acao
- brain_ops: queries ao brain, ingestao, gaps, o que o brain sabe
- tech: codigo, deploy, infraestrutura, erros tecnicos, API, banco de dados, servidor
- financeiro: MRR, faturamento, cobrancas, clientes ativos, fluxo de caixa, mensalidade
- geral: padrao quando nao se encaixa claramente em nenhum dominio acima (saudacoes, perguntas genéricas)

IMPORTANTE: Responda APENAS com JSON valido, sem blocos de codigo, sem markdown.
Formato: {"intent": "<intent>", "domain": "<domain>", "params": {}, "summary": "<1 linha resumindo o pedido>"}

Para onboard_client, extraia params do texto:
{"intent": "onboard_client", "domain": "zenya_config", "params": {"business_name": "X", "site_url": "url", "business_type": "tipo", "phone": "55..."}, "summary": "Onboarding X"}

Para brain_query, extraia params do texto:
{"intent": "brain_query", "domain": "brain_ops", "params": {"query": "o que o usuário quer saber"}, "summary": "Brain query: <tema>"}

Para brain_ingest, extraia params do texto:
{"intent": "brain_ingest", "domain": "brain_ops", "params": {"content": "o conteúdo a salvar"}, "summary": "Brain ingest: <tema>"}

Para loja_integrada_query, extraia params do texto (apenas os que estiverem presentes):
{"intent": "loja_integrada_query", "domain": "tech", "params": {"cpf": "XXX.XXX.XXX-XX", "email": "x@x.com", "pedido_id": "12345"}, "summary": "Consulta pedido: <identificador>"}

Para generate_content, extraia params do texto:
{"intent": "generate_content", "domain": "conteudo", "params": {"topic": "tema do conteudo", "format": "instagram_post", "persona": "zenya"}, "summary": "Gera post: <tema>"}

Para activate_agent, extraia params do texto:
{"intent": "activate_agent", "domain": "tech", "params": {"agent": "@analyst", "request": "analisar desempenho do cliente Vitalis"}, "summary": "Ativar @analyst: analise Vitalis"}"""


import re as _re

_URL_PATTERN = _re.compile(
    r'https?://[^\s<>"\']+|(?:www\.)[^\s<>"\']+',
    _re.IGNORECASE,
)


def _detect_url(text: str) -> str | None:
    """Retorna a primeira URL encontrada no texto, ou None."""
    match = _URL_PATTERN.search(text)
    return match.group(0) if match else None


def _is_youtube(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url


async def _handle_url_ingest(text: str, url: str, from_number: str) -> dict:
    """Cria task brain_ingest_pipeline para URL detectada na mensagem."""
    source_type = "youtube" if _is_youtube(url) else "url"

    # Texto extra alem da URL pode ser titulo/contexto
    extra_text = text.replace(url, "").strip()
    title = extra_text[:100] if extra_text else ""

    task = await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks").insert({
            "agent_id": "friday",
            "client_id": settings.sparkle_internal_client_id,
            "task_type": "brain_ingest_pipeline",
            "payload": {
                "source_ref": url,
                "source_type": source_type,
                "title": title or f"Ingestao via Friday: {url[:80]}",
                "persona": "especialista",
                "run_dna": False,
                "run_insights": True,
                "run_narrative": False,
                "run_synthesis": True,
                "from_number": from_number,
            },
            "status": "pending",
            "priority": 7,
        }).execute()
    )
    return task.data[0] if task.data else {}


async def _handle_gap_approval(text: str) -> dict | None:
    """
    Detecta se Mauro esta aprovando/rejeitando gaps do Observer.
    Retorna None se nao eh uma resposta de gap.
    """
    text_lower = text.lower().strip()

    if "aprova todos" in text_lower or "approve all" in text_lower:
        try:
            result = await asyncio.to_thread(
                lambda: supabase.table("gap_reports")
                .select("id")
                .eq("status", "pending")
                .execute()
            )
            gaps = result.data or []
            now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            for gap in gaps:
                await asyncio.to_thread(
                    lambda gid=gap["id"]: supabase.table("gap_reports")
                    .update({"status": "approved", "approved_by": "mauro", "approved_at": now, "updated_at": now})
                    .eq("id", gid)
                    .execute()
                )
                await asyncio.to_thread(
                    lambda gid=gap["id"]: supabase.table("runtime_tasks").insert({
                        "agent_id": "system",
                        "client_id": settings.sparkle_internal_client_id,
                        "task_type": "auto_implement_gap",
                        "payload": {"gap_id": gid},
                        "status": "pending",
                        "priority": 6,
                    }).execute()
                )
            return {"message": f"{len(gaps)} gaps aprovados e agendados para implementacao"}
        except Exception as e:
            return {"error": f"Falha ao aprovar gaps: {e}"}

    match = _re.search(r"aprova\s+([\d,\s]+)", text_lower)
    if match:
        indices = [int(x.strip()) for x in match.group(1).split(",") if x.strip().isdigit()]
        try:
            result = await asyncio.to_thread(
                lambda: supabase.table("gap_reports")
                .select("id")
                .eq("status", "pending")
                .order("created_at")
                .execute()
            )
            gaps = result.data or []
            now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            approved = 0
            for idx in indices:
                if 1 <= idx <= len(gaps):
                    gid = gaps[idx - 1]["id"]
                    await asyncio.to_thread(
                        lambda g=gid: supabase.table("gap_reports")
                        .update({"status": "approved", "approved_by": "mauro", "approved_at": now, "updated_at": now})
                        .eq("id", g)
                        .execute()
                    )
                    await asyncio.to_thread(
                        lambda g=gid: supabase.table("runtime_tasks").insert({
                            "agent_id": "system",
                            "client_id": settings.sparkle_internal_client_id,
                            "task_type": "auto_implement_gap",
                            "payload": {"gap_id": g},
                            "status": "pending",
                            "priority": 6,
                        }).execute()
                    )
                    approved += 1
            return {"message": f"{approved} gaps aprovados"}
        except Exception as e:
            return {"error": f"Falha ao aprovar gaps: {e}"}

    match = _re.search(r"rejeita\s+([\d,\s]+)", text_lower)
    if match:
        indices = [int(x.strip()) for x in match.group(1).split(",") if x.strip().isdigit()]
        try:
            result = await asyncio.to_thread(
                lambda: supabase.table("gap_reports")
                .select("id")
                .eq("status", "pending")
                .order("created_at")
                .execute()
            )
            gaps = result.data or []
            now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            rejected = 0
            for idx in indices:
                if 1 <= idx <= len(gaps):
                    gid = gaps[idx - 1]["id"]
                    await asyncio.to_thread(
                        lambda g=gid: supabase.table("gap_reports")
                        .update({"status": "rejected", "updated_at": now})
                        .eq("id", g)
                        .execute()
                    )
                    rejected += 1
            return {"message": f"{rejected} gaps rejeitados"}
        except Exception as e:
            return {"error": f"Falha ao rejeitar gaps: {e}"}

    return None


# ── C2-B1: Auto-ingest noise filter + fire-and-forget ──────────────────────

# Intents that should NOT be auto-ingested (noise)
_SKIP_INGEST_INTENTS = frozenset({"echo", "chat"})

# Minimum word count for casual messages to be worth ingesting
_MIN_WORDS_FOR_INGEST = 10


def _should_auto_ingest(text: str, intent: str) -> bool:
    """Determine if a transcribed message should be auto-ingested into the brain.

    Returns False for:
      - echo intent (test messages)
      - chat intent with fewer than _MIN_WORDS_FOR_INGEST words
      - Very short messages regardless of intent
    """
    if intent == "echo":
        return False

    word_count = len(text.split())

    # Short casual chat — not worth storing
    if intent == "chat" and word_count < _MIN_WORDS_FOR_INGEST:
        return False

    # Very short messages in general — likely greetings
    if word_count < 5:
        return False

    return True


async def _fire_auto_ingest(text: str, intent: str) -> None:
    """Fire-and-forget: ingest transcribed audio into mauro-personal namespace.

    This MUST be non-blocking. All errors are caught and logged.
    Never delays Friday's response to Mauro.
    """
    try:
        task_record = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "friday",
                "client_id": settings.sparkle_internal_client_id,
                "task_type": "brain_ingest",
                "payload": {
                    "content": text,
                    "source_agent": "mauro",
                    "ingest_type": "mauro_audio",
                    "target_namespace": "mauro-personal",
                    "metadata": {
                        "source": "friday-audio",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "intent": intent,
                    },
                },
                "status": "pending",
                "priority": 2,  # low priority — never compete with Friday response
            }).execute()
        )
        record = task_record.data[0] if task_record.data else {}
        if record:
            from runtime.tasks.worker import execute_task
            asyncio.create_task(execute_task(record))
        logger.info("[friday/auto-ingest] queued brain_ingest for mauro-personal (intent=%s)", intent)
    except Exception as e:
        # Never let auto-ingest errors propagate — Friday response must not be affected
        logger.error("[friday/auto-ingest] failed to queue brain_ingest: %s", e)


async def classify_and_dispatch(
    text: str,
    from_number: str = "",
    task_id: Optional[str] = None,
    from_audio: bool = False,
) -> dict:
    """
    Classify intent from text and insert a runtime_task.
    Returns the created task record.
    from_audio=True: sinaliza que a mensagem veio de transcrição de voz.
    """
    # Brain ingest detection: frases explicitas de ingestao
    _BRAIN_INGEST_TRIGGERS = (
        "brain, aprende", "brain, salva", "brain, registra",
        "ensina o brain", "adiciona ao brain", "aprende isso",
        "precisamos aprender isso", "coloca no brain", "joga no brain",
        "joga isso no brain", "ingere isso", "absorve isso",
        "brain aprende", "salva no brain", "registra no brain",
    )
    text_lower = text.lower().strip()
    for trigger in _BRAIN_INGEST_TRIGGERS:
        if text_lower.startswith(trigger):
            # Remove o trigger do inicio pra pegar so o conteudo
            content = text[len(trigger):].lstrip(":").strip()
            if not content or len(content) < 10:
                break

            # Se o conteudo e uma URL, roteia para pipeline com source_ref
            content_url = _detect_url(content)
            if content_url:
                ingest_task = await _handle_url_ingest(text, content_url, from_number)
                from runtime.tasks.worker import execute_task
                asyncio.create_task(execute_task(ingest_task))
                source_label = "video do YouTube" if _is_youtube(content_url) else "link"
                ack_msg = f"Recebi o {source_label}! Tô processando e jogando no Brain. Quando terminar, esse conhecimento já vai estar disponível pro sistema todo."
                ack_task = await asyncio.to_thread(
                    lambda: supabase.table("runtime_tasks").insert({
                        "agent_id": "friday",
                        "client_id": settings.sparkle_internal_client_id,
                        "task_type": "chat",
                        "payload": {"original_text": text[:200], "url_detected": content_url},
                        "status": "done",
                        "result": {"message": ack_msg, "ingest_task_id": ingest_task.get("id")},
                        "priority": 7,
                    }).execute()
                )
                return ack_task.data[0] if ack_task.data else {"status": "done", "result": {"message": ack_msg}}

            # Texto longo → pipeline completa com insights
            if len(content) > 200:
                task_type = "brain_ingest_pipeline"
            else:
                task_type = "brain_ingest"

            payload: dict = {
                "original_text": text,
                "from_number": from_number,
            }
            if task_type == "brain_ingest_pipeline":
                payload["raw_content"] = content
                payload["source_type"] = "direct_input"
                payload["title"] = f"Friday ingest: {content[:60]}"
                payload["persona"] = "especialista"
                payload["run_dna"] = False
                payload["run_insights"] = True
                payload["run_narrative"] = False
                payload["run_synthesis"] = True
            else:
                payload["content"] = content
                payload["ingest_type"] = "manual"
                payload["source_agent"] = "mauro"

            ingest_task = await asyncio.to_thread(
                lambda: supabase.table("runtime_tasks").insert({
                    "agent_id": "friday",
                    "client_id": settings.sparkle_internal_client_id,
                    "task_type": task_type,
                    "payload": payload,
                    "status": "pending",
                    "priority": 7,
                }).execute()
            )
            ingest_record = ingest_task.data[0] if ingest_task.data else {}
            # Executa em background — Friday responde imediatamente
            from runtime.tasks.worker import execute_task
            asyncio.create_task(execute_task(ingest_record))
            word_count = len(content.split())
            ack_msg = f"Recebi! Tô jogando no Brain ({word_count} palavras). Vou extrair os insights e quando terminar, esse conhecimento fica disponível pro sistema todo."
            ack_task = await asyncio.to_thread(
                lambda: supabase.table("runtime_tasks").insert({
                    "agent_id": "friday",
                    "client_id": settings.sparkle_internal_client_id,
                    "task_type": "chat",
                    "payload": {"original_text": text[:200], "brain_ingest_triggered": True},
                    "status": "done",
                    "result": {"message": ack_msg, "ingest_task_id": ingest_record.get("id")},
                    "priority": 7,
                }).execute()
            )
            return ack_task.data[0] if ack_task.data else {"status": "done", "result": {"message": ack_msg}}

    # URL detection: se a mensagem contem URL, roteia para brain_ingest_pipeline
    detected_url = _detect_url(text)
    if detected_url:
        ingest_task = await _handle_url_ingest(text, detected_url, from_number)
        # Executa pipeline em background — Friday responde imediatamente
        from runtime.tasks.worker import execute_task
        asyncio.create_task(execute_task(ingest_task))
        # Retorna task com status done e mensagem amigavel (nao espera pipeline)
        source_label = "video do YouTube" if _is_youtube(detected_url) else "link"
        ack_msg = f"Recebi o {source_label}! Tô processando e jogando no Brain. Quando terminar, esse conhecimento já vai estar disponível pro sistema todo."
        ack_task = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "friday",
                "client_id": settings.sparkle_internal_client_id,
                "task_type": "chat",
                "payload": {"original_text": text, "url_detected": detected_url},
                "status": "done",
                "result": {"message": ack_msg, "ingest_task_id": ingest_task.get("id")},
                "priority": 7,
            }).execute()
        )
        return ack_task.data[0] if ack_task.data else {"status": "done", "result": {"message": ack_msg}}

    # SYS-5: check gap approval before normal classification
    gap_result = await _handle_gap_approval(text)
    if gap_result is not None:
        # Create a task record for the gap approval response
        task = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "friday",
                "client_id": settings.sparkle_internal_client_id,
                "task_type": "chat",
                "payload": {"original_text": text, "gap_approval": gap_result},
                "status": "done",
                "result": gap_result,
                "priority": 7,
            }).execute()
        )
        return task.data[0] if task.data else gap_result

    raw = await call_claude(
        prompt=text,
        system=_CLASSIFY_SYSTEM,
        model="claude-haiku-4-5-20251001",
        client_id=settings.sparkle_internal_client_id,
        task_id=task_id,
        agent_id="friday",
        purpose="friday_intent_classify",
        max_tokens=256,
    )

    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = {"intent": "chat", "params": {}, "summary": text[:200]}

    intent: str = parsed.get("intent", "chat")
    domain: str = parsed.get("domain", "geral")
    params: dict = parsed.get("params", {})
    summary: str = parsed.get("summary", text[:200])

    if intent not in INTENTS and intent != "brain_ingest_pipeline":
        intent = "chat"
    if domain not in DOMAINS:
        domain = "geral"

    task_payload = {
        "original_text": text,
        "intent": intent,
        "domain": domain,
        "params": params,
        "summary": summary,
        "from_number": from_number,
    }

    if intent == "activate_agent" and params:
        if params.get("agent"):
            task_payload["agent"] = params["agent"]
        if params.get("request"):
            task_payload["request"] = params["request"]

    if intent == "onboard_client" and params:
        task_payload.update(params)

    if intent == "brain_query" and params.get("query"):
        task_payload["query"] = params["query"]

    if intent == "brain_ingest" and params.get("content"):
        content = params["content"]
        task_payload["content"] = content
        if from_audio:
            task_payload["ingest_type"] = "mauro_audio"
            task_payload["source_agent"] = "mauro"
        # Textos longos (200+ chars) vao pela pipeline completa com insight extraction
        if len(content) > 200:
            intent = "brain_ingest_pipeline"
            task_payload["raw_content"] = content
            task_payload["source_type"] = "direct_input"
            task_payload["persona"] = "especialista"
            task_payload["run_dna"] = False
            task_payload["run_insights"] = True
            task_payload["run_narrative"] = False
            task_payload["run_synthesis"] = True

    if intent == "loja_integrada_query" and params:
        # Promover cpf / email / pedido_id para o topo do payload
        for key in ("cpf", "email", "pedido_id"):
            if params.get(key):
                task_payload[key] = params[key]

    if intent == "generate_content" and params:
        task_payload["topic"] = params.get("topic") or text[:300]
        task_payload["format"] = params.get("format", "instagram_post")
        task_payload["persona"] = params.get("persona", "zenya")
        task_payload["source_type"] = "manual"

    if intent == "repurpose_audio":
        # Áudio transcrito → gerar post (source_type=repurpose_audio)
        task_payload["topic"] = text[:300]
        task_payload["format"] = params.get("format", "instagram_post")
        task_payload["persona"] = params.get("persona", "mauro")
        task_payload["source_type"] = "repurpose_audio"
        # Redireciona para generate_content handler
        intent = "generate_content"

    # Roteamento especializado: chat + domínio específico → specialist_chat
    task_type = intent
    if intent == "chat" and domain not in ("geral", ""):
        task_type = "specialist_chat"

    # C2-B1: Auto-ingest transcribed audio into mauro-personal namespace
    # Fire-and-forget — never blocks Friday's response
    if from_audio and _should_auto_ingest(text, intent):
        asyncio.create_task(_fire_auto_ingest(text, intent))

    task = await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks").insert({
            "agent_id": "friday",
            "client_id": settings.sparkle_internal_client_id,
            "task_type": task_type,
            "payload": task_payload,
            "status": "pending",
            "priority": 7,
        }).execute()
    )

    return task.data[0] if task.data else {}
