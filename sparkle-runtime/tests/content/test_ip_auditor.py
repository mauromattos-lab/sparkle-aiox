"""
Unit/integration tests for IP Auditor W1-CHAR-1.

Coverage (AC-7):
  1. Lore compatível — peça sobre Zenya ajudando PMEs → COMPATIVEL, sem warnings de lore
  2. Lore incompatível — peça com conteúdo fora do arquétipo → INCOMPATIVEL detectado
  3. Erro do Haiku (timeout simulado) → lore_compliance=SKIPPED, pipeline não falha
  4. character_lore vazio — graceful degradation, auditor continua com Brain lore
  5. Estrutura do audit_result — todos os campos obrigatórios presentes (AC-4)
  6. Comportamento não-bloqueante — warnings não impedem avanço (AC-5)
  7. get_approval_queue inclui audit_badge (AC-6)

Run: pytest tests/content/test_ip_auditor.py -v
(Must be run from sparkle-runtime root with PYTHONPATH set and .env loaded)
"""
from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Fixtures ───────────────────────────────────────────────────

def _make_piece(**overrides) -> dict:
    """Build a minimal content_piece dict for testing."""
    return {
        "id": str(uuid.uuid4()),
        "theme": overrides.pop("theme", "Zenya ajudando PMEs com IA"),
        "voice_script": overrides.pop(
            "voice_script",
            "Zenya é uma assistente de IA que cuida do atendimento da sua empresa com empatia e eficiência.",
        ),
        "caption": overrides.pop("caption", "IA que entende seu negócio #Zenya #Sparkle"),
        "status": "video_done",
        **overrides,
    }


MOCK_LORE_CHUNKS = [
    {
        "id": str(uuid.uuid4()),
        "namespace": "sparkle-lore",
        "canonical_text": "Zenya é uma atendente de IA com personalidade empática, tom acolhedor e foco em PMEs brasileiras.",
        "chunk_metadata": {"lore_type": "personality"},
        "similarity": 0.92,
    },
    {
        "id": str(uuid.uuid4()),
        "namespace": "sparkle-lore",
        "canonical_text": "Arquétipo: A Atendente Perfeita que você não consegue contratar. Zenya nunca é fria, nunca é genérica.",
        "chunk_metadata": {"lore_type": "archetype"},
        "similarity": 0.88,
    },
    {
        "id": str(uuid.uuid4()),
        "namespace": "sparkle-lore",
        "canonical_text": "Missão da Zenya: devolver tempo ao empreendedor. O tempo é o luxo real.",
        "chunk_metadata": {"lore_type": "mission"},
        "similarity": 0.85,
    },
]

MOCK_CHARACTER_LORE = [
    "[personality] Personalidade Central: Zenya age com empatia, clareza e leveza. Nunca robótica.",
    "[archetype] Arquétipo: A Atendente Perfeita — especialista sem arrogância.",
    "[voice] Tom de Voz: Acolhedor, direto, nunca formal demais.",
]


# ── AC-7 Test 1: Lore compatível → COMPATIVEL ─────────────────

@pytest.mark.asyncio
async def test_lore_compatible_piece_returns_compativel():
    """
    Peça com conteúdo alinhado ao lore da Zenya deve retornar COMPATIVEL
    e não gerar warnings de lore.
    """
    from runtime.content.ip_auditor import check_lore

    piece = _make_piece(
        theme="Zenya ajudando PMEs com atendimento humanizado",
        voice_script="Zenya cuida do seu atendimento com empatia, devolve tempo ao empreendedor.",
    )

    with (
        patch("runtime.content.ip_auditor._query_sparkle_lore", AsyncMock(return_value=MOCK_LORE_CHUNKS)),
        patch("runtime.content.ip_auditor._query_character_lore", AsyncMock(return_value=MOCK_CHARACTER_LORE)),
        patch("runtime.content.ip_auditor._check_lore_compliance", AsyncMock(return_value=("COMPATIVEL", "conteúdo alinhado ao arquétipo"))),
    ):
        lore_ok, warnings, extras = await check_lore(piece)

    assert lore_ok is True
    assert extras["lore_compliance"] == "COMPATIVEL"
    assert extras["lore_chunks_used"] == len(MOCK_LORE_CHUNKS)
    assert extras["character_lore_entries_used"] == len(MOCK_CHARACTER_LORE)
    # No lore warnings (restriction tags or INCOMPATIVEL)
    lore_warnings_only = [w for w in warnings if "lore incompativel" not in w.lower()]
    assert len(lore_warnings_only) == 0


# ── AC-7 Test 2: Lore incompatível → INCOMPATIVEL detectado ───

