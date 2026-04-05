"""
Task registry — maps task_type strings to handler functions.
To add a new handler: import it and register it here.
"""
from __future__ import annotations

from typing import Callable

from runtime.tasks.handlers.activate_agent import handle_activate_agent
from runtime.tasks.handlers.conclave import handle_conclave
from runtime.tasks.handlers.brain_ingest import handle_brain_ingest
from runtime.tasks.handlers.brain_ingest_pipeline import handle_brain_ingest_pipeline
from runtime.tasks.handlers.brain_query import handle_brain_query
from runtime.tasks.handlers.chat import handle_chat
from runtime.tasks.handlers.conversation_summary import handle_conversation_summary
from runtime.tasks.handlers.create_note import handle_create_note
from runtime.tasks.handlers.daily_briefing import handle_daily_briefing
from runtime.tasks.handlers.daily_decision_moment import handle_daily_decision_moment
from runtime.tasks.handlers.echo import handle_echo
from runtime.tasks.handlers.extract_dna import handle_extract_dna
# NOTE: file names are swapped vs content — billing handler lives in upsell.py, upsell handler lives in no_contact.py
from runtime.tasks.handlers.friday_initiative_upsell import handle_friday_initiative_billing
from runtime.tasks.handlers.friday_initiative_risk import handle_friday_initiative_risk
from runtime.tasks.handlers.friday_initiative_no_contact import handle_friday_initiative_upsell
from runtime.tasks.handlers.gap_report import handle_gap_report
from runtime.tasks.handlers.generate_content import handle_generate_content
from runtime.tasks.handlers.health_alert import handle_health_alert
from runtime.tasks.handlers.learn_from_conversation import handle_learn_from_conversation
from runtime.tasks.handlers.loja_integrada_query import handle_loja_integrada_query
from runtime.tasks.handlers.narrative_synthesis import handle_narrative_synthesis
from runtime.tasks.handlers.send_character_message import handle_send_character_message
from runtime.tasks.handlers.onboard_client import handle_onboard_client
from runtime.tasks.handlers.specialist_chat import handle_specialist_chat
from runtime.tasks.handlers.status_mrr import handle_status_mrr
from runtime.tasks.handlers.status_report import handle_status_report
from runtime.tasks.handlers.weekly_briefing import handle_weekly_briefing
from runtime.tasks.handlers.workflow_step import handle_workflow_step
from runtime.tasks.handlers.extract_client_dna import handle_extract_client_dna, handle_extract_all_client_dna
from runtime.tasks.handlers.observer_gap_analysis import handle_observer_gap_analysis
from runtime.tasks.handlers.auto_implement_gap import handle_auto_implement_gap
from runtime.tasks.handlers.extract_insights import handle_extract_insights
from runtime.tasks.handlers.brain_archival import handle_brain_archival
from runtime.tasks.handlers.brain_curate import handle_brain_curate
from runtime.tasks.handlers.client_report import handle_client_report, handle_client_reports_bulk
from runtime.tasks.handlers.cockpit_summary import handle_cockpit_summary, handle_cockpit_query
from runtime.tasks.handlers.cross_source_synthesis import handle_cross_source_synthesis
from runtime.tasks.handlers.billing import handle_create_subscription, handle_billing_alert
from runtime.tasks.handlers.gate_check import handle_gate_check
from runtime.tasks.handlers.intake_form_whatsapp import handle_intake_form_whatsapp
from runtime.tasks.handlers.scrape_instagram import handle_scrape_instagram
from runtime.tasks.handlers.intake_orchestrator import handle_intake_orchestrator
from runtime.tasks.handlers.onboard_client_v2 import handle_onboard_client_v2
from runtime.tasks.handlers.smoke_test_zenya import handle_smoke_test_zenya
from runtime.tasks.handlers.post_golive_health import handle_post_golive_health

# task_type → handler(task: dict) -> dict
REGISTRY: dict[str, Callable[[dict], dict]] = {
    "activate_agent":           handle_activate_agent,
    "conclave":                 handle_conclave,
    "brain_ingest":             handle_brain_ingest,
    "brain_ingest_pipeline":    handle_brain_ingest_pipeline,
    "brain_archival":            handle_brain_archival,
    "brain_curate":             handle_brain_curate,
    "brain_query":              handle_brain_query,
    "chat":                     handle_chat,
    "conversation_summary":     handle_conversation_summary,
    "create_note":              handle_create_note,
    "daily_briefing":           handle_daily_briefing,
    "daily_decision_moment":    handle_daily_decision_moment,
    "echo":                     handle_echo,
    "extract_dna":              handle_extract_dna,
    "friday_initiative_billing": handle_friday_initiative_billing,
    "friday_initiative_risk":   handle_friday_initiative_risk,
    "friday_initiative_upsell": handle_friday_initiative_upsell,
    "gap_report":               handle_gap_report,
    "generate_content":         handle_generate_content,
    "health_alert":             handle_health_alert,
    "learn_from_conversation":  handle_learn_from_conversation,
    "loja_integrada_query":     handle_loja_integrada_query,
    "narrative_synthesis":      handle_narrative_synthesis,
    "send_character_message":   handle_send_character_message,
    "onboard_client":           handle_onboard_client,
    "specialist_chat":          handle_specialist_chat,
    "status_mrr":               handle_status_mrr,
    "status_report":            handle_status_report,
    "weekly_briefing":          handle_weekly_briefing,
    "workflow_step":             handle_workflow_step,
    "extract_client_dna":       handle_extract_client_dna,
    "extract_all_client_dna":   handle_extract_all_client_dna,
    "observer_gap_analysis":    handle_observer_gap_analysis,
    "auto_implement_gap":       handle_auto_implement_gap,
    "extract_insights":         handle_extract_insights,
    "client_report":             handle_client_report,
    "client_reports_bulk":       handle_client_reports_bulk,
    "cockpit_summary":          handle_cockpit_summary,
    "cockpit_query":            handle_cockpit_query,
    "cross_source_synthesis":   handle_cross_source_synthesis,
    "create_subscription":      handle_create_subscription,
    "billing_alert":            handle_billing_alert,
    "gate_check":               handle_gate_check,
    # ONB-2: Intake automático
    "intake_form_whatsapp":     handle_intake_form_whatsapp,
    "scrape_instagram":         handle_scrape_instagram,
    "intake_orchestrator":      handle_intake_orchestrator,
    # ONB-3: Configuração automática da Zenya (DNA → soul_prompt → KB)
    "onboard_client_v2":        handle_onboard_client_v2,
    # ONB-5: QA smoke test (checklists + perguntas de teste)
    "smoke_test_zenya":         handle_smoke_test_zenya,
    # ONB-1.9: Health check pos-go-live (monitoramento 30 dias)
    "post_golive_health":       handle_post_golive_health,
    # fallback: free-form conversation goes to chat handler
    "task_free":                handle_chat,
}


def get_handler(task_type: str) -> Callable[[dict], dict] | None:
    return REGISTRY.get(task_type)
