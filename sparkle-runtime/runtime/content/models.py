"""
Content Engine v2 — Models and enums for multi-platform content.

Platforms: instagram, youtube, tiktok
Formats: post, carousel, reels, shorts, story
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────

class Platform(str, Enum):
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"


class ContentFormat(str, Enum):
    POST = "post"
    CAROUSEL = "carousel"
    REELS = "reels"
    SHORTS = "shorts"
    STORY = "story"
    THREAD = "thread"  # backward compat with v1


# ── Platform metadata ────────────────────────────────────────

PLATFORM_METADATA: dict[Platform, dict] = {
    Platform.INSTAGRAM: {
        "name": "Instagram",
        "max_caption_length": 2200,
        "supported_formats": [
            ContentFormat.POST,
            ContentFormat.CAROUSEL,
            ContentFormat.REELS,
            ContentFormat.STORY,
            ContentFormat.THREAD,
        ],
        "aspect_ratios": {
            "post": "1:1",
            "carousel": "1:1",
            "reels": "9:16",
            "story": "9:16",
        },
        "duration_limits": {
            "reels": {"min_seconds": 3, "max_seconds": 90},
            "story": {"min_seconds": 1, "max_seconds": 60},
        },
        "hashtag_strategy": {
            "max_hashtags": 30,
            "recommended": 15,
            "placement": "end_of_caption",
        },
    },
    Platform.YOUTUBE: {
        "name": "YouTube",
        "max_caption_length": 5000,
        "supported_formats": [ContentFormat.SHORTS],
        "aspect_ratios": {
            "shorts": "9:16",
        },
        "duration_limits": {
            "shorts": {"min_seconds": 15, "max_seconds": 60},
        },
        "hashtag_strategy": {
            "max_hashtags": 15,
            "recommended": 5,
            "placement": "description",
        },
    },
    Platform.TIKTOK: {
        "name": "TikTok",
        "max_caption_length": 2200,
        "supported_formats": [ContentFormat.REELS],
        "aspect_ratios": {
            "reels": "9:16",
        },
        "duration_limits": {
            "reels": {"min_seconds": 5, "max_seconds": 180},
        },
        "hashtag_strategy": {
            "max_hashtags": 8,
            "recommended": 5,
            "placement": "end_of_caption",
        },
    },
}


# ── Request/Response models ──────────────────────────────────

class ScheduleRequest(BaseModel):
    """Schedule a single content item for generation."""
    topic: str
    persona: str = "zenya"
    format: ContentFormat = ContentFormat.POST
    platform: Platform = Platform.INSTAGRAM
    scheduled_for: datetime
    client_id: Optional[str] = None


class BatchDayItem(BaseModel):
    """A single content item in a day plan."""
    topic: str
    format: ContentFormat = ContentFormat.POST
    platform: Platform = Platform.INSTAGRAM
    persona: str = "zenya"


class BatchDayPlan(BaseModel):
    """Plan for a single day within a batch week plan."""
    date: str = Field(..., description="YYYY-MM-DD")
    items: list[BatchDayItem] = []


class BatchGenerateRequest(BaseModel):
    """Generate a batch of content items for a week plan."""
    days: list[BatchDayPlan] = Field(
        ...,
        min_length=1,
        max_length=14,
        description="List of day plans (up to 14 days)",
    )
    client_id: Optional[str] = None


class ContentPreview(BaseModel):
    """Structured preview of a content item for its target platform."""
    id: str
    platform: Platform
    format: ContentFormat
    persona: str
    topic: str
    content: str
    hashtags: list[str] = []
    platform_metadata: dict = {}
    preview_text: str = ""
    status: str = "draft"
    created_at: Optional[str] = None


def validate_format_for_platform(
    fmt: ContentFormat,
    platform: Platform,
) -> bool:
    """Check if a content format is supported on a given platform."""
    meta = PLATFORM_METADATA.get(platform)
    if not meta:
        return False
    return fmt in meta["supported_formats"]


def get_platform_constraints(
    fmt: ContentFormat,
    platform: Platform,
) -> dict:
    """Return aspect ratio, duration limits, and hashtag strategy for a format+platform."""
    meta = PLATFORM_METADATA.get(platform, {})
    fmt_key = fmt.value
    return {
        "aspect_ratio": meta.get("aspect_ratios", {}).get(fmt_key),
        "duration_limits": meta.get("duration_limits", {}).get(fmt_key),
        "max_caption_length": meta.get("max_caption_length"),
        "hashtag_strategy": meta.get("hashtag_strategy", {}),
    }
