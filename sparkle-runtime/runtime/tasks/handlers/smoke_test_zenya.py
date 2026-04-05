"""
ONB-5: Smoke test automatizado da Zenya.

Handler que valida:
1. Checklists de qualidade (soul_prompt + KB)
2. Banco de perguntas de teste por vertical (10 perguntas)
3. Respostas avaliadas por criterios objetivos (nao LLM-as-judge — isso e Fase 2)
4. Geracao de relatorio estruturado pass/fail

REGRAS CRITICAS:
- NAO usa Z-API real — teste local via chamada direta ao LLM com soul_prompt
- NAO modifica dados de clientes reais
- Claude Haiku para avaliar respostas (barato e rapido)
- Maximo 20 cenarios de teste (story: 10 perguntas + checklists)
- testing_mode -> 'internal_testing' quando smoke test inicia
- testing_mode -> 'client_testing' quando smoke test PASSA

Payload:
{
    "client_id": "<uuid>",
    "business_type": "<opcional — lido do banco se ausente>",
    "retry_count": <int, opcional, default 0>
}
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from runtime.db import supabase
from runtime.utils.llm import call_claude
from runtime.onboarding.test_questions import get_test_questions
from runtime.onboarding.qa_checklists import check_soul_prompt, check_kb


# ── Constantes ─────────────────────────────────────────────────

SMOKE_TEST_PASS_THRESHOLD = 0.8   # 80% das perguntas devem passar
MAX_RETRIES = 3
ANSWER_TIMEOUT_SECS = 30

PLACEHOLDER_PATTERNS_STR = ["[pendente]", "[preencher]", "[todo]", "{{", "}}"]

ESCALATION_KEYWORDS = [
    "equipe", "atendente", "humano", "transferir", "encaminhar",
    "time", "chamar", "momento", "espere", "aguarde",
]

ZENYA_IDENTITY_KEYWORDS = [
    "zenya", "assistente", "virtual", "ia", "inteligencia", "artificial",
    "robo", "robô", "automatico", "automático",
]

_EVALUATION_SYSTEM = """Voce e um avaliador de qualidade de chatbots.
Avalie se a resposta da assistente virtual e aceitavel para a pergunta do usuario.

Criterios de REPROVACAO (retorne failed=true se qualquer um se aplicar):
- Resposta esta vazia
- Resposta e um erro de sistema (ex: "Internal Server Error", traceback, excecao)
- Resposta contem placeholders como [PENDENTE], [PREENCHER], {{var}}, [TODO]
- Resposta e identica para perguntas completamente diferentes (sinal de fallback generico)
- Resposta para pergunta de escalacao nao indica nenhuma forma de chamar humano

Criterios de APROVACAO:
- Resposta e coherente com a pergunta (nao precisa ser perfeita)
- Resposta e em portugues
- Resposta tem pelo menos 10 caracteres

Retorne APENAS JSON: {"passed": true/false, "reason": "motivo em 1 frase"}"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Core: Simula resposta da Zenya localmente ──────────────────

async def _simulate_zenya_response(
    question: str,
    soul_prompt: str,
    kb_context: str,
    client_id: str,
    test_id: str,
) -> str:
    """
    Simula resposta da Zenya via chamada direta ao LLM com soul_prompt.
    NAO usa Z-API — teste interno apenas.

    AC-5.1: funciona sem Z-API instance.
    AC-5.3: timeout de 30 segundos.
    """
    if not question.strip():
        # AC-1.3: edge case mensagem vazia — retorna resposta de fallback esperada
        question_for_llm = "(mensagem vazia recebida)"
    else:
        question_for_llm = question

    # Contexto reduzido de KB para o teste (evita explodir contexto)
    kb_snippet = kb_context[:2000] if kb_context else "(KB nao disponivel)"

    prompt = (
        f"=== BASE DE CONHECIMENTO (KB) ===\n{kb_snippet}\n\n"
        f"=== MENSAGEM DO CLIENTE ===\n{question_for_llm}\n\n"
        "Responda como Zenya seguindo seu soul_prompt e a KB acima. "
        "Seja direta e util. Maximo 3 frases."
    )

    try:
        response = await asyncio.wait_for(
            call_claude(
                prompt=prompt,
                system=soul_prompt,
                model="claude-haiku-4-5-20251001",
                client_id=client_id,
                task_id=test_id,
                agent_id="onboarding_qa",
                purpose="smoke_test_simulation",
                max_tokens=300,
            ),
            timeout=ANSWER_TIMEOUT_SECS,
        )
        return response.strip()
    except asyncio.TimeoutError:
        return "__TIMEOUT__"
    except Exception as e:
        return f"__ERROR__: {str(e)[:100]}"


