"""
Testes unitários — W2-CLC-2: Weekly Client Report.
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from runtime.client_lifecycle.weekly_report import (
    _calc_horario_pico,
    _calc_variacao,
    _extract_keywords_from_events,
    _current_week_start,
    generate_weekly_report,
    send_weekly_report,
    send_all_weekly_reports,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_event(hour: int, message: str = "") -> dict:
    ts = f"2026-04-07T{hour:02d}:00:00+00:00"
    return {"id": f"ev-{hour}", "event_type": "msg", "payload": {"message": message}, "created_at": ts}


# ── _calc_horario_pico ────────────────────────────────────────

class TestCalcHorarioPico(unittest.TestCase):
    def test_basic_peak(self):
        events = [_make_event(14), _make_event(14), _make_event(9)]
        self.assertEqual(_calc_horario_pico(events), "às 14h")

    def test_single_event(self):
        self.assertEqual(_calc_horario_pico([_make_event(8)]), "às 8h")

    def test_empty(self):
        self.assertEqual(_calc_horario_pico([]), "não identificado")

    def test_missing_created_at(self):
        self.assertEqual(_calc_horario_pico([{"event_type": "msg"}]), "não identificado")

    def test_tie_wins_by_most_common(self):
        events = [_make_event(10), _make_event(10), _make_event(14)]
        self.assertEqual(_calc_horario_pico(events), "às 10h")


# ── _calc_variacao ────────────────────────────────────────────

class TestCalcVariacao(unittest.TestCase):
    def test_growth(self):
        self.assertEqual(_calc_variacao(120, 100), "+20%")

    def test_decline(self):
        self.assertEqual(_calc_variacao(80, 100), "-20%")

    def test_no_change(self):
        self.assertEqual(_calc_variacao(100, 100), "+0%")

    def test_zero_previous(self):
        self.assertEqual(_calc_variacao(10, 0), "+100%")

    def test_zero_both(self):
        self.assertEqual(_calc_variacao(0, 0), "0%")

    def test_rounding(self):
        self.assertEqual(_calc_variacao(133, 100), "+33%")


# ── _extract_keywords_from_events ────────────────────────────

class TestExtractKeywords(unittest.TestCase):
    def test_basic_extraction(self):
        events = [
            _make_event(9, "pedido entrega produto"),
            _make_event(10, "pedido produto rastreamento"),
            _make_event(11, "entrega produto confirmação"),
        ]
        keywords = _extract_keywords_from_events(events, top_n=3)
        self.assertIn("Produto", keywords)

    def test_stopwords_filtered(self):
        events = [_make_event(9, "que onde como quando")]
        self.assertEqual(_extract_keywords_from_events(events, top_n=3), [])

    def test_short_words_filtered(self):
        events = [_make_event(9, "boa oi dia produto pedido")]
        keywords = _extract_keywords_from_events(events, top_n=3)
        self.assertNotIn("boa", [k.lower() for k in keywords])

    def test_empty_events(self):
        self.assertEqual(_extract_keywords_from_events([], top_n=3), [])

    def test_top_n_respected(self):
        events = [_make_event(9, "produto pedido entrega rastreamento cancelamento")] * 5
        keywords = _extract_keywords_from_events(events, top_n=2)
        self.assertLessEqual(len(keywords), 2)


# ── generate_weekly_report ────────────────────────────────────

class TestGenerateWeeklyReport(unittest.TestCase):
    def _client(self, **kw):
        return {
            "id": "uuid-1", "client_id": "c1",
            "business_name": "Confeitaria", "phone_number": "5511999",
            "active": True, **kw,
        }

    @patch("runtime.client_lifecycle.weekly_report._fetch_zenya_client", new_callable=AsyncMock)
    @patch("runtime.client_lifecycle.weekly_report._fetch_events", new_callable=AsyncMock)
    @patch("runtime.client_lifecycle.weekly_report._fetch_health_score", new_callable=AsyncMock)
    @patch("runtime.client_lifecycle.weekly_report._extract_top_topics_haiku", new_callable=AsyncMock)
    def test_report_ok(self, mock_topics, mock_health, mock_events, mock_client):
        mock_client.return_value = self._client()
        mock_events.return_value = [_make_event(14, "produto") for _ in range(15)]
        mock_health.return_value = 75.0
        mock_topics.return_value = ["Produto", "Pedido", "Entrega"]

        result = _run(generate_weekly_report("c1"))

        self.assertFalse(result["skipped"])
        self.assertEqual(result["total_events"], 15)
        self.assertIn("Confeitaria", result["report_text"])
        self.assertIn("15 atendimentos", result["report_text"])
        self.assertIn("às 14h", result["report_text"])

    @patch("runtime.client_lifecycle.weekly_report._fetch_zenya_client", new_callable=AsyncMock)
    @patch("runtime.client_lifecycle.weekly_report._fetch_events", new_callable=AsyncMock)
    @patch("runtime.client_lifecycle.weekly_report._fetch_health_score", new_callable=AsyncMock)
    def test_skip_insufficient(self, mock_health, mock_events, mock_client):
        mock_client.return_value = self._client()
        mock_events.return_value = [_make_event(14) for _ in range(5)]
        mock_health.return_value = 80.0

        result = _run(generate_weekly_report("c1"))
        self.assertTrue(result["skipped"])
        self.assertIn("insuficientes", result["skip_reason"])

    @patch("runtime.client_lifecycle.weekly_report._fetch_zenya_client", new_callable=AsyncMock)
    @patch("runtime.client_lifecycle.weekly_report._fetch_events", new_callable=AsyncMock)
    @patch("runtime.client_lifecycle.weekly_report._fetch_health_score", new_callable=AsyncMock)
    def test_skip_critical_health(self, mock_health, mock_events, mock_client):
        mock_client.return_value = self._client()
        mock_events.return_value = [_make_event(14) for _ in range(20)]
        mock_health.return_value = 20.0

        result = _run(generate_weekly_report("c1"))
        self.assertTrue(result["skipped"])
        self.assertIn("crítico", result["skip_reason"])

    @patch("runtime.client_lifecycle.weekly_report._fetch_zenya_client", new_callable=AsyncMock)
    def test_skip_client_not_found(self, mock_client):
        mock_client.return_value = None
        result = _run(generate_weekly_report("x"))
        self.assertTrue(result["skipped"])
        self.assertIn("não encontrado", result["skip_reason"])


# ── send_weekly_report ────────────────────────────────────────

class TestSendWeeklyReport(unittest.TestCase):
    @patch("runtime.client_lifecycle.weekly_report._already_sent_this_week", new_callable=AsyncMock)
    @patch("runtime.client_lifecycle.weekly_report.generate_weekly_report", new_callable=AsyncMock)
    @patch("runtime.client_lifecycle.weekly_report._log_send", new_callable=AsyncMock)
    def test_dry_run_does_not_send(self, mock_log, mock_gen, mock_sent):
        mock_sent.return_value = False
        mock_gen.return_value = {
            "skipped": False, "total_events": 20,
            "report_text": "Relatório teste", "phone_number": "5511",
            "business_name": "X", "week_start": "2026-04-07",
        }
        result = _run(send_weekly_report("c1", dry_run=True))
        self.assertFalse(result["sent"])
        self.assertTrue(result["dry_run"])
        mock_log.assert_called_once()

    @patch("runtime.client_lifecycle.weekly_report._already_sent_this_week", new_callable=AsyncMock)
    def test_anti_spam_blocks_duplicate(self, mock_sent):
        mock_sent.return_value = True
        result = _run(send_weekly_report("c1", dry_run=False))
        self.assertFalse(result["sent"])
        self.assertIn("já enviado", result["skip_reason"])


# ── send_all_weekly_reports ───────────────────────────────────

class TestSendAllWeeklyReports(unittest.TestCase):
    @patch("runtime.client_lifecycle.weekly_report._fetch_active_zenya_clients", new_callable=AsyncMock)
    def test_no_clients_returns_empty(self, mock_clients):
        mock_clients.return_value = []
        result = _run(send_all_weekly_reports(dry_run=True))
        self.assertEqual(result["total_clients"], 0)

    @patch("runtime.client_lifecycle.weekly_report._fetch_active_zenya_clients", new_callable=AsyncMock)
    @patch("runtime.client_lifecycle.weekly_report.send_weekly_report", new_callable=AsyncMock)
    def test_iterates_all_clients(self, mock_send, mock_clients):
        mock_clients.return_value = [
            {"client_id": "c1", "id": "u1"},
            {"client_id": "c2", "id": "u2"},
        ]
        mock_send.return_value = {"sent": True, "dry_run": True, "report": {}}
        result = _run(send_all_weekly_reports(dry_run=True))
        self.assertEqual(result["total_clients"], 2)
        self.assertEqual(result["sent"], 2)

    @patch("runtime.client_lifecycle.weekly_report._fetch_active_zenya_clients", new_callable=AsyncMock)
    @patch("runtime.client_lifecycle.weekly_report.send_weekly_report", new_callable=AsyncMock)
    def test_failure_in_one_continues(self, mock_send, mock_clients):
        mock_clients.return_value = [{"client_id": "c1"}, {"client_id": "c2"}]
        mock_send.side_effect = [
            Exception("falha de rede"),
            {"sent": True, "dry_run": False, "report": {}},
        ]
        result = _run(send_all_weekly_reports(dry_run=False))
        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["failed"], 1)


# ── _current_week_start ───────────────────────────────────────

class TestCurrentWeekStart(unittest.TestCase):
    def test_returns_monday(self):
        self.assertEqual(_current_week_start().weekday(), 0)


if __name__ == "__main__":
    unittest.main()
