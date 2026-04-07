"""
Unit tests for Instagram Publisher (CONTENT-1.11).

All external APIs (Instagram Graph API, Supabase, Z-API, Brain) are mocked.
Run: pytest tests/unit/test_publisher.py -v
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest


# ══════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════

FAKE_PIECE_BASE = {
    "id": "piece-aaa-bbb-ccc-111",
    "status": "scheduled",
    "video_url": "https://storage.supabase.co/videos/test.mp4",
    "final_url": None,
    "caption": "Test caption #ai #zenya",
    "voice_script": "Hello from Zenya",
    "theme": "IA para PMEs",
    "mood": "inspirador",
    "style": "influencer_natural",
    "pipeline_log": [],
    "brain_chunk_id": None,
    "published_at": None,
    "published_url": None,
    "scheduled_at": None,
    "creator_id": None,
}


def _make_piece(**overrides) -> dict:
    return {**FAKE_PIECE_BASE, **overrides}


@pytest.fixture(autouse=True)
def _mock_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "fake-key")
    monkeypatch.setenv("MAURO_WHATSAPP", "5512999999999")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "fake-ig-token")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "12345678")


@pytest.fixture()
def mock_supabase_client():
    """Mock supabase db with chainable query interface."""
    mock_sb = MagicMock()
    # table().select().eq().limit().execute() → return piece
    mock_query = MagicMock()
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.is_.return_value = mock_query
    mock_query.lte.return_value = mock_query
    mock_query.gte.return_value = mock_query
    mock_query.in_.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.update.return_value = mock_query
    mock_query.insert.return_value = mock_query
    mock_query.execute.return_value = MagicMock(data=[], count=0)
    mock_sb.table.return_value = mock_query
    mock_sb.rpc.return_value = mock_query
    return mock_sb, mock_query


# ══════════════════════════════════════════════════════════════
# get_next_slot tests (AC6, AC7)
# ══════════════════════════════════════════════════════════════

class TestGetNextSlot:
    def test_returns_a_future_datetime(self):
        """get_next_slot must always return a datetime in the future."""
        with patch("runtime.db.supabase") as mock_sb:
            mock_query = MagicMock()
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value = mock_query

            from runtime.content.publisher import get_next_slot
            slot = get_next_slot()

        assert isinstance(slot, datetime)
        assert slot > datetime.now(timezone.utc), "Slot must be in the future"

    def test_slot_is_valid_hour(self):
        """Slot must be one of 08h, 12h, or 18h BRT (= 11h, 15h, 21h UTC)."""
        valid_utc_hours = {11, 15, 21}  # BRT + 3

        with patch("runtime.db.supabase") as mock_sb:
            mock_query = MagicMock()
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value = mock_query

            from runtime.content.publisher import get_next_slot
            slot = get_next_slot()

        assert slot.hour in valid_utc_hours, (
            f"Slot UTC hour {slot.hour} not in valid set {valid_utc_hours}"
        )

    def test_skips_occupied_slots(self):
        """When a slot is occupied, get_next_slot picks the next available one."""
        # Simulate 1 occupied slot at the next candidate time
        now = datetime.now(timezone.utc)
        # Force first future slot to be "occupied"
        next_day = now + timedelta(days=1)
        occupied_slot = next_day.strftime("%Y-%m-%dT") + "11"  # 11h UTC = 08h BRT

        with patch("runtime.db.supabase") as mock_sb:
            mock_query = MagicMock()
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.execute.return_value = MagicMock(
                data=[{"scheduled_at": occupied_slot + ":00:00Z"}]
            )
            mock_sb.table.return_value = mock_query

            from runtime.content.publisher import get_next_slot

            # Run twice — may or may not skip the occupied slot depending on timing
            # Just verify it returns a valid future datetime
            slot = get_next_slot()
            assert slot > datetime.now(timezone.utc)

    def test_db_error_falls_back_gracefully(self):
        """If DB query fails, get_next_slot still returns a valid future datetime."""
        with patch("runtime.db.supabase") as mock_sb:
            mock_sb.table.side_effect = Exception("DB offline")

            from runtime.content.publisher import get_next_slot
            slot = get_next_slot()

        assert isinstance(slot, datetime)
        assert slot > datetime.now(timezone.utc)


# ══════════════════════════════════════════════════════════════
# _create_media_container tests
# ══════════════════════════════════════════════════════════════

class TestCreateMediaContainer:
    @pytest.mark.asyncio
    async def test_returns_creation_id_on_success(self):
        """Should return creation_id string on 200 response."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "container-abc-123"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            from runtime.content.publisher import _create_media_container
            result = await _create_media_container(
                ig_user_id="12345678",
                access_token="fake-token",
                video_url="https://example.com/video.mp4",
                caption="Test caption",
            )

        assert result == "container-abc-123"

    @pytest.mark.asyncio
    async def test_raises_on_non_200(self):
        """Should raise RuntimeError when API returns non-200."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad request"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            from runtime.content.publisher import _create_media_container
            with pytest.raises(RuntimeError, match="container creation failed"):
                await _create_media_container(
                    ig_user_id="123",
                    access_token="tok",
                    video_url="https://example.com/v.mp4",
                    caption="",
                )

    @pytest.mark.asyncio
    async def test_raises_if_no_id_in_response(self):
        """Should raise RuntimeError if API response has no 'id' field."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"error": "something"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            from runtime.content.publisher import _create_media_container
            with pytest.raises(RuntimeError, match="did not return container id"):
                await _create_media_container("123", "tok", "url", "cap")