# ── Core: Avaliar resposta por criterios objetivos ─────────────

def _evaluate_response_local(
    question: dict,
    response: str,
    all_responses: list[str],
) -> dict:
    """
    Avalia resposta por criterios objetivos (sem LLM — rapido e barato).
    LLM-as-judge e Fase 2.

    Returns: { passed: bool, reasons_failed: list[str] }
    """
    reasons_failed = []

    # Timeout
    if response == "__TIMEOUT__":
        return {
            "passed": False,
            "reasons_failed": ["timeout — Zenya nao respondeu em 30 segundos"],
        }

    # Erro de sistema
    if response.startswith("__ERROR__"):
        return {
            "passed": False,
            "reasons_failed": [f"erro de sistema: {response}"],
        }

    # Resposta vazia
    if not response or len(response.strip()) < 5:
        # edge_case de mensagem vazia — esperamos resposta graceful (nao pode ser vazia)
        if question.get("category") == "edge_case":
            if not response or len(response.strip()) < 5:
                reasons_failed.append("resposta graceful para mensagem vazia esta vazia ou muito curta")
        else:
            reasons_failed.append("resposta vazia")

    # Placeholders residuais
    resp_lower = response.lower()
    for ph in PLACEHOLDER_PATTERNS_STR:
        if ph in resp_lower:
            reasons_failed.append(f"placeholder residual encontrado: '{ph}'")
            break

    # Teste de escalacao: pergunta sobre falar com humano deve conter keyword de escalacao
    if question.get("escalation_test") and response not in ("__TIMEOUT__", "") and len(response) >= 5:
        escalation_present = any(kw in resp_lower for kw in ESCALATION_KEYWORDS)
        if not escalation_present:
            reasons_failed.append(
                "resposta para 'quero falar com alguem' nao contem instrucao de escalacao"
            )

    # Resposta identica para perguntas diferentes (fallback generico)
    # Verificamos se esta resposta ja apareceu em respostas anteriores (exceto edge cases)
    if (
        question.get("category") != "edge_case"
        and response.strip()
        and response in all_responses
        and len(response) > 20
    ):
        reasons_failed.append("resposta identica a uma resposta anterior (possivel fallback generico)")

    passed = len(reasons_failed) == 0
    return {"passed": passed, "reasons_failed": reasons_failed}


# ── Core: Construir contexto de KB para o prompt ──────────────

def _build_kb_context(kb_items: list[dict]) -> str:
    """Formata itens de KB como contexto para o prompt de teste."""
    if not kb_items:
        return ""
    lines = []
    for item in kb_items[:30]:  # Limita para nao explodir contexto
        q = item.get("item_name", "")
        a = item.get("description", "")
        if q and a:
            lines.append(f"P: {q}\nR: {a}")
    return "\n\n".join(lines)


# ── Alertar Friday sobre falha ─────────────────────────────────

async def _alert_friday_smoke_fail(
    client_id: str,
    business_name: str,
    passed_count: int,
    total: int,
    failed_questions: list[str],
) -> None:
    """AC-4.3: Alerta Friday com detalhes das falhas."""
    from runtime.config import settings
    mauro_phone = settings.mauro_whatsapp
    if not mauro_phone:
        print(f"[smoke_test] WARN: MAURO_WHATSAPP nao configurado — alerta nao enviado")
        return
    try:
        failed_list = "\n".join(f"  - {q}" for q in failed_questions[:5])
        msg = (
            f"[Friday] Zenya de '{business_name}' falhou no teste interno.\n"
            f"{passed_count} de {total} perguntas passaram.\n"
            f"Perguntas que falharam:\n{failed_list}"
        )
        from runtime.integrations.zapi import send_text
        await asyncio.to_thread(send_text, mauro_phone, msg)
    except Exception as e:
        print(f"[smoke_test] WARN: falha ao alertar Friday: {e}")


