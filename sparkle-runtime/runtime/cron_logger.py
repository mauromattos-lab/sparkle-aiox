"""
Instrumentação de crons — decorator log_cron.

Uso:
    @log_cron("brain_curate_02h")
    async def _run_brain_curate_02h() -> None:
        await _run_and_execute("brain_curate", priority=4)

    # Para funções com múltiplos job_ids (inline no add_job):
    _scheduler.add_job(
        log_cron("brain_curate_10h")(_run_brain_curate),
        ...
    )

Contrato:
- Registra linha em cron_executions com status='running' antes de chamar a função.
- Atualiza a linha com status='success' ou 'error' ao terminar.
- NUNCA suprime exceções — re-raise após logar o erro.
- NUNCA modifica o comportamento da função decorada.
- Se Supabase estiver offline, a função executa mesmo assim (logging nunca bloqueia).
"""
from __future__ import annotations

import asyncio
import functools
import time
import traceback
from typing import Any, Callable, Coroutine, Optional


def log_cron(cron_name: str) -> Callable:
    """
    Decorator assíncrono que envolve um job de cron com logging persistente.

    Args:
        cron_name: identificador único do job (deve bater com o job_id do APScheduler,
                   ex: "health_check", "brain_curate_02h")

    Returns:
        Decorator aplicável em qualquer ``async def`` sem argumentos.

    Behavior:
        1. INSERT cron_executions com status='running', started_at=now
        2. Executa a função original
        3. UPDATE status='success', finished_at=now, duration_ms=elapsed
        4. Em exceção: UPDATE status='error', error=str(exc), re-raise
        5. Se o INSERT falhar (ex: Supabase offline): executa a função mesmo assim,
           loga via print — logging nunca bloqueia execução.
    """
    def decorator(func: Callable[[], Coroutine[Any, Any, None]]) -> Callable[[], Coroutine[Any, Any, None]]:
        @functools.wraps(func)
        async def wrapper() -> None:
            # Import local para evitar acoplamento circular no module-level
            from runtime.db import supabase

            execution_id: Optional[str] = None
            started_ms = time.monotonic()

            # ── 1. INSERT status='running' ──────────────────────
            try:
                res = await asyncio.to_thread(
                    lambda: supabase.table("cron_executions").insert({
                        "cron_name": cron_name,
                        "status": "running",
                    }).execute()
                )
                if res.data:
                    execution_id = res.data[0].get("id")
            except Exception as insert_err:
                print(f"[cron_logger] WARN: INSERT falhou para {cron_name} — {insert_err} — executando cron mesmo assim")

            # ── 2. Executa a função original ────────────────────
            exc_to_raise: Optional[BaseException] = None
            try:
                await func()
            except Exception as e:
                exc_to_raise = e

            # ── 3. UPDATE status='success' ou 'error' ──────────
            elapsed_ms = int((time.monotonic() - started_ms) * 1000)

            if execution_id:
                try:
                    if exc_to_raise is None:
                        payload = {
                            "status": "success",
                            "finished_at": _now_iso(),
                            "duration_ms": elapsed_ms,
                        }
                    else:
                        payload = {
                            "status": "error",
                            "finished_at": _now_iso(),
                            "duration_ms": elapsed_ms,
                            "error": _format_error(exc_to_raise),
                        }
                    await asyncio.to_thread(
                        lambda p=payload: supabase.table("cron_executions")
                        .update(p)
                        .eq("id", execution_id)
                        .execute()
                    )
                except Exception as update_err:
                    print(f"[cron_logger] WARN: UPDATE falhou para {cron_name} id={execution_id} — {update_err}")
            else:
                # INSERT havia falhado — apenas log local
                status_str = "error" if exc_to_raise else "success"
                print(f"[cron_logger] {cron_name} {status_str} em {elapsed_ms}ms (sem persistência)")

            # ── 4. Re-raise se houve exceção ────────────────────
            if exc_to_raise is not None:
                raise exc_to_raise

        return wrapper
    return decorator


# ── Helpers internos ────────────────────────────────────────

def _now_iso() -> str:
    """Retorna timestamp UTC atual em ISO 8601."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _format_error(exc: BaseException) -> str:
    """Formata exceção para armazenamento — inclui tipo e primeiros 1000 chars do traceback."""
    tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
    full = "".join(tb)
    return full[:1000]
