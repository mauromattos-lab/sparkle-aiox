"""
Unit tests for task registry.
Validates all handlers are registered and get_handler works.
"""
from __future__ import annotations

import pytest

from runtime.tasks.registry import REGISTRY, get_handler


def test_registry_is_not_empty():
    assert len(REGISTRY) > 20


def test_registry_has_critical_handlers():
    critical_types = [
        "echo",
        "brain_ingest",
        "brain_query",
        "activate_agent",
        "health_alert",
        "daily_briefing",
        "chat",
        "generate_content",
        "extract_insights",
        "status_mrr",
        "status_report",
    ]
    for task_type in critical_types:
        assert task_type in REGISTRY, f"Missing handler for '{task_type}'"


def test_get_handler_returns_callable():
    handler = get_handler("echo")
    assert handler is not None
    assert callable(handler)


def test_get_handler_returns_none_for_unknown():
    handler = get_handler("nonexistent_task_type_xyz")
    assert handler is None


def test_all_handlers_are_async_callables():
    """All registered handlers should be async functions."""
    import asyncio
    for task_type, handler in REGISTRY.items():
        assert callable(handler), f"Handler for '{task_type}' is not callable"
        assert asyncio.iscoroutinefunction(handler), f"Handler for '{task_type}' is not async"


def test_task_free_maps_to_chat():
    """task_free should use the chat handler."""
    assert get_handler("task_free") is get_handler("chat")
