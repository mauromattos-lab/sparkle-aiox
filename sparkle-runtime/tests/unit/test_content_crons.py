"""
Unit tests for Content Engine Crons (CONTENT-1.12).

Tests:
- content_pipeline_tick: advances pieces in generating states
- content_publisher_tick: publishes scheduled pieces whose slot has arrived
- content_brain_sync: ingests published pieces without brain_chunk_id
- register_content_jobs: registers all 3 jobs on the scheduler
- AC4: one piece error doesn't stop others
- Friday notification (pending_approval, publish_failed)

All external dependencies are mocked.
Run: pytest tests/unit/test_content_crons.py -v
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest


# ══════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════

PAST_ISO = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
FUTURE_ISO = (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()


def _make_piece(piece_id="test-piece-001", status="scheduled", **kwargs) -> dict:
    return {
        "id": piece_id,
        "status": status,
        "video_url": "https://storage.supabase.co/video.mp4",
        "final_url": None,
        "caption": "Test #zenya",
        "theme": "IA para PMEs",
        "pipeline_log": [],
        "brain_chunk_id": None,
        "scheduled_at": PAST_ISO,
        **kwargs,
    }


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "fake-key")
    monkeypatch.setenv("MAURO_WHATSAPP", "5512999999999")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "fake-token")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "12345678")


def _make_sb_mock(data: list):
    """Create a mock supabase that returns given data on execute()."""
    mock_sb = MagicMock()
    mock_q = MagicMock()
    mock_q.select.return_value = mock_q
    mock_q.eq.return_value = mock_q
    mock_q.is_.return_value = mock_q
    mock_q.lte.return_value = mock_q
    mock_q.gte.return_value = mock_q
    mock_q.in_.return_value = mock_q
    mock_q.limit.return_value = mock_q
    mock_q.order.return_value = mock_q
    mock_q.update.return_value = mock_q
    mock_q.insert.return_value = mock_q
    mock_q.execute.return_value = MagicMock(data=data, count=len(data))
    mock_sb.table.return_value = mock_q
    mock_sb.rpc.return_value = mock_q
    return mock_sb


# ══════════════════════════════════════════════════════════════
# content_pipeline_tick tests (AC1, AC4)
# ══════════════════════════════════════════════════════════════

class TestContentPipelineTick:
    @pytest.mark.asyncio
    async def test_calls_advance_pipeline_for_each_piece(self):
        """AC1: should call advance_pipeline for each piece in generating states."""
        pieces = [
            _make_piece("piece-001", status="image_generating"),
            _make_piece("piece-002", status="video_generating"),
        ]
        mock_advance = AsyncMock()
        mock_sb = _make_sb_mock(pieces)

        with patch("runtime.db.supabase", mock_sb), \
             patch("runtime.content.pipeline.advance_pipeline", mock_advance):
            # Re-import to get fresh module after patches
            import importlib, runtime.crons.content as cron_mod
            importlib.reload(cron_mod)
            await cron_mod._run_content_pipeline_tick()

        assert mock_advance.call_count == 2

    @pytest.mark.asyncio
    async def test_ac4_one_error_does_not_stop_others(self):
        """AC4: If advance_pipeline fails for one piece, others still run."""
        pieces = [
            _make_piece("piece-001", status="image_generating"),
            _make_piece("piece-002", status="video_generating"),
            _make_piece("piece-003", status="image_generating"),
        ]
        call_counts = [0]

        async def fake_advance(piece):
            call_counts[0] += 1
            if piece["id"] == "piece-002":
                raise RuntimeError("Simulated error")

        mock_sb = _make_sb_mock(pieces)

        with patch("runtime.db.supabase", mock_sb), \
             patch("runtime.content.pipeline.advance_pipeline", side_effect=fake_advance):
            import importlib, runtime.crons.content as cron_mod
            importlib.reload(cron_mod)
            await cron_mod._run_content_pipeline_tick()

        assert call_counts[0] == 3, f"Expected 3 calls, got {call_counts[0]}"

    @pytest.mark.asyncio
    async def test_no_pieces_does_nothing(self):
        """When no pieces in generating states, no advance_pipeline calls made."""
        mock_advance = AsyncMock()
        mock_sb = _make_sb_mock([])

        with patch("runtime.db.supabase", mock_sb), \
             patch("runtime.content.pipeline.advance_pipeline", mock_advance):
            import importlib, runtime.crons.content as cron_mod
            importlib.reload(cron_mod)
            await cron_mod._run_content_pipeline_tick()

        mock_advance.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_error_is_handled_gracefully(self):
        """DB failure in pipeline_tick should not propagate as exception."""
        mock_sb = MagicMock()
        mock_sb.table.side_effect = Exception("DB offline")

        with patch("runtime.db.supabase", mock_sb):
            import importlib, runtime.crons.content as cron_mod
            importlib.reload(cron_mod)
            # Should not raise
            await cron_mod._run_content_pipeline_tick()


# ══════════════════════════════════════════════════════════════
# content_publisher_tick tests (AC2, AC4)
# ══════════════════════════════════════════════════════════════

class TestContentPublisherTick:
    @pytest.mark.asyncio
    async def test_publishes_due_pieces(self):
        """AC2: Pieces with scheduled_at <= now and status=scheduled get published."""
        pieces = [
            _make_piece("piece-001", status="scheduled", scheduled_at=PAST_ISO),
            _make_piece("piece-002", status="scheduled", scheduled_at=PAST_ISO),
        ]
        mock_publish = AsyncMock()
        mock_sb = _make_sb_mock(pieces)

        with patch("runtime.db.supabase", mock_sb), \
             patch("runtime.content.publisher.publish", mock_publish):
            import importlib, runtime.crons.content as cron_mod
            importlib.reload(cron_mod)
            await cron_mod._run_content_publisher_tick()

        assert mock_publish.call_count == 2

    @pytest.mark.asyncio
    async def test_ac4_publish_error_does_not_stop_others(self):
        """AC4: If publish fails for one piece, others still run."""
        pieces = [
            _make_piece("piece-001", status="scheduled"),
            _make_piece("piece-002", status="scheduled"),
            _make_piece("piece-003", status="scheduled"),
        ]
        call_counts = [0]

        async def fake_publish(piece):
            call_counts[0] += 1
            if piece["id"] == "piece-001":
                raise RuntimeError("Instagram API error")

        mock_sb = _make_sb_mock(pieces)

        with patch("runtime.db.supabase", mock_sb), \
             patch("runtime.content.publisher.publish", side_effect=fake_publish):
            import importlib, runtime.crons.content as cron_mod
            importlib.reload(cron_mod)
            await cron_mod._run_content_publisher_tick()

        assert call_counts[0] == 3

    @pytest.mark.asyncio
    async def test_no_due_pieces_does_nothing(self):
        """When no pieces are due, no publish calls made."""
        mock_publish = AsyncMock()
        mock_sb = _make_sb_mock([])

        with patch("runtime.db.supabase", mock_sb), \
             patch("runtime.content.publisher.publish", mock_publish):
            import importlib, runtime.crons.content as cron_mod
            importlib.reload(cron_mod)
            await cron_mod._run_content_publisher_tick()

        mock_publish.assert_not_called()


# ══════════════════════════════════════════════════════════════
# content_brain_sync tests (AC3, AC4)
# ══════════════════════════════════════════════════════════════

class TestContentBrainSync:
    @pytest.mark.asyncio
    async def test_ingests_published_pieces_without_chunk_id(self):
        """AC3: Published pieces with brain_chunk_id IS NULL get ingested."""
        pieces = [
            _make_piece("piece-001", status="published", brain_chunk_id=None),
            _make_piece("piece-002", status="published", brain_chunk_id=None),
        ]
        mock_ingest = AsyncMock(return_value="chunk-abc-123")
        mock_update = MagicMock()
        mock_sb = _make_sb_mock(pieces)

        with patch("runtime.db.supabase", mock_sb), \
             patch("runtime.content.publisher._ingest_published_to_brain", mock_ingest), \
             patch("runtime.content.publisher._update_piece", mock_update):
            import importlib, runtime.crons.content as cron_mod
            importlib.reload(cron_mod)
            await cron_mod._run_content_brain_sync()

        assert mock_ingest.call_count == 2
        assert mock_update.call_count == 2

    @pytest.mark.asyncio
    async def test_updates_brain_chunk_id_on_success(self):
        """AC3: After ingest, brain_chunk_id is updated on the piece."""
        pieces = [_make_piece("piece-001", status="published")]
        mock_ingest = AsyncMock(return_value="chunk-xyz-999")
        update_calls: list = []

        def mock_update(piece_id, fields):
            update_calls.append((piece_id, fields))

        mock_sb = _make_sb_mock(pieces)

        with patch("runtime.db.supabase", mock_sb), \
             patch("runtime.content.publisher._ingest_published_to_brain", mock_ingest), \
             patch("runtime.content.publisher._update_piece", side_effect=mock_update):
            import importlib, runtime.crons.content as cron_mod
            importlib.reload(cron_mod)
            await cron_mod._run_content_brain_sync()

        assert len(update_calls) == 1
        assert update_calls[0][1]["brain_chunk_id"] == "chunk-xyz-999"

    @pytest.mark.asyncio
    async def test_ac4_ingest_error_does_not_stop_others(self):
        """AC4: If ingest fails for one piece, others still process."""
        pieces = [
            _make_piece("piece-001", status="published"),
            _make_piece("piece-002", status="published"),
            _make_piece("piece-003", status="published"),
        ]
        ingest_calls = [0]

        async def fake_ingest(piece):
            ingest_calls[0] += 1
            if piece["id"] == "piece-002":
                raise RuntimeError("Brain ingest error")
            return "chunk-ok"

        mock_sb = _make_sb_mock(pieces)

        with patch("runtime.db.supabase", mock_sb), \
             patch("runtime.content.publisher._ingest_published_to_brain", side_effect=fake_ingest), \
             patch("runtime.content.publisher._update_piece"):
            import importlib, runtime.crons.content as cron_mod
            importlib.reload(cron_mod)
            await cron_mod._run_content_brain_sync()

        assert ingest_calls[0] == 3

    @pytest.mark.asyncio
    async def test_no_published_pieces_does_nothing(self):
        """When no published pieces need syncing, no ingest calls made."""
        mock_ingest = AsyncMock()
        mock_sb = _make_sb_mock([])

        with patch("runtime.db.supabase", mock_sb), \
             patch("runtime.content.publisher._ingest_published_to_brain", mock_ingest):
            import importlib, runtime.crons.content as cron_mod
            importlib.reload(cron_mod)
            await cron_mod._run_content_brain_sync()

        mock_ingest.assert_not_called()


# ══════════════════════════════════════════════════════════════
# register_content_jobs tests
# ══════════════════════════════════════════════════════════════

class TestRegisterContentJobs:
    def test_registers_all_three_jobs(self):
        """register_content_jobs should add exactly 3 jobs to the scheduler."""
        mock_scheduler = MagicMock()

        from runtime.crons.content import register_content_jobs
        register_content_jobs(mock_scheduler)

        assert mock_scheduler.add_job.call_count == 3

    def test_job_ids_are_correct(self):
        """Registered job IDs must match the 3 content cron names."""
        mock_scheduler = MagicMock()

        from runtime.crons.content import register_content_jobs
        register_content_jobs(mock_scheduler)

        job_ids = {c[1].get("id") for c in mock_scheduler.add_job.call_args_list}
        assert "content_pipeline_tick" in job_ids
        assert "content_publisher_tick" in job_ids
        assert "content_brain_sync" in job_ids


# ══════════════════════════════════════════════════════════════
# Friday notification tests (AC5, AC6, AC7, AC8)
# ══════════════════════════════════════════════════════════════

class TestFridayNotifications:
    @pytest.mark.asyncio
    async def test_pending_approval_anti_spam_blocks_notification(self):
        """AC6: When cooldown entry exists (< 1h ago), do not send notification."""
        mock_send = MagicMock()
        mock_sb = MagicMock()
        mock_q = MagicMock()
        mock_q.select.return_value = mock_q
        mock_q.eq.return_value = mock_q
        mock_q.gte.return_value = mock_q
        mock_q.limit.return_value = mock_q
        # Return a recent entry -- means we are in cooldown
        mock_q.execute.return_value = MagicMock(data=[{"id": "recent-entry"}])
        mock_sb.table.return_value = mock_q

        with patch("runtime.db.supabase", mock_sb), \
             patch("runtime.integrations.zapi.send_text", mock_send):
            import importlib
            import runtime.content.pipeline as pl
            importlib.reload(pl)
            await pl.friday_notify_pending_approval()

        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_pending_approval_sends_when_no_cooldown(self):
        """AC5/AC7: Friday notified when no cooldown and pieces exist."""
        mock_send = MagicMock(return_value={"sent": True})

        # Build multi-table mock
        mock_sb = MagicMock()
        table_calls = [0]

        mock_cooldown = MagicMock()
        mock_cooldown.select.return_value = mock_cooldown
        mock_cooldown.eq.return_value = mock_cooldown
        mock_cooldown.gte.return_value = mock_cooldown
        mock_cooldown.limit.return_value = mock_cooldown
        mock_cooldown.execute.return_value = MagicMock(data=[])  # no cooldown

        mock_count = MagicMock()
        mock_count.select.return_value = mock_count
        mock_count.eq.return_value = mock_count
        mock_count.execute.return_value = MagicMock(data=[{"id": "p1"}, {"id": "p2"}], count=2)

        mock_record = MagicMock()
        mock_record.insert.return_value = mock_record
        mock_record.execute.return_value = MagicMock(data=[{"id": "new-log"}])

        def route_table(name):
            table_calls[0] += 1
            if name == "cron_executions" and table_calls[0] == 1:
                return mock_cooldown
            elif name == "cron_executions":
                return mock_record
            else:
                return mock_count

        mock_sb.table.side_effect = route_table

        with patch("runtime.db.supabase", mock_sb), \
             patch("runtime.integrations.zapi.send_text", mock_send):
            import importlib, runtime.content.pipeline as pl
            importlib.reload(pl)

            # Patch settings at call-time
            with patch("runtime.config.settings") as mock_cfg:
                mock_cfg.mauro_whatsapp = "5512999999999"
                await pl.friday_notify_pending_approval()

        # Verify send was called
        mock_send.assert_called_once()
        call_msg = mock_send.call_args[0][1]
        assert "conteudo" in call_msg.lower() or "zenya" in call_msg.lower()

    @pytest.mark.asyncio
    async def test_pending_approval_notification_skipped_if_zero_pieces(self):
        """If count is 0, no notification sent even without cooldown."""
        mock_send = MagicMock()
        mock_sb = MagicMock()
        table_calls = [0]

        mock_cooldown = MagicMock()
        mock_cooldown.select.return_value = mock_cooldown
        mock_cooldown.eq.return_value = mock_cooldown
        mock_cooldown.gte.return_value = mock_cooldown
        mock_cooldown.limit.return_value = mock_cooldown
        mock_cooldown.execute.return_value = MagicMock(data=[])

        mock_count = MagicMock()
        mock_count.select.return_value = mock_count
        mock_count.eq.return_value = mock_count
        mock_count.execute.return_value = MagicMock(data=[], count=0)

        def route_table(name):
            table_calls[0] += 1
            if name == "cron_executions":
                return mock_cooldown
            return mock_count

        mock_sb.table.side_effect = route_table

        with patch("runtime.db.supabase", mock_sb), \
             patch("runtime.integrations.zapi.send_text", mock_send):
            import importlib, runtime.content.pipeline as pl
            importlib.reload(pl)
            await pl.friday_notify_pending_approval()

        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_failed_notification_content(self):
        """AC8: Message must mention 'Falha' and '/content/' URL."""
        sent_messages: list[str] = []

        def mock_send(phone, msg):
            sent_messages.append(msg)

        with patch("runtime.content.publisher.settings") as mock_settings, \
             patch("runtime.integrations.zapi.send_text", side_effect=mock_send):
            mock_settings.mauro_whatsapp = "5512999999999"

            from runtime.content.publisher import _notify_friday_publish_failed
            await _notify_friday_publish_failed("piece-abc-123", "Instagram API 500")

        assert len(sent_messages) == 1
        msg = sent_messages[0]
        assert "Falha" in msg or "falha" in msg.lower(), f"Message should mention failure: {msg}"
        assert "/content/" in msg, f"Message should include /content/ URL: {msg}"

    @pytest.mark.asyncio
    async def test_publish_failed_includes_piece_id_prefix(self):
        """AC8: Message includes truncated piece ID for identification."""
        sent_messages: list[str] = []

        def mock_send(phone, msg):
            sent_messages.append(msg)

        with patch("runtime.content.publisher.settings") as mock_settings, \
             patch("runtime.integrations.zapi.send_text", side_effect=mock_send):
            mock_settings.mauro_whatsapp = "5512999999999"

            from runtime.content.publisher import _notify_friday_publish_failed
            await _notify_friday_publish_failed("piece-abc-123", "error")

        assert len(sent_messages) == 1
        assert "piece-ab" in sent_messages[0]

    @pytest.mark.asyncio
    async def test_publish_failed_notification_skipped_if_no_phone(self):
        """If MAURO_WHATSAPP is not set, skip notification gracefully."""
        mock_send = MagicMock()

        with patch("runtime.content.publisher.settings") as mock_settings, \
             patch("runtime.integrations.zapi.send_text", mock_send):
            mock_settings.mauro_whatsapp = ""

            from runtime.content.publisher import _notify_friday_publish_failed
            await _notify_friday_publish_failed("piece-abc-123", "error")

        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_failed_notification_handles_send_error(self):
        """If Z-API send_text raises, _notify_friday_publish_failed handles it gracefully."""
        def broken_send(phone, msg):
            raise RuntimeError("Z-API offline")

        with patch("runtime.content.publisher.settings") as mock_settings, \
             patch("runtime.integrations.zapi.send_text", side_effect=broken_send):
            mock_settings.mauro_whatsapp = "5512999999999"

            from runtime.content.publisher import _notify_friday_publish_failed
            # Should not raise
            await _notify_friday_publish_failed("piece-abc-123", "error")