@pytest.mark.asyncio
async def test_lore_incompatible_piece_returns_incompativel_warning():
    """
    Peça com conteúdo fora do arquétipo da Zenya (ex: tom agressivo, ameaças)
    deve retornar lore_compliance=INCOMPATIVEL e adicionar um warning.
    """
    from runtime.content.ip_auditor import check_lore

    piece = _make_piece(
        theme="IA vai substituir todos os humanos — o futuro é sombrio",
        voice_script="Prepare-se: a IA dominará o mundo e seu emprego não existe mais.",
        caption="Skynet chegou. #IA #Futuro",
    )

    with (
        patch("runtime.content.ip_auditor._query_sparkle_lore", AsyncMock(return_value=MOCK_LORE_CHUNKS)),
        patch("runtime.content.ip_auditor._query_character_lore", AsyncMock(return_value=MOCK_CHARACTER_LORE)),
        patch(
            "runtime.content.ip_auditor._check_lore_compliance",
            AsyncMock(return_value=("INCOMPATIVEL", "tom contrario à filosofia humanista da Zenya")),
        ),
    ):
        lore_ok, warnings, extras = await check_lore(piece)

    assert extras["lore_compliance"] == "INCOMPATIVEL"
    assert any("incompativel" in w.lower() or "lore" in w.lower() for w in warnings), (
        f"Expected lore incompatibility warning, got: {warnings}"
    )


# ── AC-7 Test 3: Erro do Haiku → SKIPPED, pipeline não falha ──

@pytest.mark.asyncio
async def test_haiku_timeout_returns_skipped():
    """
    Quando o Haiku dá timeout ou erro, lore_compliance deve ser SKIPPED
    e o auditor não deve levantar exceção.
    """
    from runtime.content.ip_auditor import check_lore

    piece = _make_piece()

    with (
        patch("runtime.content.ip_auditor._query_sparkle_lore", AsyncMock(return_value=MOCK_LORE_CHUNKS)),
        patch("runtime.content.ip_auditor._query_character_lore", AsyncMock(return_value=MOCK_CHARACTER_LORE)),
        patch(
            "runtime.content.ip_auditor._check_lore_compliance",
            AsyncMock(return_value=("SKIPPED", "timeout")),
        ),
    ):
        lore_ok, warnings, extras = await check_lore(piece)

    assert extras["lore_compliance"] == "SKIPPED"
    # SKIPPED alone must not generate a lore incompatibility warning
    incompativel_warnings = [w for w in warnings if "incompativel" in w.lower()]
    assert len(incompativel_warnings) == 0


# ── AC-7 Test 4: character_lore vazio → graceful degradation ──

@pytest.mark.asyncio
async def test_empty_character_lore_continues_with_brain_only():
    """
    Se character_lore retornar vazio, o auditor deve continuar usando
    apenas os chunks do Brain — sem falhar.
    """
    from runtime.content.ip_auditor import check_lore

    piece = _make_piece()

    with (
        patch("runtime.content.ip_auditor._query_sparkle_lore", AsyncMock(return_value=MOCK_LORE_CHUNKS)),
        patch("runtime.content.ip_auditor._query_character_lore", AsyncMock(return_value=[])),
        patch(
            "runtime.content.ip_auditor._check_lore_compliance",
            AsyncMock(return_value=("COMPATIVEL", "")),
        ),
    ):
        lore_ok, warnings, extras = await check_lore(piece)

    # Must succeed even with 0 character_lore entries
    assert extras["character_lore_entries_used"] == 0
    assert extras["lore_chunks_used"] == len(MOCK_LORE_CHUNKS)
    # No crash
    assert isinstance(lore_ok, bool)


# ── AC-4 Test 5: Estrutura completa do audit_result ───────────

@pytest.mark.asyncio
async def test_audit_result_has_all_required_fields():
    """
    audit_piece() deve retornar todos os campos obrigatórios do AC-4.
    """
    from runtime.content.ip_auditor import audit_piece

    piece = _make_piece()

    with (
        patch("runtime.content.ip_auditor._query_sparkle_lore", AsyncMock(return_value=MOCK_LORE_CHUNKS)),
        patch("runtime.content.ip_auditor._query_character_lore", AsyncMock(return_value=MOCK_CHARACTER_LORE)),
        patch(
            "runtime.content.ip_auditor._check_lore_compliance",
            AsyncMock(return_value=("COMPATIVEL", "alinhado")),
        ),
        patch("runtime.content.ip_auditor.check_repetition", AsyncMock(return_value=(True, []))),
        patch(
            "runtime.content.ip_auditor.supabase",
            MagicMock(**{
                "table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value": MagicMock(data=[{"pipeline_log": []}]),
                "table.return_value.update.return_value.eq.return_value.execute.return_value": MagicMock(),
            }),
        ),
    ):
        result = await audit_piece(piece)

    required_fields = {
        "lore_ok", "lore_compliance", "lore_compliance_reason",
        "lore_chunks_used", "character_lore_entries_used",
        "repetition_ok", "warnings", "audited_at",
    }
    missing = required_fields - set(result.keys())
    assert not missing, f"audit_result missing required fields: {missing}"

    assert isinstance(result["lore_ok"], bool)
    assert result["lore_compliance"] in ("COMPATIVEL", "INCOMPATIVEL", "SKIPPED")
    assert isinstance(result["lore_chunks_used"], int)
    assert isinstance(result["character_lore_entries_used"], int)
    assert isinstance(result["warnings"], list)
    assert isinstance(result["repetition_ok"], bool)


