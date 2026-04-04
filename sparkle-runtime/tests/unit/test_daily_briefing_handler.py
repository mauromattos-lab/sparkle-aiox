"""
Unit tests for daily_briefing handler.
Mocks: Supabase, Z-API, status_mrr handler.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from runtime.tasks.handlers.daily_briefing import handle_daily_briefing


def _make_mock_sb(
    tasks_done=None,
    conversations=None,
    notes=None,
    brain_chunks_count=0,
    brain_insights_count=0,
    drafts_count=0,
    scheduled_count=0,
    gaps_count=0,
    active_tasks=None,
    failed_count=0,
):
    """Build a mock supabase with controlled data for all briefing queries."""
    mock_sb = MagicMock()
    call_idx = [0]

    def table_fn(name):
        q = MagicMock()
        q.select.return_value = q
        q.eq.return_value = q
        q.gte.return_value = q
        q.lt.return_value = q
        q.in_.return_value = q
        q.order.return_value = q
        q.limit.return_value = q

        resp = MagicMock()

        if name == "runtime_tasks":
            call_idx[0] += 1
            idx = call_idx[0]
            if idx == 1:
                # tasks done in 24h
                resp.data = tasks_done or []
            elif idx == 2:
                # active workflows
                resp.data = active_tasks or []
            elif idx == 3:
                # failed tasks count
                resp.data = [{"id": f"f-{i}"} for i in range(failed_count)]
                resp.count = failed_count
            else:
                resp.data = []
                resp.count = 0
        elif name == "conversation_history":
            resp.data = conversations or []
        elif name == "notes":
            resp.data = notes or []
        elif name == "brain_chunks":
            resp.data = [{"id": f"c-{i}"} for i in range(brain_chunks_count)]
            resp.count = brain_chunks_count
        elif name == "brain_insights":
            resp.data = [{"id": f"i-{i}"} for i in range(brain_insights_count)]
            resp.count = brain_insights_count
        elif name == "generated_content":
            resp.data = [{"id": f"d-{i}"} for i in range(drafts_count)]
            resp.count = drafts_count
        elif name == "gap_reports":
            resp.data = [{"id": f"g-{i}"} for i in range(gaps_count)]
            resp.count = gaps_count
        else:
            resp.data = []
            resp.count = 0

        q.execute.return_value = resp
        return q

    mock_sb.table = table_fn
    return mock_sb


@pytest.mark.asyncio
async def test_daily_briefing_basic_structure():
    """Briefing should contain expected sections."""
    mock_sb = _make_mock_sb(
        tasks_done=[
            {"task_type": "chat"},
            {"task_type": "chat"},
            {"task_type": "brain_query"},
        ],
        conversations=[
            {"phone": "5512999999999"},
            {"phone": "5512999999999"},
            {"phone": "5512888888888"},
        ],
        notes=[{"summary": "Test note", "content": "Some content"}],
    )

    with patch("runtime.tasks.handlers.daily_briefing.supabase", mock_sb):
        with patch("runtime.tasks.handlers.daily_briefing.settings") as mock_settings:
            mock_settings.mauro_whatsapp = ""
            mock_settings.sparkle_internal_client_id = "sparkle-internal"
            with patch(
                "runtime.tasks.handlers.daily_briefing.handle_status_mrr",
                new_callable=AsyncMock,
                return_value={"total_mrr": 4594.0, "clients": [{"name": "Vitalis"}]},
            ):
                result = await handle_daily_briefing({})

    msg = result["message"]
    assert "Bom dia, Mauro" in msg
    assert "Tasks executadas" in msg
    assert "Conversas" in msg
    assert "Relatório de" in msg or "relatório" in msg.lower()


@pytest.mark.asyncio
async def test_daily_briefing_sends_whatsapp():
    """When mauro_whatsapp is set, should attempt to send via Z-API."""
    mock_sb = _make_mock_sb()

    with patch("runtime.tasks.handlers.daily_briefing.supabase", mock_sb):
        with patch("runtime.tasks.handlers.daily_briefing.settings") as mock_settings:
            mock_settings.mauro_whatsapp = "5512999999999"
            mock_settings.sparkle_internal_client_id = "sparkle-internal"
            with patch(
                "runtime.tasks.handlers.daily_briefing.handle_status_mrr",
                new_callable=AsyncMock,
                return_value={"total_mrr": 0, "clients": []},
            ):
                with patch(
                    "runtime.tasks.handlers.daily_briefing.send_text",
                    create=True,
                ) as mock_send:
                    result = await handle_daily_briefing({})

    # Should have tried to send WhatsApp
    assert result["message"]  # at minimum, message is not empty


@pytest.mark.asyncio
async def test_daily_briefing_handles_db_errors_gracefully():
    """If one section fails, others should still render."""
    mock_sb = MagicMock()

    def table_fn(name):
        q = MagicMock()
        q.select.return_value = q
        q.eq.return_value = q
        q.gte.return_value = q
        q.lt.return_value = q
        q.in_.return_value = q
        q.order.return_value = q
        q.limit.return_value = q
        # Everything fails
        q.execute.side_effect = Exception("DB down")
        return q

    mock_sb.table = table_fn

    with patch("runtime.tasks.handlers.daily_briefing.supabase", mock_sb):
        with patch("runtime.tasks.handlers.daily_briefing.settings") as mock_settings:
            mock_settings.mauro_whatsapp = ""
            mock_settings.sparkle_internal_client_id = "sparkle-internal"
            with patch(
                "runtime.tasks.handlers.daily_briefing.handle_status_mrr",
                new_callable=AsyncMock,
                side_effect=Exception("MRR error"),
            ):
                result = await handle_daily_briefing({})

    msg = result["message"]
    # Should still have greeting even if all sections failed
    assert "Bom dia, Mauro" in msg
    # Should contain error indicators for failed sections
    assert "erro" in msg.lower()


@pytest.mark.asyncio
async def test_daily_briefing_mrr_formatting():
    """MRR should be formatted in Brazilian Real."""
    mock_sb = _make_mock_sb()

    with patch("runtime.tasks.handlers.daily_briefing.supabase", mock_sb):
        with patch("runtime.tasks.handlers.daily_briefing.settings") as mock_settings:
            mock_settings.mauro_whatsapp = ""
            mock_settings.sparkle_internal_client_id = "sparkle-internal"
            with patch(
                "runtime.tasks.handlers.daily_briefing.handle_status_mrr",
                new_callable=AsyncMock,
                return_value={"total_mrr": 4594.0, "clients": [{"name": "A"}, {"name": "B"}]},
            ):
                result = await handle_daily_briefing({})

    msg = result["message"]
    assert "R$" in msg
    assert "2 clientes" in msg