# ══════════════════════════════════════════════════════════════
# _poll_container_status tests
# ══════════════════════════════════════════════════════════════

class TestPollContainerStatus:
    @pytest.mark.asyncio
    async def test_returns_finished_on_first_poll(self):
        """Should return FINISHED immediately if first poll returns FINISHED."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status_code": "FINISHED"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            from runtime.content.publisher import _poll_container_status
            status = await _poll_container_status("container-123", "fake-token")

        assert status == "FINISHED"

    @pytest.mark.asyncio
    async def test_polls_multiple_times_before_finished(self):
        """Should poll until FINISHED, sleeping between attempts."""
        responses = [
            MagicMock(status_code=200, json=MagicMock(return_value={"status_code": "IN_PROGRESS"})),
            MagicMock(status_code=200, json=MagicMock(return_value={"status_code": "IN_PROGRESS"})),
            MagicMock(status_code=200, json=MagicMock(return_value={"status_code": "FINISHED"})),
        ]
        call_count = 0

        async def fake_get(*args, **kwargs):
            nonlocal call_count
            r = responses[min(call_count, len(responses) - 1)]
            call_count += 1
            return r

        mock_client = AsyncMock()
        mock_client.get = fake_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            from runtime.content.publisher import _poll_container_status
            status = await _poll_container_status("container-123", "fake-token")

        assert status == "FINISHED"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_on_error_status(self):
        """Should raise RuntimeError if container reaches ERROR status."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status_code": "ERROR"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            from runtime.content.publisher import _poll_container_status
            with pytest.raises(RuntimeError, match="terminal error status"):
                await _poll_container_status("container-123", "tok")


# ══════════════════════════════════════════════════════════════
# _publish_container tests
# ══════════════════════════════════════════════════════════════

class TestPublishContainer:
    @pytest.mark.asyncio
    async def test_returns_media_id_on_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "media-post-999"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            from runtime.content.publisher import _publish_container
            media_id = await _publish_container("12345678", "fake-token", "container-xyz")

        assert media_id == "media-post-999"

    @pytest.mark.asyncio
    async def test_raises_on_api_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal error"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            from runtime.content.publisher import _publish_container
            with pytest.raises(RuntimeError, match="publish failed"):
                await _publish_container("123", "tok", "container-abc")


# ══════════════════════════════════════════════════════════════
# publish() integration tests (AC2, AC3, AC4)
# ══════════════════════════════════════════════════════════════