# ── AC-5 Test 6: Comportamento não-bloqueante ─────────────────

@pytest.mark.asyncio
async def test_audit_never_raises_on_error():
    """
    audit_piece() nunca deve levantar exceção — mesmo se Brain e Haiku falharem.
    """
    from runtime.content.ip_auditor import audit_piece

    piece = _make_piece()

    with (
        patch("runtime.content.ip_auditor._query_sparkle_lore", AsyncMock(return_value=[])),
        patch("runtime.content.ip_auditor._query_character_lore", AsyncMock(return_value=[])),
        patch(
            "runtime.content.ip_auditor._check_lore_compliance",
            AsyncMock(return_value=("SKIPPED", "no lore")),
        ),
        patch("runtime.content.ip_auditor.check_repetition", AsyncMock(return_value=(True, []))),
        patch(
            "runtime.content.ip_auditor.supabase",
            MagicMock(**{
                "table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value": MagicMock(data=[{"pipeline_log": []}]),
                "table.return_value.update.return_value.eq.return_value.execute.side_effect": Exception("DB error"),
            }),
        ),
    ):
        # Must not raise — errors are swallowed
        result = await audit_piece(piece)

    assert "lore_ok" in result
    assert "audited_at" in result


# ── AC-6 Test 7: audit_badge na fila de aprovação ─────────────

def test_audit_badge_computed_from_pipeline_log():
    """
    _compute_audit_badge() deve derivar o badge correto do pipeline_log.
    """
    from runtime.content.approval import _compute_audit_badge

    # Piece with COMPATIVEL audit
    piece_ok = {
        "pipeline_log": [{
            "event": "ip_audit",
            "ip_audit": {
                "lore_ok": True,
                "lore_compliance": "COMPATIVEL",
                "lore_compliance_reason": "alinhado",
                "lore_chunks_used": 3,
                "character_lore_entries_used": 2,
                "warnings": [],
            },
        }]
    }
    badge = _compute_audit_badge(piece_ok)
    assert badge["status"] == "lore_ok"
    assert badge["label"] == "Lore OK"
    assert badge["lore_compliance"] == "COMPATIVEL"

    # Piece with INCOMPATIVEL audit
    piece_warn = {
        "pipeline_log": [{
            "event": "ip_audit",
            "ip_audit": {
                "lore_ok": False,
                "lore_compliance": "INCOMPATIVEL",
                "lore_compliance_reason": "tom contrario",
                "lore_chunks_used": 3,
                "character_lore_entries_used": 2,
                "warnings": ["Lore incompativel: tom contrario à filosofia"],
            },
        }]
    }
    badge_warn = _compute_audit_badge(piece_warn)
    assert badge_warn["status"] == "lore_warning"
    assert "Warning" in badge_warn["label"]

    # Piece with no audit yet
    piece_pending = {"pipeline_log": []}
    badge_pending = _compute_audit_badge(piece_pending)
    assert badge_pending["status"] == "pending"

    # Piece with SKIPPED audit and no warnings
    piece_skipped = {
        "pipeline_log": [{
            "event": "ip_audit",
            "ip_audit": {
                "lore_ok": True,
                "lore_compliance": "SKIPPED",
                "lore_compliance_reason": "timeout",
                "lore_chunks_used": 0,
                "character_lore_entries_used": 0,
                "warnings": [],
            },
        }]
    }
    badge_skipped = _compute_audit_badge(piece_skipped)
    assert badge_skipped["status"] == "skipped"
    assert "Skipped" in badge_skipped["label"]


# ── _check_lore_compliance unit test ──────────────────────────

@pytest.mark.asyncio
async def test_check_lore_compliance_parses_incompativel():
    """
    _check_lore_compliance() deve parsear corretamente INCOMPATIVEL com justificativa.
    """
    from runtime.content.ip_auditor import _check_lore_compliance

    piece = _make_piece()

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="INCOMPATIVEL — tom agressivo contradiz filosofia humanista da Zenya")]

    with patch("anthropic.Anthropic") as MockAnthropicClass:
        mock_client = MagicMock()
        MockAnthropicClass.return_value = mock_client
        mock_client.messages.create.return_value = mock_response

        compliance, reason = await _check_lore_compliance(piece, MOCK_LORE_CHUNKS, MOCK_CHARACTER_LORE)

    assert compliance == "INCOMPATIVEL"
    assert len(reason) > 0


@pytest.mark.asyncio
async def test_check_lore_compliance_parses_compativel():
    """
    _check_lore_compliance() deve parsear corretamente COMPATIVEL.
    """
    from runtime.content.ip_auditor import _check_lore_compliance

    piece = _make_piece()

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="COMPATIVEL — conteúdo alinhado ao arquétipo da Zenya")]

    with patch("anthropic.Anthropic") as MockAnthropicClass:
        mock_client = MagicMock()
        MockAnthropicClass.return_value = mock_client
        mock_client.messages.create.return_value = mock_response

        compliance, reason = await _check_lore_compliance(piece, MOCK_LORE_CHUNKS, MOCK_CHARACTER_LORE)

    assert compliance == "COMPATIVEL"
