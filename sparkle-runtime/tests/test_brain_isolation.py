"""
Tests for B1-03: Brain Isolation — per-agent brain access control.

These are pure unit tests (no Supabase, no network).
"""
from __future__ import annotations

import pytest

from runtime.brain.isolation import (
    get_brain_owner_filter,
    get_brain_owner_for_ingest,
    validate_brain_access,
    verify_isolation,
)


# ── get_brain_owner_filter ─────────────────────────────────────────


class TestGetBrainOwnerFilter:
    def test_friday_returns_friday(self):
        assert get_brain_owner_filter("friday") == "friday"

    def test_friday_ignores_client_id(self):
        assert get_brain_owner_filter("friday", client_id="client_123") == "friday"

    def test_brain_returns_brain(self):
        assert get_brain_owner_filter("brain") == "brain"

    def test_system_returns_none(self):
        assert get_brain_owner_filter("system") is None

    def test_orion_returns_none(self):
        assert get_brain_owner_filter("orion") is None

    def test_zenya_with_client_id(self):
        assert get_brain_owner_filter("zenya_confeitaria", client_id="client_abc") == "client_abc"

    def test_zenya_without_client_id_falls_back_to_slug(self):
        result = get_brain_owner_filter("zenya_ensinaja")
        assert result == "zenya_ensinaja"

    def test_zenya_plain_with_client_id(self):
        assert get_brain_owner_filter("zenya", client_id="client_xyz") == "client_xyz"

    def test_unknown_agent_returns_slug(self):
        assert get_brain_owner_filter("some_custom_agent") == "some_custom_agent"

    def test_empty_string_returns_empty(self):
        assert get_brain_owner_filter("") == ""

    def test_case_insensitive(self):
        assert get_brain_owner_filter("FRIDAY") == "friday"
        assert get_brain_owner_filter("System") is None
        assert get_brain_owner_filter("ORION") is None

    def test_whitespace_stripped(self):
        assert get_brain_owner_filter("  friday  ") == "friday"


# ── validate_brain_access ──────────────────────────────────────────


class TestValidateBrainAccess:
    def test_friday_can_access_own(self):
        assert validate_brain_access("friday", "friday") is True

    def test_friday_cannot_access_other(self):
        assert validate_brain_access("friday", "client_abc") is False

    def test_system_can_access_anything(self):
        assert validate_brain_access("system", "friday") is True
        assert validate_brain_access("system", "client_abc") is True
        assert validate_brain_access("system", "random") is True

    def test_orion_can_access_anything(self):
        assert validate_brain_access("orion", "friday") is True
        assert validate_brain_access("orion", "whatever") is True

    def test_zenya_can_access_own_client(self):
        assert validate_brain_access("zenya_conf", "client_1", client_id="client_1") is True

    def test_zenya_cannot_access_other_client(self):
        assert validate_brain_access("zenya_conf", "client_2", client_id="client_1") is False

    def test_unknown_agent_can_access_own_slug(self):
        assert validate_brain_access("custom_bot", "custom_bot") is True

    def test_unknown_agent_cannot_access_other(self):
        assert validate_brain_access("custom_bot", "friday") is False


# ── get_brain_owner_for_ingest ─────────────────────────────────────


class TestGetBrainOwnerForIngest:
    def test_friday_ingest_owner(self):
        assert get_brain_owner_for_ingest("friday") == "friday"

    def test_system_ingest_owner(self):
        assert get_brain_owner_for_ingest("system") == "system"

    def test_orion_ingest_owner(self):
        assert get_brain_owner_for_ingest("orion") == "system"

    def test_zenya_ingest_with_client(self):
        assert get_brain_owner_for_ingest("zenya_x", client_id="client_1") == "client_1"

    def test_default_agent_ingest(self):
        assert get_brain_owner_for_ingest("some_agent") == "some_agent"


# ── verify_isolation ───────────────────────────────────────────────


class TestVerifyIsolation:
    def test_friday_vs_zenya_isolated(self):
        result = verify_isolation("friday", "zenya_conf")
        assert result["isolated"] is True
        assert result["a_can_see_b"] is False
        assert result["b_can_see_a"] is False

    def test_system_vs_friday_not_isolated(self):
        result = verify_isolation("system", "friday")
        assert result["a_can_see_b"] is True
        assert result["isolated"] is False

    def test_friday_vs_friday_same(self):
        result = verify_isolation("friday", "friday")
        assert result["a_can_see_b"] is True
        assert result["b_can_see_a"] is True
        assert result["isolated"] is False

    def test_two_different_agents_isolated(self):
        result = verify_isolation("agent_a", "agent_b")
        assert result["isolated"] is True
        assert result["a_can_see_b"] is False
        assert result["b_can_see_a"] is False

    def test_orion_vs_any_not_isolated(self):
        result = verify_isolation("orion", "agent_x")
        assert result["a_can_see_b"] is True

    def test_returns_correct_owners(self):
        result = verify_isolation("friday", "system")
        assert result["a_owner"] == "friday"
        assert result["b_owner"] is None