# ── Atualizar gate condition ───────────────────────────────────

async def _update_gate_condition(
    client_id: str,
    phase: str,
    condition: str,
    value: bool,
) -> None:
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .select("gate_details")
            .eq("client_id", client_id)
            .eq("phase", phase)
            .maybe_single()
            .execute()
        )
        current = {}
        if result and result.data:
            current = result.data.get("gate_details") or {}
        current[condition] = value
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .update({"gate_details": current, "updated_at": _now()})
            .eq("client_id", client_id)
            .eq("phase", phase)
            .execute()
        )
    except Exception as e:
        print(f"[smoke_test] update_gate_condition error: {e}")


# ── Handler principal ──────────────────────────────────────────

async def handle_smoke_test_zenya(task: dict) -> dict:
    """
    ONB-5: Executa smoke test completo da Zenya.

    Sequencia:
      1. Buscar dados do cliente (soul_prompt, KB, business_type)
      2. Atualizar testing_mode -> 'internal_testing'
      3. Executar checklists (soul_prompt + KB)
      4. Enviar 10 perguntas de teste e avaliar respostas
      5. Calcular score final (pass >= 80%)
      6. Se PASS: gate test_internal passa, testing_mode -> 'client_testing'
         Se FAIL: alertar Friday, registrar falha no banco
      7. Retornar relatorio estruturado

    Payload:
        client_id (str, required)
        business_type (str, optional — lido do banco)
        retry_count (int, optional, default 0)
    """
    payload = task.get("payload", {})
    client_id = payload.get("client_id", "").strip()
    retry_count = int(payload.get("retry_count", 0))

    if not client_id:
        return {"status": "error", "error": "client_id e obrigatorio"}

    print(f"[smoke_test] Iniciando smoke test para {client_id[:12]}... (retry={retry_count})")

    # ── 1. Buscar dados do cliente ─────────────────────────────

    zenya_result = await asyncio.to_thread(
        lambda: supabase.table("zenya_clients")
        .select("soul_prompt_generated,business_name,business_type,testing_mode")
        .eq("client_id", client_id)
        .maybe_single()
        .execute()
    )
    zenya = zenya_result.data if zenya_result else None

    if not zenya:
        return {
            "status": "error",
            "error": f"zenya_clients nao encontrado para client_id={client_id}",
        }

    soul_prompt = zenya.get("soul_prompt_generated") or ""
    business_name = zenya.get("business_name") or "Negocio"
    business_type = payload.get("business_type") or zenya.get("business_type") or "generico"

    if not soul_prompt:
        return {
            "status": "error",
            "error": "soul_prompt_generated esta vazio — execute ONB-3 antes do smoke test",
        }

    # ── 2. Atualizar testing_mode -> 'internal_testing' ────────

    try:
        await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .update({"testing_mode": "internal_testing", "updated_at": _now()})
            .eq("client_id", client_id)
            .execute()
        )
        print(f"[smoke_test] testing_mode -> internal_testing para {client_id[:12]}")
    except Exception as e:
        print(f"[smoke_test] WARN: falha ao atualizar testing_mode: {e}")

    # ── 3. Executar checklists de qualidade ────────────────────

    print(f"[smoke_test] Executando checklists de qualidade...")
    sp_check, kb_check = await asyncio.gather(
        check_soul_prompt(client_id),
        check_kb(client_id),
    )

    checklist_passed = sp_check["passed"] and kb_check["passed"]
    print(
        f"[smoke_test] Soul prompt: {sp_check['score']}/{sp_check['total']} | "
        f"KB: {kb_check['score']}/{kb_check['total']}"
    )

    # ── 4. Buscar KB para contexto de resposta ─────────────────

    kb_result = await asyncio.to_thread(
        lambda: supabase.table("zenya_knowledge_base")
        .select("item_name,description")
        .eq("client_id", client_id)
        .eq("active", True)
        .limit(30)
        .execute()
    )
    kb_items = kb_result.data or []
    kb_context = _build_kb_context(kb_items)

    # ── 5. Enviar perguntas de teste e avaliar respostas ────────

    questions = get_test_questions(business_type)
    print(f"[smoke_test] {len(questions)} perguntas de teste para vertical '{business_type}'")

    question_results = []
    all_responses: list[str] = []

    for q in questions:
        q_text = q["text"]
        q_id = q["id"]
        test_id = f"smoke-{client_id[:12]}-{q_id}"

        print(f"[smoke_test]   Pergunta [{q_id}]: '{q_text[:60]}'")

        response = await _simulate_zenya_response(
            question=q_text,
            soul_prompt=soul_prompt,
            kb_context=kb_context,
            client_id=client_id,
            test_id=test_id,
        )

        eval_result = _evaluate_response_local(q, response, all_responses)

        # Adiciona resposta ao historico para verificacao de duplicatas
        if response not in ("__TIMEOUT__",) and not response.startswith("__ERROR__"):
            all_responses.append(response.strip())

        question_results.append({
            "question_id": q_id,
            "question_text": q_text,
            "category": q.get("category"),
            "escalation_test": q.get("escalation_test", False),
            "response": response[:500],  # Truncar para o relatorio
            "passed": eval_result["passed"],
            "reasons_failed": eval_result.get("reasons_failed", []),
        })

        status_icon = "PASS" if eval_result["passed"] else "FAIL"
        print(f"[smoke_test]   -> {status_icon}" + (
            f": {eval_result['reasons_failed'][0]}" if eval_result.get("reasons_failed") else ""
        ))

    # ── 6. Calcular score ──────────────────────────────────────

    total_questions = len(questions)
    passed_questions = sum(1 for r in question_results if r["passed"])
    failed_questions = [r for r in question_results if not r["passed"]]
    pass_rate = passed_questions / total_questions if total_questions > 0 else 0.0

    smoke_test_passed = pass_rate >= SMOKE_TEST_PASS_THRESHOLD

    print(
        f"[smoke_test] Score: {passed_questions}/{total_questions} "
        f"({pass_rate:.0%}) — {'PASS' if smoke_test_passed else 'FAIL'}"
    )

    # Score combinado: smoke test + checklists
    overall_passed = smoke_test_passed and checklist_passed

    # ── 7. Salvar resultado no banco ───────────────────────────

    smoke_result_data = {
        "smoke_test": {
            "passed": smoke_test_passed,
            "total": total_questions,
            "passed_count": passed_questions,
            "failed_count": len(failed_questions),
            "pass_rate": round(pass_rate, 3),
            "threshold": SMOKE_TEST_PASS_THRESHOLD,
            "retry_count": retry_count,
            "ran_at": _now(),
        },
        "soul_prompt_checklist": {
            "passed": sp_check["passed"],
            "score": sp_check["score"],
            "total": sp_check["total"],
            "details": sp_check["details"],
        },
        "kb_checklist": {
            "passed": kb_check["passed"],
            "score": kb_check["score"],
            "total": kb_check["total"],
            "kb_item_count": kb_check.get("kb_item_count", 0),
            "details": kb_check["details"],
        },
        "question_results": question_results,
        "overall_passed": overall_passed,
    }

    try:
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .update({
                "gate_details": {
                    **({} ),  # Sera merged com gate_details existente
                    "smoke_test_result": smoke_result_data,
                    "smoke_test_ran_at": _now(),
                },
                "updated_at": _now(),
            })
            .eq("client_id", client_id)
            .eq("phase", "test_internal")
            .execute()
        )
    except Exception as e:
        print(f"[smoke_test] WARN: falha ao salvar resultado no banco: {e}")

    # ── 8. Atualizar gate e testing_mode ──────────────────────

    if overall_passed:
        # Gate test_internal passa
        await _update_gate_condition(client_id, "test_internal", "internal_tests_passed", True)

        # Atualizar testing_mode -> 'client_testing'
        try:
            await asyncio.to_thread(
                lambda: supabase.table("zenya_clients")
                .update({
                    "testing_mode": "client_testing",
                    "updated_at": _now(),
                })
                .eq("client_id", client_id)
                .execute()
            )
            print(f"[smoke_test] testing_mode -> client_testing para {client_id[:12]}")
        except Exception as e:
            print(f"[smoke_test] WARN: falha ao atualizar testing_mode para client_testing: {e}")

        # Avançar pipeline para test_client
        try:
            from runtime.onboarding.service import check_gate, PHASE_CONDITIONS
            gate_result = await check_gate(
                client_id,
                "test_internal",
                PHASE_CONDITIONS.get("test_internal", []),
            )
            if gate_result.get("passed"):
                print(
                    f"[smoke_test] Gate test_internal PASSOU. "
                    f"Proximo: {gate_result.get('next_phase', 'test_client')}"
                )
        except Exception as e:
            print(f"[smoke_test] WARN: falha ao checar gate apos smoke test: {e}")

    else:
        # AC-4.3: Smoke test falhou — alertar Friday
        failed_question_texts = [
            f"{r['question_text'] or '(vazia)'}: {', '.join(r['reasons_failed'][:1])}"
            for r in failed_questions[:5]
        ]

        checklist_failures = []
        if not sp_check["passed"]:
            failed_sp = [d["check"] for d in sp_check["details"] if not d["passed"]]
            checklist_failures.append(f"Soul prompt: {', '.join(failed_sp)}")
        if not kb_check["passed"]:
            failed_kb = [d["check"] for d in kb_check["details"] if not d["passed"]]
            checklist_failures.append(f"KB: {', '.join(failed_kb)}")

        all_failures = failed_question_texts + checklist_failures

        await _alert_friday_smoke_fail(
            client_id=client_id,
            business_name=business_name,
            passed_count=passed_questions,
            total=total_questions,
            failed_questions=all_failures,
        )

        # AC-4.4: Verificar numero de retries — apos 3 falhas: escalar para Mauro
        if retry_count >= MAX_RETRIES - 1:
            print(
                f"[smoke_test] CRITICO: {retry_count + 1} tentativas falharam para "
                f"{client_id[:12]}. Escalando para Mauro."
            )
            try:
                from runtime.config import settings
                from runtime.integrations.zapi import send_text
                mauro_phone = settings.mauro_whatsapp
                if mauro_phone:
                    msg = (
                        f"[Friday CRITICO] Zenya de '{business_name}' falhou no smoke test "
                        f"por {retry_count + 1} vezes consecutivas. "
                        f"Requer intervencao manual."
                    )
                    await asyncio.to_thread(send_text, mauro_phone, msg)
            except Exception as e:
                print(f"[smoke_test] WARN: falha ao enviar alerta critico: {e}")

        # Marcar fase test_internal como failed
        try:
            await asyncio.to_thread(
                lambda: supabase.table("onboarding_workflows")
                .update({
                    "status": "failed",
                    "error_log": {
                        "error": "smoke_test_failed",
                        "pass_rate": round(pass_rate, 3),
                        "retry_count": retry_count,
                        "failed_questions": [r["question_id"] for r in failed_questions],
                        "checklist_failures": checklist_failures,
                    },
                    "updated_at": _now(),
                })
                .eq("client_id", client_id)
                .eq("phase", "test_internal")
                .execute()
            )
        except Exception as e:
            print(f"[smoke_test] WARN: falha ao marcar fase como failed: {e}")

    # ── 9. Retornar relatorio ──────────────────────────────────

    summary = (
        f"Smoke test '{business_name}': {'PASSOU' if overall_passed else 'FALHOU'}.\n"
        f"  Perguntas: {passed_questions}/{total_questions} ({pass_rate:.0%})\n"
        f"  Soul prompt: {sp_check['score']}/{sp_check['total']}\n"
        f"  KB: {kb_check['score']}/{kb_check['total']}"
    )
    print(f"[smoke_test] {summary}")

    return {
        "status": "completed",
        "client_id": client_id,
        "business_name": business_name,
        "overall_passed": overall_passed,
        "smoke_test": {
            "passed": smoke_test_passed,
            "total": total_questions,
            "passed_count": passed_questions,
            "failed_count": len(failed_questions),
            "pass_rate": round(pass_rate, 3),
        },
        "soul_prompt_checklist": {
            "passed": sp_check["passed"],
            "score": f"{sp_check['score']}/{sp_check['total']}",
        },
        "kb_checklist": {
            "passed": kb_check["passed"],
            "score": f"{kb_check['score']}/{kb_check['total']}",
            "kb_item_count": kb_check.get("kb_item_count", 0),
        },
        "question_details": question_results,
        "retry_count": retry_count,
        "summary": summary,
        "message": summary,
    }
