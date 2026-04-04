"""
Unit tests for Brain Namespace Resolution (B3-05).

Tests namespace resolution from URLs, file types, metadata overrides,
normalization, and fallback behavior.
"""
from __future__ import annotations

import pytest

from runtime.brain.namespace import resolve_namespace, _normalize


# ── _normalize tests ────────────────────────────────────────────────────────

def test_normalize_lowercase():
    assert _normalize("YouTube") == "youtube"


def test_normalize_spaces_to_underscore():
    assert _normalize("my namespace") == "my_namespace"


def test_normalize_special_chars():
    assert _normalize("client@#dna!") == "client_dna"


def test_normalize_multiple_underscores():
    assert _normalize("too___many___underscores") == "too_many_underscores"


def test_normalize_empty_string():
    assert _normalize("") == "general"


def test_normalize_only_special_chars():
    assert _normalize("@#$%") == "general"


# ── Explicit namespace override ─────────────────────────────────────────────

def test_explicit_namespace_in_metadata():
    result = resolve_namespace(metadata={"namespace": "custom_ns"})
    assert result == "custom_ns"


def test_explicit_namespace_with_spaces():
    result = resolve_namespace(metadata={"namespace": "My Custom Namespace"})
    assert result == "my_custom_namespace"


def test_explicit_namespace_empty_string_ignored():
    result = resolve_namespace(metadata={"namespace": ""})
    # Empty string should be ignored, fallback to other logic
    assert result == "general"


def test_explicit_namespace_whitespace_ignored():
    result = resolve_namespace(metadata={"namespace": "   "})
    assert result == "general"


# ── Source type mapping ─────────────────────────────────────────────────────

def test_source_type_youtube():
    result = resolve_namespace(metadata={"source_type": "youtube"})
    assert result == "youtube"


def test_source_type_web_url():
    result = resolve_namespace(metadata={"source_type": "web_url"})
    assert result == "web"


def test_source_type_conversation_summary():
    result = resolve_namespace(metadata={"source_type": "conversation_summary"})
    assert result == "conversation"


def test_source_type_weekly_digest():
    result = resolve_namespace(metadata={"source_type": "weekly_digest"})
    assert result == "conversation"


def test_source_type_client_dna():
    result = resolve_namespace(metadata={"source_type": "client_dna"})
    assert result == "client_dna"


def test_source_type_insight():
    result = resolve_namespace(metadata={"source_type": "insight"})
    assert result == "insight"


def test_source_type_narrative():
    result = resolve_namespace(metadata={"source_type": "narrative"})
    assert result == "insight"


# ── File upload refinement ──────────────────────────────────────────────────

def test_file_upload_pdf():
    result = resolve_namespace(metadata={"source_type": "file_upload", "file_extension": ".pdf"})
    assert result == "file_pdf"


def test_file_upload_csv():
    result = resolve_namespace(metadata={"source_type": "file_upload", "file_extension": ".csv"})
    assert result == "file_csv"


def test_file_upload_txt():
    result = resolve_namespace(metadata={"source_type": "file_upload", "file_extension": ".txt"})
    assert result == "file_text"


def test_file_upload_md():
    result = resolve_namespace(metadata={"source_type": "file_upload", "file_extension": ".md"})
    assert result == "file_text"


def test_file_upload_unknown_extension():
    result = resolve_namespace(metadata={"source_type": "file_upload", "file_extension": ".docx"})
    assert result == "file_text"  # fallback for file type


def test_file_upload_no_extension():
    result = resolve_namespace(metadata={"source_type": "file_upload"})
    assert result == "file_text"  # fallback for file type


# ── URL-based detection ─────────────────────────────────────────────────────

def test_youtube_url_full():
    result = resolve_namespace(source_url="https://www.youtube.com/watch?v=abc123")
    assert result == "youtube"


def test_youtube_url_short():
    result = resolve_namespace(source_url="https://youtu.be/abc123")
    assert result == "youtube"


def test_youtube_url_case_insensitive():
    result = resolve_namespace(source_url="https://YOUTUBE.COM/watch?v=x")
    assert result == "youtube"


def test_non_youtube_url():
    result = resolve_namespace(source_url="https://example.com/article")
    assert result == "general"


# ── file_type parameter as extension ────────────────────────────────────────

def test_file_type_pdf():
    result = resolve_namespace(file_type=".pdf")
    assert result == "file_pdf"


def test_file_type_csv():
    result = resolve_namespace(file_type=".csv")
    assert result == "file_csv"


def test_file_type_unknown():
    result = resolve_namespace(file_type=".xlsx")
    assert result == "file_text"


# ── file_type as source_type string ─────────────────────────────────────────

def test_file_type_as_source_type():
    result = resolve_namespace(file_type="youtube")
    assert result == "youtube"


# ── Fallback ────────────────────────────────────────────────────────────────

def test_no_args_returns_general():
    assert resolve_namespace() == "general"


def test_none_args_returns_general():
    assert resolve_namespace(source_url=None, file_type=None, metadata=None) == "general"


def test_empty_metadata_returns_general():
    assert resolve_namespace(metadata={}) == "general"


# ── Priority: explicit > source_type > URL ──────────────────────────────────

def test_explicit_overrides_source_type():
    result = resolve_namespace(
        source_url="https://youtube.com/watch?v=x",
        metadata={"namespace": "override", "source_type": "youtube"},
    )
    assert result == "override"


def test_source_type_overrides_url():
    result = resolve_namespace(
        source_url="https://youtube.com/watch?v=x",
        metadata={"source_type": "web_url"},
    )
    assert result == "web"
