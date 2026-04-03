"""
conclave handler — Deliberação multi-agente paralela.

Quando uma pergunta envolve múltiplos domínios ou requer deliberação de alto nível,
o Conclave aciona 2-4 especialistas em paralelo e sintetiza com Opus.

Casos de uso:
  - Decisão estratégica que envolve negócio + tráfego + conteúdo
  - Análise de cliente com múltiplas dimensões
  - Diagnóstico de problema que pode ter causa em diferentes áreas
  - Planejamento de sprint / próximos passos

Fluxo:
  1. Detecta quais domínios são relevantes para a questão
  2. Chama specialist handlers em paralelo (asyncio.gather)
  3. Cada especialista responde com sua perspectiva + DNA
  4. Opus sintetiza as perspectivas em decisão/recomendação coesa
  5. Resultado marcado como brain_worthy (decisão de alto nível)
"""
from __future__ import annotations

import asyncio
from typing import Optional

from runtime.config import settings
from runtime.utils.llm import call_claude

# Import direto dos handlers especializados (chamada interna, sem task queue)
from runtime.tasks.handlers.specialist_chat import (
    handle_specialist_chat,
    _DOMAIN_PERSONAS,
    _load_domain_dna,
)


# Mapeamento de palavras-chave para domínios relevantes
_DOMAIN_TRIGGERS: dict[str, list[str]] = {
    "trafego_pago": [
        "anúncio", "ads", "meta", "google", "campanha", "tráfego",
        "leads", "cpl", "roas", "criativo", "verba", "investimento",
    ],
    "estrategia": [
        "estratégia", "crescer", "escalar", "posicionamento", "preço",
        "proposta", "cliente", "mercado", "pitch", "decidir", "vale a pena",
        "focar", "prioridade", "próximos passos",
    ],
    "conteudo": [
        "conteúdo", "post", "instagram", "carrossel", "story", "legenda",
        "copywriting", "engajamento", "orgânico", "orgânico",
    ],
    "zenya_config": [
        "zenya", "atendimento", "whatsapp", "chatbot", "fluxo",
        "resposta automática", "bot",
    ],
    "financeiro": [
        "mrr", "faturamento", "receita", "cobrança", "preço",
        "margem", "caixa", "churn",
    ],
}


def _detect_domains(text: str, max_domains: int = 3) -> list[str]:
    """Detecta quais domínios são mais relevantes para a pergunta."""
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for domain, keywords in _DOMAIN_TRIGGERS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[domain] = score
    # Ordena por score, retorna top N
    sorted_domains = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    detected = [d for d, _ in sorted_domains[:max_domains]]
    # Sempre inclui estrategia como âncora se nenhum domínio detectado
    if not detected:
        detected = ["estrategia", "financeiro"]
    return detected


async def _call_specialist(domain: str, task: dict) -> dict:
    """Chama specialist handler para um domínio específico."""
    # Cria task sintético com o domínio forçado
    specialist_task = {
        **task,
        "payload": {
            **task.get("payload", {}),
            "domain": domain,
        },
    }
    try:
        result = await handle_specialist_chat(specialist_task)
        return {"domain": domain, "response": result.get("message", ""), "ok": True}
    except Exception as e:
        print(f"[conclave] especialista {domain} falhou: {e}")
        return {"domain": domain, "response": "", "ok": False, "error": str(e)}


async def handle_conclave(task: dict) -> dict:
    """
    Orquestra deliberação paralela de múltiplos especialistas.
    """
    payload = task.get("payload", {})
    task_id = task.get("id")
    client_id = task.get("client_id") or settings.sparkle_internal_client_id

    original_text: str = payload.get("original_text", "")
    forced_domains: list = payload.get("domains", [])  # permite forçar domínios específicos

    # 1. Detectar domínios relevantes
    domains = forced_domains if forced_domains else _detect_domains(original_text)
    print(f"[conclave] questão: '{original_text[:80]}' | domínios: {domains}")

    # 2. Chamar todos os especialistas em paralelo
    tasks_coros = [_call_specialist(domain, task) for domain in domains]
    specialist_results = await asyncio.gather(*tasks_coros)

    # Filtra só os que responderam com sucesso
    valid_results = [r for r in specialist_results if r["ok"] and r["response"]]

    if not valid_results:
        return {
            "message": "Conclave: nenhum especialista conseguiu responder. Tente novamente.",
            "domains": domains,
            "conclave": True,
        }

    # 3. Se só um especialista respondeu, retorna direto sem síntese
    if len(valid_results) == 1:
        return {
            "message": valid_results[0]["response"],
            "domain": valid_results[0]["domain"],
            "conclave": False,  # degradou para specialist_chat
            "brain_worthy": True,
            "brain_content": (
                f"[Conclave degradado → {valid_results[0]['domain']}]\n"
                f"{valid_results[0]['response']}"
            ),
        }

    # 4. Montar prompt de síntese para Opus
    perspectives_text = ""
    for r in valid_results:
        perspectives_text += f"\n\n### Perspectiva: {r['domain'].upper()}\n{r['response']}"

    synthesis_system = (
        "Você é o Conselho Executivo da Sparkle AIOX — a voz de síntese do Conclave. "
        "Você recebe perspectivas de especialistas diferentes sobre a mesma questão e produz "
        "uma decisão/recomendação coesa, sem contradições, orientada a ação. "
        "Não resuma as perspectivas — sintetize-as em algo mais valioso do que cada uma isolada. "
        "Seja direto. Indique prioridade quando houver conflito. "
        "Formato: recomendação clara → raciocínio → próximos passos numerados."
    )

    synthesis_prompt = (
        f"Questão: {original_text}\n\n"
        f"Perspectivas dos especialistas:{perspectives_text}\n\n"
        "Sintetize em uma decisão/recomendação executiva."
    )

    synthesis = await call_claude(
        prompt=synthesis_prompt,
        system=synthesis_system,
        model="claude-opus-4-5",  # Opus para síntese de alto nível
        client_id=client_id,
        task_id=task_id,
        agent_id="conclave",
        purpose="conclave_synthesis",
        max_tokens=1000,
    )

    domains_used = [r["domain"] for r in valid_results]

    return {
        "message": synthesis,
        "conclave": True,
        "domains_consulted": domains_used,
        "specialists_count": len(valid_results),
        # Decisões do Conclave sempre vão pro Brain
        "brain_worthy": True,
        "brain_content": (
            f"[Conclave — {', '.join(domains_used)}]\n"
            f"Questão: {original_text[:200]}\n\n"
            f"Síntese executiva:\n{synthesis}"
        ),
    }
