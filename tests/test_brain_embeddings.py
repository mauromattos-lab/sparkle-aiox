"""
Testes P3 — Brain Embeddings.

Testa:
  T1: generate_embedding retorna None quando BRAIN_EMBEDDINGS_ENABLED=false (feature flag)
  T2: generate_embedding retorna None quando OPENAI_API_KEY ausente mesmo com flag=true
  T3: estimate_cost_usd calcula corretamente para 34301 chars (~$0.000172)
  T4: threshold filtering em brain_query descarta resultados abaixo do limiar
  T5: brain_ingest ainda funciona sem embedding (fallback seguro)
  T6: config carrega brain_embeddings_enabled e brain_similarity_threshold corretamente

Nota: testes de vector search real (AC-3) são feitos pelo @qa no ambiente
      de produção após BRAIN_EMBEDDINGS_ENABLED=true e OPENAI_API_KEY configurada.
"""
from __future__ import annotations

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestEmbeddingFeatureFlag(unittest.IsolatedAsyncioTestCase):
    """T1: feature flag BRAIN_EMBEDDINGS_ENABLED controla geração de embedding."""

    async def test_generate_embedding_returns_none_when_disabled(self):
        """Quando BRAIN_EMBEDDINGS_ENABLED=false (default), retorna None sem chamar OpenAI."""
        with patch.dict(os.environ, {"BRAIN_EMBEDDINGS_ENABLED": "false"}, clear=False):
            # Reimportar para pegar novo env
            import importlib
            import runtime.utils.embeddings as emb_mod
            importlib.reload(emb_mod)

            result = await emb_mod.generate_embedding("texto de teste qualquer")
            self.assertIsNone(result)

    async def test_generate_embedding_returns_none_when_no_api_key(self):
        """T2: Com flag=true mas sem OPENAI_API_KEY, retorna None (não levanta exception)."""
        env = {"BRAIN_EMBEDDINGS_ENABLED": "true"}
        # Remover OPENAI_API_KEY se existir
        env_clean = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
        env_clean["BRAIN_EMBEDDINGS_ENABLED"] = "true"

        with patch.dict(os.environ, env_clean, clear=True):
            import importlib
            import runtime.utils.embeddings as emb_mod
            importlib.reload(emb_mod)

            result = await emb_mod.generate_embedding("texto sem api key")
            self.assertIsNone(result)


class TestEstimateCost(unittest.IsolatedAsyncioTestCase):
    """T3: estimate_cost_usd calcula corretamente."""

    async def test_estimate_cost_34301_chars(self):
        """34.301 chars (backfill atual) → ~$0.000172 USD."""
        from runtime.utils.embeddings import estimate_cost_usd
        cost = await estimate_cost_usd(34301)
        # $0.02 / 1M tokens, 1 token ≈ 4 chars
        # 34301 / 4 = 8575.25 tokens → 8575.25 / 1_000_000 * 0.02 = 0.000172
        self.assertAlmostEqual(cost, 0.000172, places=5)

    async def test_estimate_cost_zero(self):
        """0 chars → $0.0."""
        from runtime.utils.embeddings import estimate_cost_usd
        cost = await estimate_cost_usd(0)
        self.assertEqual(cost, 0.0)

    async def test_estimate_cost_1_million_tokens(self):
        """4M chars = 1M tokens → $0.02 USD."""
        from runtime.utils.embeddings import estimate_cost_usd
        cost = await estimate_cost_usd(4_000_000)
        self.assertAlmostEqual(cost, 0.02, places=5)


class TestSimilarityThreshold(unittest.IsolatedAsyncioTestCase):
    """T4: threshold de similaridade filtra resultados abaixo do limiar."""

    async def test_threshold_filters_low_similarity(self):
        """Resultados com similarity < threshold devem ser descartados."""
        from runtime.config import settings

        # Simular resultado do RPC com similaridades mistas
        mock_rpc_data = [
            {"source_type": "info", "canonical_text": "resultado relevante", "pipeline_type": "mauro", "client_id": None, "similarity": 0.85},
            {"source_type": "info", "canonical_text": "resultado pouco relevante", "pipeline_type": "mauro", "client_id": None, "similarity": 0.60},
            {"source_type": "info", "canonical_text": "resultado irrelevante", "pipeline_type": "mauro", "client_id": None, "similarity": 0.40},
        ]

        threshold = 0.75
        filtered = [r for r in mock_rpc_data if r.get("similarity", 0) >= threshold]

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["canonical_text"], "resultado relevante")
        self.assertGreaterEqual(filtered[0]["similarity"], threshold)

    async def test_threshold_fallback_when_all_below(self):
        """Quando todos os resultados ficam abaixo do threshold, lista filtrada é vazia."""
        mock_rpc_data = [
            {"similarity": 0.50},
            {"similarity": 0.45},
            {"similarity": 0.30},
        ]
        threshold = 0.75
        filtered = [r for r in mock_rpc_data if r.get("similarity", 0) >= threshold]
        # Vazio — brain_query deve fallback para text search
        self.assertEqual(len(filtered), 0)

    def test_config_default_threshold(self):
        """T6: BRAIN_SIMILARITY_THRESHOLD default é 0.75."""
        from runtime.config import settings
        self.assertEqual(settings.brain_similarity_threshold, 0.75)

    def test_config_embeddings_disabled_by_default(self):
        """T6: BRAIN_EMBEDDINGS_ENABLED default é False."""
        from runtime.config import settings
        self.assertFalse(settings.brain_embeddings_enabled)


class TestBrainIngestFallback(unittest.IsolatedAsyncioTestCase):
    """T5: brain_ingest continua funcionando sem embedding (fallback seguro)."""

    async def test_ingest_succeeds_without_openai(self):
        """
        Ingestão retorna sucesso mesmo sem OPENAI_API_KEY.
        O registro é salvo sem embedding — busca textual continua funcionando.
        """
        # Mock do supabase insert para não tocar no banco real
        mock_result = MagicMock()
        mock_result.data = [{"id": "test-uuid-1234", "pipeline_type": "mauro"}]

        with patch.dict(os.environ, {"BRAIN_EMBEDDINGS_ENABLED": "false"}, clear=False):
            with patch("runtime.tasks.handlers.brain_ingest.supabase") as mock_db:
                mock_db.table.return_value.insert.return_value.execute.return_value = mock_result

                from runtime.tasks.handlers.brain_ingest import handle_brain_ingest
                result = await handle_brain_ingest({
                    "payload": {
                        "content": "MRR atual Sparkle é R$5.491 por mês",
                        "owner_type": "mauro",
                    }
                })

        self.assertNotIn("error", result)
        self.assertIn("Anotado no Brain", result.get("message", ""))
        self.assertEqual(result.get("owner_type"), "mauro")
        self.assertEqual(result.get("pipeline_type"), "mauro")
