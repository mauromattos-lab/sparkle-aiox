"""
Unit tests for echo handler.
Tests the simplest handler to validate test infrastructure works.
"""
from __future__ import annotations

import pytest

from runtime.tasks.handlers.echo import handle_echo


@pytest.mark.asyncio
async def test_echo_returns_payload_content():
    task = {"payload": {"content": "hello world"}}
    result = await handle_echo(task)
    assert result["message"] == "Echo: hello world"
    assert result["received_payload"] == {"content": "hello world"}


@pytest.mark.asyncio
async def test_echo_returns_original_text_when_no_content():
    task = {"payload": {"original_text": "test text"}}
    result = await handle_echo(task)
    assert "test text" in result["message"]


@pytest.mark.asyncio
async def test_echo_returns_str_payload_when_empty():
    task = {"payload": {}}
    result = await handle_echo(task)
    assert "Echo:" in result["message"]


@pytest.mark.asyncio
async def test_echo_handoff_flag():
    task = {"payload": {"content": "test", "return_handoff": True}}
    result = await handle_echo(task)
    assert result["handoff_to"] == "brain_ingest"
    assert "handoff_payload" in result
    assert result["handoff_payload"]["ingest_type"] == "test"


@pytest.mark.asyncio
async def test_echo_brain_worthy_flag():
    task = {"payload": {"content": "test", "brain_worthy": True}}
    result = await handle_echo(task)
    assert result["brain_worthy"] is True
    assert "brain_content" in result


@pytest.mark.asyncio
async def test_echo_no_handoff_by_default():
    task = {"payload": {"content": "simple"}}
    result = await handle_echo(task)
    assert "handoff_to" not in result
    assert "brain_worthy" not in result
