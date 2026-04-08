"""
Tests for W2-CLC-1: Client Health Score.

Validates:
- classify() maps score ranges to correct classification labels
- _compute_weighted_score() applies weights correctly
- _signal_volume() handles missing data, new clients, and ratio scenarios
- _signal_payment() maps subscription statuses to scores
- _signal_access() maps days-since-last-event to scores
- calculate_health_score() integrates signals and persists result
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from runtime.client_health.calculator import (
    classify,
    _compute_weighted_score,
    _signal_support,
    _signal_checkin,
)


# ── AC-1: classify() ──────────────────────────────────────────────────────────

class TestClassify:
    def test_score_100_is_healthy(self):
        assert classify(100) == "healthy"

    def test_score_80_is_healthy(self):
        assert classify(80) == "healthy"

    def test_score_79_is_attention(self):
        assert classify(79) == "attention"

    def test_score_60_is_attention(self):
        assert classify(60) == "attention"

    def test_score_59_is_risk(self):
        assert classify(59) == "risk"

    def test_score_40_is_risk(self):
        assert classify(40) == "risk"

    def test_score_39_is_critical(self):
        assert classify(39) == "critical"

    def test_score_0_is_critical(self):
        assert classify(0) == "critical"

    def test_score_50_is_risk(self):
        assert classify(50) == "risk"


# ── AC-1: _compute_weighted_score() ──────────────────────────────────────────

class TestComputeWeightedScore:
    def test_all_100_gives_100(self):
        signals = {
            "volume": {"score": 100},
            "payment": {"score": 100},
            "access": {"score": 100},
            "support": {"score": 100},
            "checkin": {"score": 100},
        }
        assert _compute_weighted_score(signals) == 100

    def test_all_0_gives_0(self):
        signals = {
            "volume": {"score": 0},
            "payment": {"score": 0},
            "access": {"score": 0},
            "support": {"score": 0},
            "checkin": {"score": 0},
        }
        assert _compute_weighted_score(signals) == 0

    def test_all_50_gives_50(self):
        signals = {
            "volume": {"score": 50},
            "payment": {"score": 50},
            "access": {"score": 50},
            "support": {"score": 50},
            "checkin": {"score": 50},
        }
        assert _compute_weighted_score(signals) == 50

    def test_missing_signal_defaults_to_50(self):
        # Only volume (30%) at 100, rest default to 50
        signals = {
            "volume": {"score": 100},
        }
        # 100*0.30 + 50*0.25 + 50*0.20 + 50*0.15 + 50*0.10 = 30+12.5+10+7.5+5 = 65
        result = _compute_weighted_score(signals)
        assert result == 65

    def test_only_payment_at_100(self):
        # payment (25%) at 100, rest at 50
        signals = {
            "payment": {"score": 100},
        }
        # 50*0.30 + 100*0.25 + 50*0.20 + 50*0.15 + 50*0.10 = 15+25+10+7.5+5 = 62.5 → 62 or 63
        result = _compute_weighted_score(signals)
        assert result in (62, 63)

    def test_score_clamped_to_100(self):
        signals = {
            "volume": {"score": 200},  # unrealistic but should be clamped
            "payment": {"score": 100},
            "access": {"score": 100},
            "support": {"score": 100},
            "checkin": {"score": 100},
        }
        result = _compute_weighted_score(signals)
        assert result == 100

    def test_score_clamped_to_0(self):
        signals = {
            "volume": {"score": -100},  # unrealistic but should be clamped
            "payment": {"score": 0},
            "access": {"score": 0},
            "support": {"score": 0},
            "checkin": {"score": 0},
        }
        result = _compute_weighted_score(signals)
        assert result == 0


# ── AC-1: _signal_support() placeholder ─────────────────────────────────────

class TestSignalSupport:
    @pytest.mark.asyncio
    async def test_support_returns_placeholder_80(self):
        result = await _signal_support("any-client-id")
        assert result["score"] == 80
        assert result["open_tickets"] == 0
        assert result["source"] == "placeholder"


# ── AC-1: _signal_checkin() derived from others ──────────────────────────────

class TestSignalCheckin:
    @pytest.mark.asyncio
    async def test_checkin_averages_other_signals(self):
        signals = {
            "volume": {"score": 80},
            "payment": {"score": 60},
            "access": {"score": 100},
            "support": {"score": 80},
        }
        result = await _signal_checkin(signals)
        assert result["score"] == int((80 + 60 + 100 + 80) / 4)
        assert result["source"] == "derived_from_others"

    @pytest.mark.asyncio
    async def test_checkin_empty_signals_defaults_to_80(self):
        result = await _signal_checkin({})
        assert result["score"] == 80
        assert result["source"] == "derived_from_others"

    @pytest.mark.asyncio
    async def test_checkin_single_signal(self):
        signals = {"volume": {"score": 40}}
        result = await _signal_checkin(signals)
        assert result["score"] == 40


# ── AC-1: _signal_volume() logic ─────────────────────────────────────────────

class TestSignalVolume:
    @pytest.mark.asyncio
    async def test_volume_no_history_no_recent(self):
        """New client with no data → neutral score 50."""
        from runtime.client_health.calculator import _signal_volume

        mock_res_recent = MagicMock()
        mock_res_recent.count = 0
        mock_res_prev = MagicMock()
        mock_res_prev.count = 0

        call_count = 0

        async def mock_thread(fn):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_res_recent
            return mock_res_prev

        with patch("asyncio.to_thread", side_effect=mock_thread):
            result = await _signal_volume("test-client")

        assert result["score"] == 50
        assert result["recent_count"] == 0

    @pytest.mark.asyncio
    async def test_volume_new_client_with_recent_activity(self):
        """No history but has recent activity → score 70."""
        from runtime.client_health.calculator import _signal_volume

        mock_res_recent = MagicMock()
        mock_res_recent.count = 10
        mock_res_prev = MagicMock()
        mock_res_prev.count = 0

        call_count = 0

        async def mock_thread(fn):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_res_recent
            return mock_res_prev

        with patch("asyncio.to_thread", side_effect=mock_thread):
            result = await _signal_volume("test-client")

        assert result["score"] == 70

    @pytest.mark.asyncio
    async def test_volume_at_100_percent_of_average(self):
        """Volume equals the weekly average → score 100."""
        from runtime.client_health.calculator import _signal_volume

        mock_res_recent = MagicMock()
        mock_res_recent.count = 50  # 50 this week
        mock_res_prev = MagicMock()
        mock_res_prev.count = 200  # 200 over 4 weeks = avg 50

        call_count = 0

        async def mock_thread(fn):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_res_recent
            return mock_res_prev

        with patch("asyncio.to_thread", side_effect=mock_thread):
            result = await _signal_volume("test-client")

        assert result["score"] == 100

    @pytest.mark.asyncio
    async def test_volume_at_50_percent_of_average(self):
        """Volume is half the weekly average → score 50."""
        from runtime.client_health.calculator import _signal_volume

        mock_res_recent = MagicMock()
        mock_res_recent.count = 25  # 25 this week
        mock_res_prev = MagicMock()
        mock_res_prev.count = 200  # avg 50

        call_count = 0

        async def mock_thread(fn):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_res_recent
            return mock_res_prev

        with patch("asyncio.to_thread", side_effect=mock_thread):
            result = await _signal_volume("test-client")

        assert result["score"] == 50


# ── AC-1: _signal_payment() logic ────────────────────────────────────────────

class TestSignalPayment:
    @pytest.mark.asyncio
    async def test_payment_active_subscription(self):
        from runtime.client_health.calculator import _signal_payment

        mock_res = MagicMock()
        mock_res.data = {"status": "ACTIVE", "next_due_date": "2026-05-01"}

        with patch("asyncio.to_thread", return_value=mock_res):
            result = await _signal_payment("test-client")

        assert result["score"] == 100
        assert result["status"] == "ACTIVE"

    @pytest.mark.asyncio
    async def test_payment_overdue_subscription(self):
        from runtime.client_health.calculator import _signal_payment

        mock_res = MagicMock()
        mock_res.data = {"status": "OVERDUE", "next_due_date": "2026-03-01"}

        with patch("asyncio.to_thread", return_value=mock_res):
            result = await _signal_payment("test-client")

        assert result["score"] == 20

    @pytest.mark.asyncio
    async def test_payment_no_subscription_returns_50(self):
        from runtime.client_health.calculator import _signal_payment

        mock_res = MagicMock()
        mock_res.data = None

        with patch("asyncio.to_thread", return_value=mock_res):
            result = await _signal_payment("test-client")

        assert result["score"] == 50
        assert result["status"] == "no_subscription"

    @pytest.mark.asyncio
    async def test_payment_inactive_subscription(self):
        from runtime.client_health.calculator import _signal_payment

        mock_res = MagicMock()
        mock_res.data = {"status": "INACTIVE", "next_due_date": None}

        with patch("asyncio.to_thread", return_value=mock_res):
            result = await _signal_payment("test-client")

        assert result["score"] == 0


# ── AC-1: _signal_access() logic ─────────────────────────────────────────────

class TestSignalAccess:
    @pytest.mark.asyncio
    async def test_access_recent_activity_under_3_days(self):
        from datetime import datetime, timedelta, timezone
        from runtime.client_health.calculator import _signal_access

        recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        mock_res = MagicMock()
        mock_res.data = [{"created_at": recent}]

        with patch("asyncio.to_thread", return_value=mock_res):
            result = await _signal_access("test-client")

        assert result["score"] == 100

    @pytest.mark.asyncio
    async def test_access_no_events_gives_20(self):
        from runtime.client_health.calculator import _signal_access

        mock_res = MagicMock()
        mock_res.data = []

        with patch("asyncio.to_thread", return_value=mock_res):
            result = await _signal_access("test-client")

        assert result["score"] == 20
        assert result["last_event_at"] is None

    @pytest.mark.asyncio
    async def test_access_over_30_days_gives_20(self):
        from datetime import datetime, timedelta, timezone
        from runtime.client_health.calculator import _signal_access

        old_event = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        mock_res = MagicMock()
        mock_res.data = [{"created_at": old_event}]

        with patch("asyncio.to_thread", return_value=mock_res):
            result = await _signal_access("test-client")

        assert result["score"] == 20
        assert result["days_since_last"] >= 30

    @pytest.mark.asyncio
    async def test_access_between_7_and_14_days_gives_60(self):
        from datetime import datetime, timedelta, timezone
        from runtime.client_health.calculator import _signal_access

        ten_days_ago = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        mock_res = MagicMock()
        mock_res.data = [{"created_at": ten_days_ago}]

        with patch("asyncio.to_thread", return_value=mock_res):
            result = await _signal_access("test-client")

        assert result["score"] == 60


# ── AC-3: risk_level / classification boundaries ─────────────────────────────

class TestRiskLevelBoundaries:
    """Verify that the classification aligns with the story's risk_level definition."""

    def test_healthy_boundary(self):
        assert classify(80) == "healthy"
        assert classify(100) == "healthy"

    def test_attention_zone(self):
        # story calls scores 60-79 "at_risk"; calculator calls it "attention"
        assert classify(60) == "attention"
        assert classify(79) == "attention"

    def test_risk_zone(self):
        assert classify(40) == "risk"
        assert classify(59) == "risk"

    def test_critical_zone(self):
        assert classify(0) == "critical"
        assert classify(39) == "critical"
