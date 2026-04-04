"""
Unit tests for Content Engine v2.

Tests:
- Models: Platform, ContentFormat, validation, constraints
- Templates: registry, lookup, backward compat
- Router: preview, batch generation, template listing
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from runtime.content.models import (
    BatchDayItem,
    BatchDayPlan,
    BatchGenerateRequest,
    ContentFormat,
    Platform,
    PLATFORM_METADATA,
    ScheduleRequest,
    get_platform_constraints,
    validate_format_for_platform,
)
from runtime.content.templates import (
    ContentTemplate,
    get_prompt_instructions,
    get_template,
    list_templates,
)


# ══════════════════════════════════════════════════════════════
# Models tests
# ══════════════════════════════════════════════════════════════

class TestPlatformEnum:
    def test_platform_values(self):
        assert Platform.INSTAGRAM.value == "instagram"
        assert Platform.YOUTUBE.value == "youtube"
        assert Platform.TIKTOK.value == "tiktok"

    def test_platform_from_string(self):
        assert Platform("instagram") == Platform.INSTAGRAM
        assert Platform("youtube") == Platform.YOUTUBE

    def test_invalid_platform_raises(self):
        with pytest.raises(ValueError):
            Platform("twitter")


class TestContentFormatEnum:
    def test_format_values(self):
        assert ContentFormat.POST.value == "post"
        assert ContentFormat.CAROUSEL.value == "carousel"
        assert ContentFormat.REELS.value == "reels"
        assert ContentFormat.SHORTS.value == "shorts"
        assert ContentFormat.STORY.value == "story"
        assert ContentFormat.THREAD.value == "thread"

    def test_format_from_string(self):
        assert ContentFormat("reels") == ContentFormat.REELS


class TestValidateFormatForPlatform:
    def test_post_on_instagram(self):
        assert validate_format_for_platform(ContentFormat.POST, Platform.INSTAGRAM) is True

    def test_carousel_on_instagram(self):
        assert validate_format_for_platform(ContentFormat.CAROUSEL, Platform.INSTAGRAM) is True

    def test_reels_on_instagram(self):
        assert validate_format_for_platform(ContentFormat.REELS, Platform.INSTAGRAM) is True

    def test_story_on_instagram(self):
        assert validate_format_for_platform(ContentFormat.STORY, Platform.INSTAGRAM) is True

    def test_shorts_on_youtube(self):
        assert validate_format_for_platform(ContentFormat.SHORTS, Platform.YOUTUBE) is True

    def test_reels_on_tiktok(self):
        assert validate_format_for_platform(ContentFormat.REELS, Platform.TIKTOK) is True

    def test_carousel_on_youtube_invalid(self):
        assert validate_format_for_platform(ContentFormat.CAROUSEL, Platform.YOUTUBE) is False

    def test_shorts_on_instagram_invalid(self):
        assert validate_format_for_platform(ContentFormat.SHORTS, Platform.INSTAGRAM) is False

    def test_post_on_tiktok_invalid(self):
        assert validate_format_for_platform(ContentFormat.POST, Platform.TIKTOK) is False


class TestGetPlatformConstraints:
    def test_instagram_post_constraints(self):
        c = get_platform_constraints(ContentFormat.POST, Platform.INSTAGRAM)
        assert c["aspect_ratio"] == "1:1"
        assert c["max_caption_length"] == 2200
        assert c["duration_limits"] is None
        assert c["hashtag_strategy"]["max_hashtags"] == 30

    def test_instagram_reels_constraints(self):
        c = get_platform_constraints(ContentFormat.REELS, Platform.INSTAGRAM)
        assert c["aspect_ratio"] == "9:16"
        assert c["duration_limits"]["max_seconds"] == 90

    def test_youtube_shorts_constraints(self):
        c = get_platform_constraints(ContentFormat.SHORTS, Platform.YOUTUBE)
        assert c["aspect_ratio"] == "9:16"
        assert c["duration_limits"]["max_seconds"] == 60
        assert c["hashtag_strategy"]["recommended"] == 5

    def test_tiktok_reels_constraints(self):
        c = get_platform_constraints(ContentFormat.REELS, Platform.TIKTOK)
        assert c["duration_limits"]["max_seconds"] == 180
        assert c["hashtag_strategy"]["max_hashtags"] == 8


class TestPlatformMetadata:
    def test_all_platforms_have_metadata(self):
        for p in Platform:
            assert p in PLATFORM_METADATA

    def test_instagram_has_all_formats(self):
        ig = PLATFORM_METADATA[Platform.INSTAGRAM]
        assert ContentFormat.POST in ig["supported_formats"]
        assert ContentFormat.CAROUSEL in ig["supported_formats"]
        assert ContentFormat.REELS in ig["supported_formats"]
        assert ContentFormat.STORY in ig["supported_formats"]


# ══════════════════════════════════════════════════════════════
# Pydantic model tests
# ══════════════════════════════════════════════════════════════

class TestScheduleRequest:
    def test_defaults(self):
        from datetime import datetime
        req = ScheduleRequest(topic="test", scheduled_for=datetime.now())
        assert req.platform == Platform.INSTAGRAM
        assert req.format == ContentFormat.POST
        assert req.persona == "zenya"
        assert req.client_id is None

    def test_custom_platform(self):
        from datetime import datetime
        req = ScheduleRequest(
            topic="test",
            scheduled_for=datetime.now(),
            platform="youtube",
            format="shorts",
        )
        assert req.platform == Platform.YOUTUBE
        assert req.format == ContentFormat.SHORTS


class TestBatchModels:
    def test_batch_day_item_defaults(self):
        item = BatchDayItem(topic="Dicas de marketing")
        assert item.format == ContentFormat.POST
        assert item.platform == Platform.INSTAGRAM
        assert item.persona == "zenya"

    def test_batch_day_plan(self):
        plan = BatchDayPlan(
            date="2026-04-07",
            items=[
                BatchDayItem(topic="Post 1"),
                BatchDayItem(topic="Post 2", format="reels", platform="tiktok"),
            ],
        )
        assert len(plan.items) == 2
        assert plan.items[1].platform == Platform.TIKTOK

    def test_batch_generate_request(self):
        req = BatchGenerateRequest(
            days=[
                BatchDayPlan(
                    date="2026-04-07",
                    items=[BatchDayItem(topic="Topic A")],
                ),
            ],
        )
        assert len(req.days) == 1
        assert req.client_id is None


# ══════════════════════════════════════════════════════════════
# Templates tests
# ══════════════════════════════════════════════════════════════

class TestTemplateRegistry:
    def test_list_templates_returns_all(self):
        templates = list_templates()
        assert len(templates) >= 6  # 4 IG + 1 YT + 1 TT
        formats = {t["format"] for t in templates}
        assert "post" in formats
        assert "carousel" in formats
        assert "reels" in formats
        assert "shorts" in formats
        assert "story" in formats

    def test_get_template_instagram_post(self):
        t = get_template(ContentFormat.POST, Platform.INSTAGRAM)
        assert t is not None
        assert t.name == "Post Instagram"
        assert t.max_length == 2200

    def test_get_template_instagram_carousel(self):
        t = get_template(ContentFormat.CAROUSEL, Platform.INSTAGRAM)
        assert t is not None
        assert t.slide_count == (5, 10)

    def test_get_template_instagram_reels(self):
        t = get_template(ContentFormat.REELS, Platform.INSTAGRAM)
        assert t is not None
        assert "hook" in [s["section"] for s in t.structure]

    def test_get_template_youtube_shorts(self):
        t = get_template(ContentFormat.SHORTS, Platform.YOUTUBE)
        assert t is not None
        assert "title" in [s["section"] for s in t.structure]

    def test_get_template_tiktok_reels(self):
        t = get_template(ContentFormat.REELS, Platform.TIKTOK)
        assert t is not None
        assert "sound_suggestion" in [s["section"] for s in t.structure]

    def test_get_template_invalid_combo(self):
        t = get_template(ContentFormat.SHORTS, Platform.INSTAGRAM)
        assert t is None

    def test_template_to_dict(self):
        t = get_template(ContentFormat.POST, Platform.INSTAGRAM)
        d = t.to_dict()
        assert d["format"] == "post"
        assert d["platform"] == "instagram"
        assert "structure" in d


class TestTemplateBackwardCompat:
    def test_v1_instagram_post_string(self):
        t = get_template("instagram_post")
        assert t is not None
        assert t.format == ContentFormat.POST

    def test_v1_carousel_string(self):
        t = get_template("carousel")
        assert t is not None
        assert t.format == ContentFormat.CAROUSEL

    def test_v1_story_string(self):
        t = get_template("story")
        assert t is not None
        assert t.format == ContentFormat.STORY

    def test_string_format_and_platform(self):
        t = get_template("reels", "tiktok")
        assert t is not None
        assert t.platform == Platform.TIKTOK

    def test_invalid_string_returns_none(self):
        t = get_template("nonexistent_format")
        assert t is None


class TestGetPromptInstructions:
    def test_instagram_post_has_instructions(self):
        instructions = get_prompt_instructions(ContentFormat.POST, Platform.INSTAGRAM)
        assert "Instagram" in instructions or "legenda" in instructions

    def test_youtube_shorts_has_instructions(self):
        instructions = get_prompt_instructions(ContentFormat.SHORTS, Platform.YOUTUBE)
        assert "YouTube" in instructions or "Shorts" in instructions

    def test_fallback_for_unknown(self):
        instructions = get_prompt_instructions("unknown_format", "unknown_platform")
        assert "conteudo" in instructions.lower()


# ══════════════════════════════════════════════════════════════
# Router helpers tests
# ══════════════════════════════════════════════════════════════

class TestBuildPreviewText:
    def test_preview_text_basic(self):
        from runtime.content.router import _build_preview_text
        text = _build_preview_text(
            content="Hello world content",
            hashtags=["marketing", "digital"],
            fmt=ContentFormat.POST,
            platform=Platform.INSTAGRAM,
        )
        assert "INSTAGRAM" in text
        assert "POST" in text
        assert "Hello world content" in text
        assert "#marketing" in text

    def test_preview_text_long_content_truncated(self):
        from runtime.content.router import _build_preview_text
        long_content = "x" * 600
        text = _build_preview_text(
            content=long_content,
            hashtags=[],
            fmt=ContentFormat.POST,
            platform=Platform.INSTAGRAM,
        )
        assert "..." in text
        assert len(text) < len(long_content) + 200  # Some overhead for header

    def test_preview_text_over_limit_warning(self):
        from runtime.content.router import _build_preview_text
        over_content = "x" * 2500
        text = _build_preview_text(
            content=over_content,
            hashtags=[],
            fmt=ContentFormat.POST,
            platform=Platform.INSTAGRAM,
        )
        assert "AVISO" in text
        assert "2200" in text

    def test_preview_text_hashtag_limit(self):
        from runtime.content.router import _build_preview_text
        many_tags = [f"tag{i}" for i in range(20)]
        text = _build_preview_text(
            content="Content",
            hashtags=many_tags,
            fmt=ContentFormat.POST,
            platform=Platform.INSTAGRAM,
        )
        # Instagram recommended is 15
        assert "+5 mais" in text


# ══════════════════════════════════════════════════════════════
# Router endpoint tests (via TestClient)
# ══════════════════════════════════════════════════════════════

class TestTemplatesEndpoint:
    def test_list_all_templates(self, test_app):
        client, mock_sb = test_app
        resp = client.get("/content/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 6
        assert "instagram" in data["platforms"]
        assert "youtube" in data["platforms"]
        assert "tiktok" in data["platforms"]

    def test_filter_by_platform(self, test_app):
        client, mock_sb = test_app
        resp = client.get("/content/templates?platform=youtube")
        assert resp.status_code == 200
        data = resp.json()
        for t in data["templates"]:
            assert t["platform"] == "youtube"

    def test_filter_by_format(self, test_app):
        client, mock_sb = test_app
        resp = client.get("/content/templates?format=reels")
        assert resp.status_code == 200
        data = resp.json()
        for t in data["templates"]:
            assert t["format"] == "reels"


class TestPreviewEndpoint:
    def test_preview_returns_structured_data(self, test_app):
        client, mock_sb = test_app
        mock_sb.set_table_data("generated_content", [{
            "id": "content-001",
            "platform": "instagram",
            "format": "post",
            "persona": "zenya",
            "topic": "Marketing digital",
            "content": "Conteudo de teste para preview",
            "hashtags": ["marketing", "digital"],
            "status": "draft",
            "created_at": "2026-04-04T10:00:00Z",
        }])
        resp = client.get("/content/content-001/preview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "content-001"
        assert data["platform"] == "instagram"
        assert data["format"] == "post"
        assert data["content"] == "Conteudo de teste para preview"
        assert "platform_metadata" in data
        assert "preview_text" in data
        assert data["char_count"] > 0

    def test_preview_not_found(self, test_app):
        client, mock_sb = test_app
        # Empty table data means not found
        mock_sb.set_table_data("generated_content", [])
        resp = client.get("/content/nonexistent-id/preview")
        assert resp.status_code == 404

    def test_preview_v1_format_compat(self, test_app):
        client, mock_sb = test_app
        mock_sb.set_table_data("generated_content", [{
            "id": "content-v1",
            "format": "instagram_post",  # v1 format name
            "persona": "zenya",
            "topic": "Test",
            "content": "V1 content",
            "hashtags": [],
            "status": "draft",
            "created_at": "2026-04-04T10:00:00Z",
        }])
        resp = client.get("/content/content-v1/preview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "post"  # Mapped to v2 format
        assert data["platform"] == "instagram"  # Default platform


class TestBatchEndpoint:
    def test_batch_creates_tasks(self, test_app):
        client, mock_sb = test_app
        resp = client.post("/content/generate-batch", json={
            "days": [
                {
                    "date": "2026-04-07",
                    "items": [
                        {"topic": "Dicas de marketing", "format": "post", "platform": "instagram"},
                        {"topic": "Bastidores", "format": "reels", "platform": "instagram"},
                    ],
                },
                {
                    "date": "2026-04-08",
                    "items": [
                        {"topic": "Tutorial rapido", "format": "shorts", "platform": "youtube"},
                    ],
                },
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_scheduled"] == 3
        assert data["total_errors"] == 0
        assert len(data["tasks"]) == 3

    def test_batch_validates_format_platform(self, test_app):
        client, mock_sb = test_app
        resp = client.post("/content/generate-batch", json={
            "days": [
                {
                    "date": "2026-04-07",
                    "items": [
                        {"topic": "Invalid combo", "format": "carousel", "platform": "youtube"},
                    ],
                },
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_errors"] == 1
        assert data["total_scheduled"] == 0
        assert "not supported" in data["errors"][0]["error"]

    def test_batch_empty_days_rejected(self, test_app):
        client, mock_sb = test_app
        resp = client.post("/content/generate-batch", json={
            "days": [],
        })
        assert resp.status_code == 422  # Pydantic validation error

    def test_batch_mixed_valid_invalid(self, test_app):
        client, mock_sb = test_app
        resp = client.post("/content/generate-batch", json={
            "days": [
                {
                    "date": "2026-04-07",
                    "items": [
                        {"topic": "Valid post", "format": "post", "platform": "instagram"},
                        {"topic": "Invalid combo", "format": "shorts", "platform": "instagram"},
                    ],
                },
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_scheduled"] == 1
        assert data["total_errors"] == 1


class TestScheduleEndpointV2:
    def test_schedule_with_platform(self, test_app):
        client, mock_sb = test_app
        resp = client.post("/content/schedule", json={
            "topic": "YouTube tutorial",
            "format": "shorts",
            "platform": "youtube",
            "scheduled_for": "2026-04-10T10:00:00Z",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["platform"] == "youtube"
        assert data["format"] == "shorts"

    def test_schedule_invalid_format_platform(self, test_app):
        client, mock_sb = test_app
        resp = client.post("/content/schedule", json={
            "topic": "Test",
            "format": "carousel",
            "platform": "youtube",
            "scheduled_for": "2026-04-10T10:00:00Z",
        })
        assert resp.status_code == 400
        assert "not supported" in resp.json()["detail"]

    def test_schedule_defaults_to_instagram(self, test_app):
        client, mock_sb = test_app
        resp = client.post("/content/schedule", json={
            "topic": "Default platform test",
            "scheduled_for": "2026-04-10T10:00:00Z",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["platform"] == "instagram"
        assert data["format"] == "post"


class TestListContentWithPlatform:
    def test_list_with_platform_filter(self, test_app):
        client, mock_sb = test_app
        mock_sb.set_table_data("generated_content", [
            {"id": "1", "platform": "instagram", "format": "post"},
        ])
        resp = client.get("/content/list?platform=instagram")
        assert resp.status_code == 200
