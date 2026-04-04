"""
Unit tests for Member State Engine (B4-05).

Tests level calculation, event recording logic, leaderboard, and
community member CRUD operations.

All DB calls are mocked via asyncio.to_thread patch.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Level Calculation Tests ──────────────────────────────────────────────────

class TestCalculateLevel:
    """Tests for the XP-to-level calculation."""

    def test_zero_xp_is_level_1(self):
        from runtime.members.state import calculate_level
        assert calculate_level(0) == 1

    def test_small_xp_is_level_1(self):
        from runtime.members.state import calculate_level
        assert calculate_level(50) == 1
        assert calculate_level(99) == 1

    def test_100_xp_is_level_2(self):
        from runtime.members.state import calculate_level
        assert calculate_level(100) == 2

    def test_level_increases_with_xp(self):
        from runtime.members.state import calculate_level
        levels = [calculate_level(xp) for xp in [0, 100, 300, 600, 900, 1200, 1500, 1900, 2300, 2700]]
        # Each should be >= previous
        for i in range(1, len(levels)):
            assert levels[i] >= levels[i - 1], f"Level should not decrease: {levels}"

    def test_max_level_is_10(self):
        from runtime.members.state import calculate_level
        assert calculate_level(999999) == 10

    def test_negative_xp_is_level_1(self):
        from runtime.members.state import calculate_level
        assert calculate_level(-100) == 1

    def test_level_thresholds_are_sorted(self):
        from runtime.members.state import LEVEL_THRESHOLDS
        assert LEVEL_THRESHOLDS == sorted(LEVEL_THRESHOLDS)
        assert len(LEVEL_THRESHOLDS) == 10

    def test_exact_threshold_boundaries(self):
        from runtime.members.state import calculate_level, LEVEL_THRESHOLDS
        # At each threshold, you should be exactly that level
        for i, threshold in enumerate(LEVEL_THRESHOLDS):
            expected_level = i + 1
            assert calculate_level(threshold) == expected_level, (
                f"XP {threshold} should be level {expected_level}"
            )
        # One below each threshold (except level 1) should be previous level
        for i in range(1, len(LEVEL_THRESHOLDS)):
            xp_below = LEVEL_THRESHOLDS[i] - 1
            expected_level = i  # previous level
            assert calculate_level(xp_below) == expected_level, (
                f"XP {xp_below} should be level {expected_level}"
            )

    def test_all_10_levels_reachable(self):
        from runtime.members.state import calculate_level, LEVEL_THRESHOLDS
        for i, threshold in enumerate(LEVEL_THRESHOLDS):
            assert calculate_level(threshold) == i + 1


# ── Event Recording Tests ────────────────────────────────────────────────────

def _make_to_thread_mock(responses: list):
    """Create an async side_effect that returns responses in order."""
    call_idx = 0

    async def side_effect(fn):
        nonlocal call_idx
        if call_idx < len(responses):
            result = responses[call_idx]
            call_idx += 1
            return result
        call_idx += 1
        return MagicMock(data=[])

    return side_effect


class TestRecordEvent:
    """Tests for record_event logic (XP update + level recalculation)."""

    @pytest.mark.asyncio
    async def test_record_event_with_xp(self):
        from runtime.members.state import record_event

        fake_event_row = {
            "id": "evt-001",
            "member_id": "member-uuid-001",
            "event_type": "message_sent",
            "event_data": {},
            "xp_earned": 25,
        }

        responses = [
            MagicMock(data=[fake_event_row]),   # insert event
            MagicMock(data={"xp": 75}),         # select current xp
            MagicMock(data=[{"xp": 100}]),      # update xp/level
        ]

        with patch("runtime.members.state.asyncio.to_thread", side_effect=_make_to_thread_mock(responses)):
            result = await record_event(
                member_id="member-uuid-001",
                event_type="message_sent",
                event_data={},
                xp_earned=25,
            )

        assert result["new_xp"] == 100
        assert result["new_level"] == 2

    @pytest.mark.asyncio
    async def test_record_event_zero_xp_no_level_change(self):
        from runtime.members.state import record_event

        fake_event_row = {
            "id": "evt-002",
            "member_id": "member-uuid-001",
            "event_type": "page_view",
            "event_data": {},
            "xp_earned": 0,
        }

        responses = [
            MagicMock(data=[fake_event_row]),   # insert event
            MagicMock(data=[]),                 # update last_active_at
        ]

        with patch("runtime.members.state.asyncio.to_thread", side_effect=_make_to_thread_mock(responses)):
            result = await record_event(
                member_id="member-uuid-001",
                event_type="page_view",
                xp_earned=0,
            )

        assert "new_xp" not in result
        assert "new_level" not in result
        assert result["event_type"] == "page_view"

    @pytest.mark.asyncio
    async def test_record_event_level_up_from_0(self):
        from runtime.members.state import record_event

        fake_event_row = {
            "id": "evt-003",
            "member_id": "uuid-fresh",
            "event_type": "first_message",
            "event_data": {"welcome": True},
            "xp_earned": 100,
        }

        responses = [
            MagicMock(data=[fake_event_row]),   # insert event
            MagicMock(data={"xp": 0}),          # select current xp (fresh member)
            MagicMock(data=[{"xp": 100}]),      # update
        ]

        with patch("runtime.members.state.asyncio.to_thread", side_effect=_make_to_thread_mock(responses)):
            result = await record_event(
                member_id="uuid-fresh",
                event_type="first_message",
                event_data={"welcome": True},
                xp_earned=100,
            )

        assert result["new_xp"] == 100
        assert result["new_level"] == 2


# ── Leaderboard Tests ────────────────────────────────────────────────────────

class TestGetLeaderboard:
    """Tests for leaderboard ranking logic."""

    @pytest.mark.asyncio
    async def test_leaderboard_adds_rank(self):
        from runtime.members.state import get_leaderboard

        fake_rows = [
            {"id": "a", "member_id": "m1", "display_name": "Alice", "level": 5, "xp": 1000, "engagement_score": 0.8, "last_active_at": None},
            {"id": "b", "member_id": "m2", "display_name": "Bob", "level": 3, "xp": 500, "engagement_score": 0.6, "last_active_at": None},
            {"id": "c", "member_id": "m3", "display_name": "Carol", "level": 2, "xp": 200, "engagement_score": 0.4, "last_active_at": None},
        ]

        async def mock_to_thread(fn):
            return MagicMock(data=fake_rows)

        with patch("runtime.members.state.asyncio.to_thread", side_effect=mock_to_thread):
            result = await get_leaderboard(client_id="client-001", limit=10)

        assert len(result) == 3
        assert result[0]["rank"] == 1
        assert result[0]["display_name"] == "Alice"
        assert result[1]["rank"] == 2
        assert result[2]["rank"] == 3

    @pytest.mark.asyncio
    async def test_leaderboard_empty(self):
        from runtime.members.state import get_leaderboard

        async def mock_to_thread(fn):
            return MagicMock(data=[])

        with patch("runtime.members.state.asyncio.to_thread", side_effect=mock_to_thread):
            result = await get_leaderboard(client_id="client-empty")

        assert result == []


# ── Get Member Tests ─────────────────────────────────────────────────────────

class TestGetMember:
    """Tests for get_member lookup."""

    @pytest.mark.asyncio
    async def test_get_member_found(self):
        from runtime.members.state import get_member

        fake_member = {
            "id": "uuid-001",
            "client_id": "c1",
            "member_id": "m1",
            "display_name": "Alice",
            "level": 3,
            "xp": 500,
            "status": "active",
        }

        async def mock_to_thread(fn):
            return MagicMock(data=fake_member)

        with patch("runtime.members.state.asyncio.to_thread", side_effect=mock_to_thread):
            result = await get_member(client_id="c1", member_id="m1")

        assert result is not None
        assert result["display_name"] == "Alice"

    @pytest.mark.asyncio
    async def test_get_member_not_found(self):
        from runtime.members.state import get_member

        async def mock_to_thread(fn):
            return MagicMock(data=None)

        with patch("runtime.members.state.asyncio.to_thread", side_effect=mock_to_thread):
            result = await get_member(client_id="c1", member_id="nonexistent")

        assert result is None


# ── Create Member Tests ──────────────────────────────────────────────────────

class TestCreateMember:
    """Tests for create_member upsert."""

    @pytest.mark.asyncio
    async def test_create_member_returns_row(self):
        from runtime.members.state import create_member

        fake_row = {
            "id": "uuid-new",
            "client_id": "c1",
            "member_id": "m-new",
            "display_name": "NewUser",
            "level": 1,
            "xp": 0,
            "status": "active",
        }

        async def mock_to_thread(fn):
            return MagicMock(data=[fake_row])

        with patch("runtime.members.state.asyncio.to_thread", side_effect=mock_to_thread):
            result = await create_member(
                client_id="c1",
                member_id="m-new",
                display_name="NewUser",
            )

        assert result["member_id"] == "m-new"
        assert result["display_name"] == "NewUser"

    @pytest.mark.asyncio
    async def test_create_member_without_display_name(self):
        from runtime.members.state import create_member

        fake_row = {
            "id": "uuid-new2",
            "client_id": "c1",
            "member_id": "m-anon",
            "display_name": None,
            "level": 1,
            "xp": 0,
        }

        async def mock_to_thread(fn):
            return MagicMock(data=[fake_row])

        with patch("runtime.members.state.asyncio.to_thread", side_effect=mock_to_thread):
            result = await create_member(
                client_id="c1",
                member_id="m-anon",
            )

        assert result["member_id"] == "m-anon"
        assert result["display_name"] is None


# ── Update Member Tests ──────────────────────────────────────────────────────

class TestUpdateMember:
    """Tests for update_member partial update."""

    @pytest.mark.asyncio
    async def test_update_filters_disallowed_fields(self):
        from runtime.members.state import update_member

        fake_row = {
            "id": "uuid-001",
            "display_name": "Updated",
            "status": "active",
        }

        async def mock_to_thread(fn):
            return MagicMock(data=[fake_row])

        with patch("runtime.members.state.asyncio.to_thread", side_effect=mock_to_thread):
            result = await update_member(
                member_id="uuid-001",
                updates={"display_name": "Updated", "xp": 9999, "level": 99},
            )

        # xp and level are NOT in allowed fields — should still return result
        assert result is not None
        assert result["display_name"] == "Updated"

    @pytest.mark.asyncio
    async def test_update_empty_returns_none(self):
        from runtime.members.state import update_member

        result = await update_member(
            member_id="uuid-001",
            updates={"xp": 9999},  # xp not in allowed set
        )

        assert result is None
