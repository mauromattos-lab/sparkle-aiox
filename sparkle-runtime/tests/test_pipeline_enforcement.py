"""
Tests for Pipeline Enforcement — C2-B2.

Covers:
  - Happy path: sequential transitions 0->1->2->3->4
  - All possible skip attempts (0->2, 0->3, 0->4, 1->3, 1->4, 2->4)
  - Backward transitions (2->1, 4->0, etc.)
  - Step name resolution
  - validate_transition returns correct bool
  - Invalid step handling
"""
from __future__ import annotations

import pytest

from runtime.workflows.pipeline_enforcement import (
    STEP_NAMES,
    NAME_TO_STEP,
    MAX_STEP,
    get_step_name,
    resolve_step,
    validate_transition,
)


# ── Test: Step name resolution ────────────────────────────────────────

class TestStepResolution:
    def test_step_names_complete(self):
        """All 5 steps are defined."""
        assert len(STEP_NAMES) == 5
        assert STEP_NAMES[0] == "story_created"
        assert STEP_NAMES[1] == "dev_implementing"
        assert STEP_NAMES[2] == "qa_validating"
        assert STEP_NAMES[3] == "devops_deploying"
        assert STEP_NAMES[4] == "done"

    def test_get_step_name(self):
        assert get_step_name(0) == "story_created"
        assert get_step_name(4) == "done"
        assert get_step_name(99).startswith("unknown_step_")

    def test_resolve_step_by_int(self):
        assert resolve_step(0) == 0
        assert resolve_step(3) == 3

    def test_resolve_step_by_name(self):
        assert resolve_step("story_created") == 0
        assert resolve_step("qa_validating") == 2
        assert resolve_step("done") == 4

    def test_resolve_step_by_string_int(self):
        assert resolve_step("2") == 2

    def test_resolve_step_invalid(self):
        with pytest.raises(ValueError):
            resolve_step("nonexistent_step")

    def test_name_to_step_mapping(self):
        assert NAME_TO_STEP["story_created"] == 0
        assert NAME_TO_STEP["done"] == 4


# ── Test: validate_transition ─────────────────────────────────────────

class TestValidateTransition:
    """Test all transition scenarios for the 5-step pipeline."""

    # Happy path: all valid sequential transitions
    def test_valid_0_to_1(self):
        assert validate_transition(0, 1) is True

    def test_valid_1_to_2(self):
        assert validate_transition(1, 2) is True

    def test_valid_2_to_3(self):
        assert validate_transition(2, 3) is True

    def test_valid_3_to_4(self):
        assert validate_transition(3, 4) is True

    # Full happy path
    def test_happy_path_sequential(self):
        """Complete pipeline 0->1->2->3->4 all pass."""
        for current in range(4):
            assert validate_transition(current, current + 1) is True, (
                f"Transition {current} -> {current + 1} should be valid"
            )

    # Skip attempts (all should fail)
    def test_skip_0_to_2(self):
        assert validate_transition(0, 2) is False

    def test_skip_0_to_3(self):
        assert validate_transition(0, 3) is False

    def test_skip_0_to_4(self):
        assert validate_transition(0, 4) is False

    def test_skip_1_to_3(self):
        assert validate_transition(1, 3) is False

    def test_skip_1_to_4(self):
        assert validate_transition(1, 4) is False

    def test_skip_2_to_4(self):
        assert validate_transition(2, 4) is False

    # Backward transitions (all should fail)
    def test_backward_1_to_0(self):
        assert validate_transition(1, 0) is False

    def test_backward_2_to_0(self):
        assert validate_transition(2, 0) is False

    def test_backward_2_to_1(self):
        assert validate_transition(2, 1) is False

    def test_backward_4_to_0(self):
        assert validate_transition(4, 0) is False

    # Same step (should fail - not advancing)
    def test_same_step_0_to_0(self):
        assert validate_transition(0, 0) is False

    def test_same_step_2_to_2(self):
        assert validate_transition(2, 2) is False

    # Beyond max step
    def test_beyond_max_4_to_5(self):
        assert validate_transition(4, 5) is False

    # Using step names instead of indices
    def test_valid_by_name(self):
        assert validate_transition("story_created", "dev_implementing") is True

    def test_skip_by_name(self):
        assert validate_transition("story_created", "qa_validating") is False

    # Invalid step values
    def test_invalid_step_value(self):
        assert validate_transition("bogus", 1) is False

    def test_negative_step(self):
        assert validate_transition(-1, 0) is True  # -1 + 1 == 0, valid range

    # All possible skip combinations exhaustive test
    def test_all_invalid_skips(self):
        """Every non-sequential forward jump should be invalid."""
        for current in range(5):
            for target in range(5):
                if target == current + 1:
                    # This is the only valid transition
                    continue
                result = validate_transition(current, target)
                assert result is False, (
                    f"Transition {current} -> {target} should be INVALID "
                    f"but returned {result}"
                )


# ── Test: pipeline template exists ────────────────────────────────────

class TestPipelineTemplate:
    def test_aios_pipeline_template_exists(self):
        """aios_pipeline template is registered in WORKFLOW_TEMPLATES."""
        from runtime.workflows.templates import WORKFLOW_TEMPLATES

        slugs = [t["slug"] for t in WORKFLOW_TEMPLATES]
        assert "aios_pipeline" in slugs

    def test_aios_pipeline_has_5_steps(self):
        from runtime.workflows.templates import WORKFLOW_TEMPLATES

        template = next(t for t in WORKFLOW_TEMPLATES if t["slug"] == "aios_pipeline")
        assert len(template["steps"]) == 5

    def test_aios_pipeline_step_names_match(self):
        from runtime.workflows.templates import WORKFLOW_TEMPLATES

        template = next(t for t in WORKFLOW_TEMPLATES if t["slug"] == "aios_pipeline")
        expected_names = [
            "story_created",
            "dev_implementing",
            "qa_validating",
            "devops_deploying",
            "done",
        ]
        actual_names = [s["name"] for s in template["steps"]]
        assert actual_names == expected_names

    def test_aios_pipeline_is_active(self):
        from runtime.workflows.templates import WORKFLOW_TEMPLATES

        template = next(t for t in WORKFLOW_TEMPLATES if t["slug"] == "aios_pipeline")
        assert template["active"] is True

    def test_existing_templates_unchanged(self):
        """Adding aios_pipeline didn't break existing templates."""
        from runtime.workflows.templates import WORKFLOW_TEMPLATES

        slugs = [t["slug"] for t in WORKFLOW_TEMPLATES]
        assert "onboarding_zenya" in slugs
        assert "content_production" in slugs
        assert "brain_learning" in slugs
