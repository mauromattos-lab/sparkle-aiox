"""
Testes unitários — W2-BRAIN-1: Brain Domain Synthesis + Health Dashboard.
"""
from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from runtime.brain.synthesis import update_domain_synthesis, get_brain_health


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _old(days: int = 100) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _chunk(status: str = "approved", ns: str = "general", usage: int = 1) -> dict:
    return {"curation_status": status, "namespace": ns, "created_at": _now(), "usage_count": usage}


# ── update_domain_synthesis ───────────────────────────────────

class TestUpdateDomainSynthesis(unittest.TestCase):
    @patch("runtime.brain.synthesis.supabase")
    def test_no_chunks_returns_false(self, mock_supabase):
        res = MagicMock()
        res.data = []
        (mock_supabase.table.return_value.select.return_value
         .eq.return_value.eq.return_value.is_.return_value
         .order.return_value.limit.return_value.execute.return_value) = res

        self.assertFalse(_run(update_domain_synthesis("test-ns")))

    @patch("runtime.brain.synthesis.supabase")
    @patch("anthropic.Anthropic")
    def test_haiku_empty_returns_false(self, mock_cls, mock_supabase):
        chunks_res = MagicMock()
        chunks_res.data = [{"id": "c1", "content": "x", "source_title": "t", "usage_count": 1}]
        (mock_supabase.table.return_value.select.return_value
         .eq.return_value.eq.return_value.is_.return_value
         .order.return_value.limit.return_value.execute.return_value) = chunks_res

        mock_cls.return_value.messages.create.return_value = MagicMock(content=[MagicMock(text="")])
        self.assertFalse(_run(update_domain_synthesis("test-ns")))

    @patch("runtime.brain.synthesis.supabase")
    @patch("anthropic.Anthropic")
    def test_haiku_exception_returns_false(self, mock_cls, mock_supabase):
        chunks_res = MagicMock()
        chunks_res.data = [{"id": "c1", "content": "x", "source_title": "t", "usage_count": 1}]
        (mock_supabase.table.return_value.select.return_value
         .eq.return_value.eq.return_value.is_.return_value
         .order.return_value.limit.return_value.execute.return_value) = chunks_res

        mock_cls.return_value.messages.create.side_effect = Exception("API error")
        self.assertFalse(_run(update_domain_synthesis("test-ns")))

    @patch("runtime.brain.synthesis.supabase")
    @patch("anthropic.Anthropic")
    def test_insert_when_no_existing(self, mock_cls, mock_supabase):
        chunks_res = MagicMock()
        chunks_res.data = [
            {"id": f"c{i}", "content": f"c {i}", "source_title": f"t{i}", "usage_count": i}
            for i in range(3)
        ]
        synth_res = MagicMock()
        synth_res.data = []
        insert_res = MagicMock()
        insert_res.data = [{"id": "new"}]

        table = mock_supabase.table.return_value
        # chunks query
        (table.select.return_value.eq.return_value.eq.return_value.is_.return_value
         .order.return_value.limit.return_value.execute.return_value) = chunks_res
        # existing synthesis query
        (table.select.return_value.eq.return_value.eq.return_value
         .limit.return_value.execute.return_value) = synth_res
        table.insert.return_value.execute.return_value = insert_res

        mock_cls.return_value.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Síntese gerada pelo Haiku")]
        )

        self.assertTrue(_run(update_domain_synthesis("sparkle-lore")))


# ── get_brain_health ──────────────────────────────────────────

class TestGetBrainHealth(unittest.TestCase):
    def _setup(self, mock_supabase, chunks, stale_count=0, syntheses=None):
        chunks_res = MagicMock()
        chunks_res.data = chunks
        table = mock_supabase.table.return_value
        table.select.return_value.is_.return_value.execute.return_value = chunks_res

        stale_res = MagicMock()
        stale_res.count = stale_count
        (table.select.return_value.eq.return_value.eq.return_value
         .lt.return_value.is_.return_value.execute.return_value) = stale_res

        synth_res = MagicMock()
        synth_res.data = syntheses or []
        table.select.return_value.eq.return_value.execute.return_value = synth_res

    @patch("runtime.brain.synthesis.supabase")
    def test_counts_by_status(self, mock_supabase):
        chunks = [
            _chunk("approved"), _chunk("approved"),
            _chunk("pending"), _chunk("rejected"),
        ]
        self._setup(mock_supabase, chunks)
        result = _run(get_brain_health())

        self.assertEqual(result["total_chunks"], 4)
        self.assertEqual(result["approved_chunks"], 2)
        self.assertEqual(result["pending_chunks"], 1)
        self.assertEqual(result["rejected_chunks"], 1)

    @patch("runtime.brain.synthesis.supabase")
    def test_approval_rate_50pct(self, mock_supabase):
        chunks = [_chunk("approved"), _chunk("approved"), _chunk("pending"), _chunk("pending")]
        self._setup(mock_supabase, chunks)
        result = _run(get_brain_health())
        self.assertEqual(result["approval_rate_percent"], 50.0)

    @patch("runtime.brain.synthesis.supabase")
    def test_stale_count_in_result(self, mock_supabase):
        self._setup(mock_supabase, [], stale_count=7)
        result = _run(get_brain_health())
        self.assertEqual(result["stale_chunks"], 7)

    @patch("runtime.brain.synthesis.supabase")
    def test_alert_when_synthesis_old(self, mock_supabase):
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()
        syntheses = [{"domain": "sparkle-lore", "updated_at": old_ts}]
        self._setup(mock_supabase, [], syntheses=syntheses)
        result = _run(get_brain_health())
        self.assertTrue(any("sparkle-lore" in a for a in result["alerts"]))

    @patch("runtime.brain.synthesis.supabase")
    def test_alert_when_too_many_pending(self, mock_supabase):
        chunks = [_chunk("pending") for _ in range(51)]
        self._setup(mock_supabase, chunks)
        result = _run(get_brain_health())
        self.assertTrue(any("pendentes" in a.lower() or "curadoria" in a.lower() for a in result["alerts"]))

    @patch("runtime.brain.synthesis.supabase")
    def test_namespaces_breakdown(self, mock_supabase):
        chunks = [
            _chunk("approved", ns="sparkle-lore"),
            _chunk("approved", ns="sparkle-lore"),
            _chunk("pending", ns="mauro-personal"),
        ]
        self._setup(mock_supabase, chunks)
        result = _run(get_brain_health())
        ns_names = {ns["namespace"] for ns in result["namespaces"]}
        self.assertIn("sparkle-lore", ns_names)
        self.assertIn("mauro-personal", ns_names)

    @patch("runtime.brain.synthesis.supabase")
    def test_error_returns_error_key(self, mock_supabase):
        mock_supabase.table.side_effect = Exception("DB error")
        result = _run(get_brain_health())
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
