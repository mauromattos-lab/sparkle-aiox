"""
google_provisioner.py — ONB-1.5b (v2)

Provisiona integrações Google para novo cliente via n8n webhooks.
Delega Drive e Calendar para workflows n8n que usam OAuth2 da conta Sparkle.

Workflows n8n:
- Drive:    POST https://n8n.sparkleai.tech/webhook/7w4uDx1h3Vf0feUP/webhook/provision-drive
- Calendar: POST https://n8n.sparkleai.tech/webhook/AVbmzj48oOeMeKDi/webhook/provision-calendar

Não requer credenciais Google diretas no Runtime — as OAuth2 estão no n8n.
"""
from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from runtime.db import supabase


# ─── URLs dos webhooks n8n (produção) ────────────────────────────────────────
N8N_DRIVE_WEBHOOK = "https://n8n.sparkleai.tech/webhook/7w4uDx1h3Vf0feUP/webhook/provision-drive"
N8N_CALENDAR_WEBHOOK = "https://n8n.sparkleai.tech/webhook/AVbmzj48oOeMeKDi/webhook/provision-calendar"
WEBHOOK_TIMEOUT = 120  # segundos


@dataclass
class DriveResult:
    success: bool
    folder_id: Optional[str] = None
    folder_url: Optional[str] = None
    manual_required: bool = False
    error: Optional[str] = None


@dataclass
class CalendarResult:
    success: bool
    calendar_id: Optional[str] = None
    account_email: Optional[str] = None
    manual_required: bool = False
    error: Optional[str] = None


def _call_webhook(url: str, payload: dict) -> tuple[Optional[dict], Optional[str]]:
    """
    Chama um webhook n8n via POST. Retorna (response_dict, error_message).
    """
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=WEBHOOK_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data, None
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return None, f"HTTP {e.code}: {err_body}"
    except Exception as e:
        return None, str(e)


def provision_drive(client_id: str, business_name: str, client_email: Optional[str] = None) -> DriveResult:
    """
    Cria estrutura de pastas no Google Drive via webhook n8n.
    Síncrono — chamar via asyncio.to_thread.
    """
    payload: dict = {"business_name": business_name}
    if client_email:
        payload["client_email"] = client_email

    data, err = _call_webhook(N8N_DRIVE_WEBHOOK, payload)

    if err:
        print(f"[google_provisioner] Drive webhook falhou: {err}")
        return DriveResult(success=False, manual_required=True, error=f"Drive webhook falhou: {err}")

    if not data or not data.get("success"):
        error_msg = data.get("error", "Resposta inesperada do webhook Drive") if data else "Sem resposta"
        print(f"[google_provisioner] Drive retornou erro: {error_msg}")
        return DriveResult(success=False, manual_required=True, error=error_msg)

    folder_id = data.get("folder_id", "")
    folder_url = data.get("folder_url", f"https://drive.google.com/drive/folders/{folder_id}")
    print(f"[google_provisioner] Drive criado para {business_name}: {folder_id}")
    return DriveResult(success=True, folder_id=folder_id, folder_url=folder_url)


def provision_calendar(
    client_id: str,
    business_name: str,
    business_hours: Optional[dict] = None,
) -> CalendarResult:
    """
    Cria calendário Google via webhook n8n.
    Síncrono — chamar via asyncio.to_thread.
    """
    payload = {"business_name": business_name, "client_id": client_id}

    data, err = _call_webhook(N8N_CALENDAR_WEBHOOK, payload)

    if err:
        print(f"[google_provisioner] Calendar webhook falhou: {err}")
        return CalendarResult(success=False, manual_required=True, error=f"Calendar webhook falhou: {err}")

    if not data or not data.get("success"):
        error_msg = data.get("error", "Resposta inesperada do webhook Calendar") if data else "Sem resposta"
        print(f"[google_provisioner] Calendar retornou erro: {error_msg}")
        return CalendarResult(success=False, manual_required=True, error=error_msg)

    calendar_id = data.get("calendar_id", "")
    print(f"[google_provisioner] Calendar criado para {business_name}: {calendar_id}")
    return CalendarResult(success=True, calendar_id=calendar_id)


async def provision_google(
    client_id: str,
    business_name: str,
    has_scheduling: bool = False,
    client_email: Optional[str] = None,
    business_hours: Optional[dict] = None,
) -> dict:
    """
    Orquestra Drive + Calendar (se has_scheduling) via webhooks n8n.
    Atualiza zenya_clients com resultados.
    """
    tasks = [
        asyncio.to_thread(provision_drive, client_id, business_name, client_email)
    ]
    if has_scheduling:
        tasks.append(
            asyncio.to_thread(provision_calendar, client_id, business_name, business_hours)
        )

    results = await asyncio.gather(*tasks)
    drive_result: DriveResult = results[0]
    calendar_result: Optional[CalendarResult] = results[1] if has_scheduling else None

    update_data: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if drive_result.success and drive_result.folder_id:
        update_data["google_drive_folder_id"] = drive_result.folder_id
    if calendar_result and calendar_result.success:
        update_data["google_calendar_id"] = calendar_result.calendar_id

    if len(update_data) > 1:  # mais que só updated_at
        try:
            await asyncio.to_thread(
                lambda: supabase.table("zenya_clients")
                .update(update_data)
                .eq("client_id", client_id)
                .execute()
            )
        except Exception as e:
            print(f"[google_provisioner] update zenya_clients falhou: {e}")

    return {
        "drive": {
            "success": drive_result.success,
            "folder_id": drive_result.folder_id,
            "folder_url": drive_result.folder_url,
            "manual_required": drive_result.manual_required,
            "error": drive_result.error,
        },
        "calendar": (
            {
                "success": calendar_result.success,
                "calendar_id": calendar_result.calendar_id,
                "skipped": False,
                "manual_required": calendar_result.manual_required,
                "error": calendar_result.error,
            }
            if calendar_result
            else {"skipped": True}
        ),
    }
