"""
gate_check handler — ONB-1: AC-3.x

Verifica se as condicoes do gate de uma fase de onboarding estao satisfeitas.
Se sim: marca fase como completed, avanca para proxima fase.
Se nao: retorna { passed: false, missing: [...] }

Task payload:
{
    "client_id": "uuid",
    "phase": "contract",
    "conditions": ["contract_signed", "payment_confirmed"]  # opcional
}

Se conditions nao for fornecido, usa as condicoes padrao da fase (PHASE_CONDITIONS).
"""
from __future__ import annotations


async def handle_gate_check(task: dict) -> dict:
    """
    AC-3.1/3.2: Gate check handler.

    Verifica condicoes de um gate de onboarding e avanca fase se satisfeitas.
    """
    payload = task.get("payload", {})
    client_id = payload.get("client_id", "").strip()
    phase = payload.get("phase", "").strip()
    conditions = payload.get("conditions")  # optional — None means use defaults

    if not client_id:
        return {"status": "error", "error": "client_id e obrigatorio"}
    if not phase:
        return {"status": "error", "error": "phase e obrigatorio"}

    from runtime.onboarding.service import check_gate, PHASE_CONDITIONS

    # Use provided conditions or fall back to phase defaults
    if conditions is None:
        conditions = PHASE_CONDITIONS.get(phase, [])

    result = await check_gate(client_id, phase, conditions)

    return {
        "status": "ok",
        "task_id": task.get("id"),
        "client_id": client_id,
        "phase": phase,
        **result,
    }
