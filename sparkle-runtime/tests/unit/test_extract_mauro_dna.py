"""
Testes unitários — W2-FRIDAY-1: extract_mauro_dna.
"""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from runtime.tasks.handlers.extract_mauro_dna import (
    extract_mauro_dna,
    handle_extract_mauro_dna,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_conv(role: str, content: str, day: str = "2026-04-07") -> dict:
    return {"role": role, "content": content, "created_at": f"{day}T10:00:00+00:00"}


def _haiku_resp(extracted: dict) -> MagicMock:
    resp = MagicMock()
    resp.content = [MagicMock(text=json.dumps(extracted))]
    return resp


_EMPTY = {cat: [] for cat in
          ["valores", "preferencias", "cultura_pop", "tom_comunicacao",
           "pilares_pessoais", "visao_negocio", "gatilhos_atencao"]}


# ── Sem conversas ─────────────────────────────────────────────

class TestNoConversations(unittest.TestCase):
    @patch("runtime.tasks.handlers.extract_mauro_dna.supabase")
    def test_returns_empty_message(self, mock_supabase):
        res = MagicMock()
        res.data = []
        (mock_supabase.table.return_value.select.return_value
         .is_.return_value.gte.return_value.order.return_value
         .limit.return_value.execute.return_value) = res

        result = _run(extract_mauro_dna(days_back=7))
        self.assertEqual(result["entries_extracted"], 0)
        self.assertIn("sem conversas", result.get("message", ""))


# ── Extração e persistência ───────────────────────────────────

class TestExtraction(unittest.TestCase):
    def _setup_supabase(self, mock_supabase, conversations):
        conv_res = MagicMock()
        conv_res.data = conversations
        (mock_supabase.table.return_value.select.return_value
         .is_.return_value.gte.return_value.order.return_value
         .limit.return_value.execute.return_value) = conv_res

        # existing check → vazio (sempre insert)
        exist_res = MagicMock()
        exist_res.data = []
        (mock_supabase.table.return_value.select.return_value
         .eq.return_value.eq.return_value.limit.return_value
         .execute.return_value) = exist_res

        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "x"}])

    @patch("runtime.tasks.handlers.extract_mauro_dna.supabase")
    @patch("anthropic.Anthropic")
    def test_extracts_entries(self, mock_cls, mock_supabase):
        self._setup_supabase(mock_supabase, [
            _make_conv("user", "Valorizo muito a prosperidade"),
        ])
        extracted = {**_EMPTY, "valores": [
            {"key": "prosperidade", "content": "Mauro valoriza prosperidade.", "confidence": 0.9},
        ]}
        mock_cls.return_value.messages.create.return_value = _haiku_resp(extracted)

        result = _run(extract_mauro_dna(days_back=7))
        self.assertEqual(result["entries_extracted"], 1)
        self.assertIn("valores", result["categories"])

    @patch("runtime.tasks.handlers.extract_mauro_dna.supabase")
    @patch("anthropic.Anthropic")
    def test_filters_low_confidence(self, mock_cls, mock_supabase):
        self._setup_supabase(mock_supabase, [
            _make_conv("user", "Gosto de filmes"),
        ])
        extracted = {**_EMPTY, "cultura_pop": [
            {"key": "cinema", "content": "Aprecia cinema.", "confidence": 0.9},
            {"key": "baixa", "content": "Talvez goste.", "confidence": 0.4},  # < 0.6 → ignorado
        ]}
        mock_cls.return_value.messages.create.return_value = _haiku_resp(extracted)

        result = _run(extract_mauro_dna(days_back=7))
        self.assertEqual(result["entries_extracted"], 1)
        keys = [e["key"] for e in result["entries"]]
        self.assertIn("cinema", keys)
        self.assertNotIn("baixa", keys)

    @patch("runtime.tasks.handlers.extract_mauro_dna.supabase")
    @patch("anthropic.Anthropic")
    def test_json_parse_error_graceful(self, mock_cls, mock_supabase):
        self._setup_supabase(mock_supabase, [_make_conv("user", "Algo relevante aqui")])
        resp = MagicMock()
        resp.content = [MagicMock(text="isso não é json")]
        mock_cls.return_value.messages.create.return_value = resp

        result = _run(extract_mauro_dna(days_back=7))
        self.assertEqual(result["entries_extracted"], 0)
        self.assertIn("JSON", result.get("error", ""))

    @patch("runtime.tasks.handlers.extract_mauro_dna.supabase")
    @patch("anthropic.Anthropic")
    def test_markdown_fences_stripped(self, mock_cls, mock_supabase):
        self._setup_supabase(mock_supabase, [_make_conv("user", "Prefiro direto")])
        payload = {**_EMPTY, "preferencias": [
            {"key": "direto", "content": "Prefere direto.", "confidence": 0.8}
        ]}
        resp = MagicMock()
        resp.content = [MagicMock(text=f"```json\n{json.dumps(payload)}\n```")]
        mock_cls.return_value.messages.create.return_value = resp

        result = _run(extract_mauro_dna(days_back=7))
        self.assertEqual(result["entries_extracted"], 1)

    @patch("runtime.tasks.handlers.extract_mauro_dna.supabase")
    @patch("anthropic.Anthropic")
    def test_short_messages_skipped(self, mock_cls, mock_supabase):
        """Mensagens < 5 chars não vão para o Haiku."""
        self._setup_supabase(mock_supabase, [
            _make_conv("user", "ok"),
            _make_conv("user", "sim"),
            _make_conv("user", "Esta mensagem é longa o suficiente"),
        ])
        mock_cls.return_value.messages.create.return_value = _haiku_resp(_EMPTY)
        result = _run(extract_mauro_dna(days_back=7))
        self.assertNotIn("error", result)

    @patch("runtime.tasks.handlers.extract_mauro_dna.supabase")
    @patch("anthropic.Anthropic")
    def test_all_empty_categories(self, mock_cls, mock_supabase):
        self._setup_supabase(mock_supabase, [_make_conv("user", "Olá Friday como vai")])
        mock_cls.return_value.messages.create.return_value = _haiku_resp(_EMPTY)

        result = _run(extract_mauro_dna(days_back=7))
        self.assertEqual(result["entries_extracted"], 0)
        self.assertEqual(result["entries"], [])


# ── handle_extract_mauro_dna ──────────────────────────────────

class TestHandleEntryPoint(unittest.TestCase):
    @patch("runtime.tasks.handlers.extract_mauro_dna.extract_mauro_dna", new_callable=AsyncMock)
    def test_passes_days_back(self, mock_fn):
        mock_fn.return_value = {"entries_extracted": 0, "categories": {}, "entries": []}
        _run(handle_extract_mauro_dna({"payload": {"days_back": 14}}))
        mock_fn.assert_called_once_with(days_back=14)

    @patch("runtime.tasks.handlers.extract_mauro_dna.extract_mauro_dna", new_callable=AsyncMock)
    def test_default_days_back(self, mock_fn):
        mock_fn.return_value = {"entries_extracted": 0, "categories": {}, "entries": []}
        _run(handle_extract_mauro_dna({"payload": {}}))
        mock_fn.assert_called_once_with(days_back=7)


if __name__ == "__main__":
    unittest.main()