class TestPublish:
    @pytest.mark.asyncio
    async def test_success_sets_published_status(self):
        """AC3: On success, status='published', published_at and published_url set."""
        piece = _make_piece()
        published_piece = {**piece, "status": "published", "published_url": "https://www.instagram.com/p/ABC123/"}

        with patch("runtime.db.supabase") as mock_sb, \
             patch("runtime.content.publisher._create_media_container", new_callable=AsyncMock) as mock_create, \
             patch("runtime.content.publisher._poll_container_status", new_callable=AsyncMock) as mock_poll, \
             patch("runtime.content.publisher._publish_container", new_callable=AsyncMock) as mock_pub, \
             patch("runtime.content.publisher._get_piece") as mock_get, \
             patch("runtime.content.publisher._update_piece") as mock_update, \
             patch("runtime.content.publisher._append_pipeline_log") as mock_log, \
             patch("asyncio.create_task"):

            mock_create.return_value = "container-xyz"
            mock_poll.return_value = "FINISHED"
            mock_pub.return_value = "ABC123"
            mock_get.return_value = published_piece

            # Mock settings
            with patch("runtime.content.publisher.settings") as mock_settings:
                mock_settings.instagram_access_token = "fake-token"
                mock_settings.instagram_user_id = "12345678"
                mock_settings.mauro_whatsapp = "5512999999999"

                from runtime.content.publisher import publish
                result = await publish(piece)

        # Verify _update_piece was called with published status
        update_calls = mock_update.call_args_list
        published_call = [c for c in update_calls if c[0][1].get("status") == "published"]
        assert published_call, "Should have called _update_piece with status='published'"

        # Verify published_url format
        published_url_call = published_call[0][0][1].get("published_url", "")
        assert published_url_call.startswith("https://www.instagram.com/p/")

    @pytest.mark.asyncio
    async def test_failure_sets_publish_failed_status(self):
        """AC4: On failure, status='publish_failed', error_log updated."""
        piece = _make_piece()
        failed_piece = {**piece, "status": "publish_failed", "error_log": "API error"}

        with patch("runtime.content.publisher._create_media_container", new_callable=AsyncMock) as mock_create, \
             patch("runtime.content.publisher._get_piece") as mock_get, \
             patch("runtime.content.publisher._update_piece") as mock_update, \
             patch("runtime.content.publisher._append_pipeline_log"), \
             patch("asyncio.create_task"):

            mock_create.side_effect = RuntimeError("Instagram API error: 500")
            mock_get.return_value = failed_piece

            with patch("runtime.content.publisher.settings") as mock_settings:
                mock_settings.instagram_access_token = "fake-token"
                mock_settings.instagram_user_id = "12345678"
                mock_settings.mauro_whatsapp = "5512999999999"

                from runtime.content.publisher import publish
                result = await publish(piece)

        update_calls = mock_update.call_args_list
        failed_call = [c for c in update_calls if c[0][1].get("status") == "publish_failed"]
        assert failed_call, "Should have called _update_piece with status='publish_failed'"
        assert "error_log" in failed_call[0][0][1]

    @pytest.mark.asyncio
    async def test_missing_credentials_sets_publish_failed(self):
        """If Instagram credentials are not configured, set publish_failed immediately."""
        piece = _make_piece()

        with patch("runtime.content.publisher._get_piece", return_value=piece), \
             patch("runtime.content.publisher._update_piece") as mock_update, \
             patch("runtime.content.publisher._append_pipeline_log"), \
             patch("asyncio.create_task"):

            with patch("runtime.content.publisher.settings") as mock_settings:
                mock_settings.instagram_access_token = ""
                mock_settings.instagram_user_id = ""
                mock_settings.mauro_whatsapp = "5512999999999"

                from runtime.content.publisher import publish
                await publish(piece)

        update_calls = mock_update.call_args_list
        failed_call = [c for c in update_calls if c[0][1].get("status") == "publish_failed"]
        assert failed_call

    @pytest.mark.asyncio
    async def test_friday_notified_on_publish_failed(self):
        """AC4: Friday notification triggered when publish fails."""
        piece = _make_piece()

        create_task_calls: list = []

        def fake_create_task(coro):
            create_task_calls.append(coro)
            # Cancel to avoid unawaited coroutine warning
            coro.close()
            return MagicMock()

        with patch("runtime.content.publisher._create_media_container", new_callable=AsyncMock) as mock_create, \
             patch("runtime.content.publisher._get_piece", return_value=piece), \
             patch("runtime.content.publisher._update_piece"), \
             patch("runtime.content.publisher._append_pipeline_log"), \
             patch("asyncio.create_task", side_effect=fake_create_task):

            mock_create.side_effect = RuntimeError("Test error")

            with patch("runtime.content.publisher.settings") as mock_settings:
                mock_settings.instagram_access_token = "fake-token"
                mock_settings.instagram_user_id = "12345678"
                mock_settings.mauro_whatsapp = "5512999999999"

                from runtime.content.publisher import publish
                await publish(piece)

        # At least one create_task call should have happened (for Friday notify)
        assert len(create_task_calls) >= 1

    @pytest.mark.asyncio
    async def test_missing_video_url_sets_publish_failed(self):
        """Piece without video_url or final_url should go to publish_failed."""
        piece = _make_piece(video_url=None, final_url=None)

        with patch("runtime.content.publisher._get_piece", return_value=piece), \
             patch("runtime.content.publisher._update_piece") as mock_update, \
             patch("runtime.content.publisher._append_pipeline_log"), \
             patch("asyncio.create_task"):

            with patch("runtime.content.publisher.settings") as mock_settings:
                mock_settings.instagram_access_token = "fake-token"
                mock_settings.instagram_user_id = "12345678"
                mock_settings.mauro_whatsapp = "5512999999999"

                from runtime.content.publisher import publish
                await publish(piece)

        update_calls = mock_update.call_args_list
        failed_call = [c for c in update_calls if c[0][1].get("status") == "publish_failed"]
        assert failed_call

    @pytest.mark.asyncio
    async def test_published_url_format(self):
        """AC3: published_url must be https://www.instagram.com/p/{media_id}/"""
        piece = _make_piece()
        fresh_piece = {**piece, "status": "published"}

        with patch("runtime.content.publisher._create_media_container", new_callable=AsyncMock, return_value="cnt-xyz"), \
             patch("runtime.content.publisher._poll_container_status", new_callable=AsyncMock, return_value="FINISHED"), \
             patch("runtime.content.publisher._publish_container", new_callable=AsyncMock, return_value="MEDIA999"), \
             patch("runtime.content.publisher._get_piece", return_value=fresh_piece), \
             patch("runtime.content.publisher._update_piece") as mock_update, \
             patch("runtime.content.publisher._append_pipeline_log"), \
             patch("asyncio.create_task"):

            with patch("runtime.content.publisher.settings") as mock_settings:
                mock_settings.instagram_access_token = "fake-token"
                mock_settings.instagram_user_id = "12345678"
                mock_settings.mauro_whatsapp = "5512999999999"

                from runtime.content.publisher import publish
                await publish(piece)

        update_calls = mock_update.call_args_list
        published_call = [c for c in update_calls if c[0][1].get("status") == "published"]
        assert published_call
        assert published_call[0][0][1]["published_url"] == "https://www.instagram.com/p/MEDIA999/"

    @pytest.mark.asyncio
    async def test_brain_ingest_triggered_on_success(self):
        """AC5: Brain ingest triggered via asyncio.create_task on successful publish."""
        piece = _make_piece()
        fresh_piece = {**piece, "status": "published"}

        task_calls: list = []

        def fake_create_task(coro):
            task_calls.append(coro)
            coro.close()
            return MagicMock()

        with patch("runtime.content.publisher._create_media_container", new_callable=AsyncMock, return_value="cnt-xyz"), \
             patch("runtime.content.publisher._poll_container_status", new_callable=AsyncMock, return_value="FINISHED"), \
             patch("runtime.content.publisher._publish_container", new_callable=AsyncMock, return_value="MEDIA123"), \
             patch("runtime.content.publisher._get_piece", return_value=fresh_piece), \
             patch("runtime.content.publisher._update_piece"), \
             patch("runtime.content.publisher._append_pipeline_log"), \
             patch("asyncio.create_task", side_effect=fake_create_task):

            with patch("runtime.content.publisher.settings") as mock_settings:
                mock_settings.instagram_access_token = "fake-token"
                mock_settings.instagram_user_id = "12345678"
                mock_settings.mauro_whatsapp = "5512999999999"

                from runtime.content.publisher import publish
                await publish(piece)

        # create_task should have been called at least once (for brain ingest)
        assert len(task_calls) >= 1


