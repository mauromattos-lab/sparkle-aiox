"""
google_provisioner.py — ONB-1.5b

Provisiona integrações Google para novo cliente:
- Google Drive: cria pasta com estrutura padrão
- Google Calendar: cria/configura calendário com horários do cliente

Requer: GOOGLE_SERVICE_ACCOUNT_JSON no .env (JSON da service account da Sparkle)
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from runtime.db import supabase


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


def _get_google_service() -> Optional[object]:
    """
    Retorna cliente autenticado do Google via service account.
    Retorna None se credenciais ausentes.
    """
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not sa_json:
        return None

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build  # type: ignore

        creds_info = json.loads(sa_json)
        scopes = [
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/calendar",
        ]
        creds = service_account.Credentials.from_service_account_info(
            creds_info, scopes=scopes
        )
        return creds
    except Exception as e:
        print(f"[google_provisioner] credenciais inválidas: {e}")
        return None


def provision_drive(client_id: str, business_name: str, client_email: Optional[str] = None) -> DriveResult:
    """
    Cria estrutura de pastas no Google Drive da Sparkle para o cliente.
    Síncrono — chamar via asyncio.to_thread.
    """
    creds = _get_google_service()
    if creds is None:
        return DriveResult(
            success=False,
            manual_required=True,
            error="GOOGLE_SERVICE_ACCOUNT_JSON ausente — adicionar ao .env para automatizar Drive",
        )

    try:
        from googleapiclient.discovery import build  # type: ignore

        service = build("drive", "v3", credentials=creds)

        # Cria pasta raiz do cliente
        folder_meta = {
            "name": business_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        root = service.files().create(body=folder_meta, fields="id").execute()
        root_id = root["id"]

        # Cria subpastas
        subfolders = ["materiais/fotos", "materiais/docs", "materiais/videos", "contratos"]
        for path in subfolders:
            parts = path.split("/")
            parent_id = root_id
            for part in parts:
                sub = service.files().create(
                    body={
                        "name": part,
                        "mimeType": "application/vnd.google-apps.folder",
                        "parents": [parent_id],
                    },
                    fields="id",
                ).execute()
                parent_id = sub["id"]

        # Compartilha com email do cliente se fornecido
        if client_email:
            service.permissions().create(
                fileId=root_id,
                body={"type": "user", "role": "writer", "emailAddress": client_email},
            ).execute()

        folder_url = f"https://drive.google.com/drive/folders/{root_id}"
        print(f"[google_provisioner] Drive criado para {business_name}: {root_id}")

        return DriveResult(success=True, folder_id=root_id, folder_url=folder_url)

    except Exception as e:
        return DriveResult(
            success=False,
            manual_required=True,
            error=f"Drive creation falhou: {e}",
        )


def provision_calendar(
    client_id: str,
    business_name: str,
    business_hours: Optional[dict] = None,
) -> CalendarResult:
    """
    Cria calendário Google para o cliente com horários de atendimento.
    Síncrono — chamar via asyncio.to_thread.
    """
    creds = _get_google_service()
    if creds is None:
        return CalendarResult(
            success=False,
            manual_required=True,
            error="GOOGLE_SERVICE_ACCOUNT_JSON ausente — Calendar não provisionado",
        )

    try:
        from googleapiclient.discovery import build  # type: ignore

        service = build("calendar", "v3", credentials=creds)
        sa_json = json.loads(os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "{}"))
        account_email = sa_json.get("client_email", "")

        # Cria calendário
        calendar_body = {
            "summary": f"Zenya — {business_name}",
            "description": f"Calendário de atendimento gerenciado pela Sparkle para {business_name}",
            "timeZone": "America/Sao_Paulo",
        }
        calendar = service.calendars().insert(body=calendar_body).execute()
        calendar_id = calendar["id"]

        print(f"[google_provisioner] Calendar criado para {business_name}: {calendar_id}")
        return CalendarResult(
            success=True,
            calendar_id=calendar_id,
            account_email=account_email,
        )

    except Exception as e:
        return CalendarResult(
            success=False,
            manual_required=True,
            error=f"Calendar creation falhou: {e}",
        )


async def provision_google(
    client_id: str,
    business_name: str,
    has_scheduling: bool = False,
    client_email: Optional[str] = None,
    business_hours: Optional[dict] = None,
) -> dict:
    """
    Orquestra Drive + Calendar (se has_scheduling).
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
    drive_result = results[0]
    calendar_result = results[1] if has_scheduling else None

    update_data: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if drive_result.success and drive_result.folder_id:
        update_data["google_drive_folder_id"] = drive_result.folder_id
    if calendar_result and calendar_result.success:
        update_data["google_calendar_id"] = calendar_result.calendar_id
        update_data["google_account_email"] = calendar_result.account_email

    if update_data:
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
            "manual_required": drive_result.manual_required,
            "error": drive_result.error,
        },
        "calendar": {
            "success": calendar_result.success if calendar_result else None,
            "calendar_id": calendar_result.calendar_id if calendar_result else None,
            "skipped": not has_scheduling,
            "manual_required": calendar_result.manual_required if calendar_result else False,
        } if has_scheduling else {"skipped": True},
    }
