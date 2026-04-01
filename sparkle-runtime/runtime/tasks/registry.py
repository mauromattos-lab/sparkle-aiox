"""
Task registry — maps task_type strings to handler functions.
To add a new handler: import it and register it here.
"""
from __future__ import annotations

from typing import Callable

from runtime.tasks.handlers.activate_agent import handle_activate_agent
from runtime.tasks.handlers.brain_query import handle_brain_query
from runtime.tasks.handlers.chat import handle_chat
from runtime.tasks.handlers.conversation_summary import handle_conversation_summary
from runtime.tasks.handlers.create_note import handle_create_note
from runtime.tasks.handlers.daily_briefing import handle_daily_briefing
from runtime.tasks.handlers.echo import handle_echo
from runtime.tasks.handlers.health_alert import handle_health_alert
from runtime.tasks.handlers.learn_from_conversation import handle_learn_from_conversation
from runtime.tasks.handlers.onboard_client import handle_onboard_client
from runtime.tasks.handlers.status_mrr import handle_status_mrr
from runtime.tasks.handlers.status_report import handle_status_report
from runtime.tasks.handlers.weekly_briefing import handle_weekly_briefing

# task_type → handler(task: dict) -> dict
REGISTRY: dict[str, Callable[[dict], dict]] = {
    "activate_agent":           handle_activate_agent,
    "brain_query":              handle_brain_query,
    "chat":                     handle_chat,
    "conversation_summary":     handle_conversation_summary,
    "create_note":              handle_create_note,
    "daily_briefing":           handle_daily_briefing,
    "echo":                     handle_echo,
    "health_alert":             handle_health_alert,
    "learn_from_conversation":  handle_learn_from_conversation,
    "onboard_client":           handle_onboard_client,
    "status_mrr":               handle_status_mrr,
    "status_report":            handle_status_report,
    "weekly_briefing":          handle_weekly_briefing,
    # fallback: free-form conversation goes to chat handler
    "task_free":                handle_chat,
}


def get_handler(task_type: str) -> Callable[[dict], dict] | None:
    return REGISTRY.get(task_type)