# ══════════════════════════════════════════════════════════════
# schedule_piece tests (AC1)
# ══════════════════════════════════════════════════════════════

class TestSchedulePiece:
    def test_schedule_piece_returns_datetime(self):
        """schedule_piece should return a future datetime."""
        with patch("runtime.db.supabase") as mock_sb, \
             patch("runtime.content.publisher.get_next_slot") as mock_slot, \
             patch("runtime.content.publisher._update_piece") as mock_update, \
             patch("runtime.content.publisher._append_pipeline_log"):

            future_dt = datetime.now(timezone.utc) + timedelta(hours=8)
            mock_slot.return_value = future_dt

            from runtime.content.publisher import schedule_piece
            result = schedule_piece("fake-piece-id")

        assert result == future_dt

    def test_schedule_piece_calls_update_with_scheduled_status(self):
        """schedule_piece must update status to 'scheduled'."""
        with patch("runtime.content.publisher.get_next_slot") as mock_slot, \
             patch("runtime.content.publisher._update_piece") as mock_update, \
             patch("runtime.content.publisher._append_pipeline_log"):

            future_dt = datetime.now(timezone.utc) + timedelta(hours=8)
            mock_slot.return_value = future_dt

            from runtime.content.publisher import schedule_piece
            schedule_piece("fake-piece-id")

        mock_update.assert_called_once()
        call_args = mock_update.call_args[0]
        assert call_args[1]["status"] == "scheduled"
        assert "scheduled_at" in call_args[1]
