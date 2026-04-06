"""
Workflow Templates — seed data for the 3 core business workflows.

Templates are stored in workflow_templates (Supabase) and consumed by
the workflow engine (workflow_step handler + /workflow/start endpoint).

Each template is a list of steps with:
  - task_type: must match a key in runtime.tasks.registry.REGISTRY
  - payload_template: dict with {{variable}} placeholders resolved at runtime
  - on_success / on_failure: routing to next step index
  - required_gates: optional list of gate approvals needed before execution

Call seed_workflow_templates() to upsert (slug-based) all templates.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from runtime.db import supabase


# ── Template definitions ───────────────────────────────────────────────

WORKFLOW_TEMPLATES: list[dict] = [
    # ─────────────────────────────────────────────────────────────────
    # 1. onboarding_zenya — Client onboarding via real handlers
    # ─────────────────────────────────────────────────────────────────
    {
        "slug": "onboarding_zenya",
        "name": "Onboarding Novo Cliente Zenya",
        "description": (
            "Pipeline completa handler-driven: scrape site -> ingest no Brain "
            "-> extrair DNA do cliente -> gerar system prompt -> notificar Mauro"
        ),
        "version": 2,
        "active": True,
        "default_priority": 7,
        # ── Variáveis obrigatórias no context ao chamar /workflow/start ──────
        # Validadas por _TEMPLATE_REQUIRED_CONTEXT em runtime/workflow/router.py
        #   site_url        (str) URL do site do cliente — DEVE começar com http:// ou https://
        #   business_name   (str) Nome do negócio — não pode ser vazio
        #   client_id       (str) UUID do cliente no Supabase — não pode ser vazio
        # ── Variáveis opcionais ───────────────────────────────────────────────
        #   business_type       (str) Tipo do negócio (padrão: "negócio")
        #   phone               (str) Telefone do cliente
        #   extra_source_type   (str) Fonte extra: "url" | "text" (step 1, continue_on_failure)
        #   extra_source_ref    (str) URL ou texto da fonte extra (step 1)
        "steps": [
            {
                "step": 0,
                "name": "scrape_site",
                "task_type": "brain_ingest_pipeline",
                "agent_id": "brain",
                "description": (
                    "Scrape do site do cliente e ingestao no Brain. "
                    "Usa pipeline completa: raw storage -> chunking -> canonicalizacao -> embedding."
                ),
                "payload_template": {
                    "source_type": "url",
                    "source_ref": "{{site_url}}",
                    "title": "Site {{business_name}}",
                    "persona": "cliente",
                    "client_id": "{{client_id}}",
                    "run_dna": False,
                    "run_narrative": False,
                },
                "on_success": {"next_step": 1},
                "on_failure": {"continue": False},
                "required_gates": [],
            },
            {
                "step": 1,
                "name": "brain_ingest_content",
                "task_type": "brain_ingest_pipeline",
                "agent_id": "brain",
                "description": (
                    "Ingestao complementar — se houver conteudo adicional (Instagram, docs). "
                    "Roda DNA extraction nos chunks ingeridos."
                ),
                "payload_template": {
                    "source_type": "{{extra_source_type}}",
                    "source_ref": "{{extra_source_ref}}",
                    "title": "Conteudo complementar {{business_name}}",
                    "persona": "cliente",
                    "client_id": "{{client_id}}",
                    "run_dna": True,
                    "run_narrative": False,
                },
                "on_success": {"next_step": 2},
                "on_failure": {"continue": True, "next_step": 2},
                "required_gates": [],
            },
            {
                "step": 2,
                "name": "extract_client_dna",
                "task_type": "extract_client_dna",
                "agent_id": "system",
                "description": (
                    "Extrai DNA estruturado do cliente (6 camadas) a partir dos chunks do Brain. "
                    "Gera: identidade, tom_voz, regras_negocio, diferenciais, publico_alvo, anti_patterns."
                ),
                "payload_template": {
                    "client_id": "{{client_id}}",
                    "regenerate_prompt": True,
                    "additional_context": (
                        "Negocio: {{business_name}}. Tipo: {{business_type}}. "
                        "Telefone: {{phone}}."
                    ),
                },
                "on_success": {"next_step": 3},
                "on_failure": {"continue": False},
                "required_gates": [],
            },
            {
                "step": 3,
                "name": "generate_system_prompt",
                "task_type": "onboard_client",
                "agent_id": "dev",
                "description": (
                    "Gera KB (20-30 itens) + system prompt personalizado. "
                    "Cria registro em clients e insere KB em zenya_knowledge_base. "
                    "Usa o DNA extraido no step anterior como contexto."
                ),
                "payload_template": {
                    "business_name": "{{business_name}}",
                    "business_type": "{{business_type}}",
                    "site_url": "{{site_url}}",
                    "phone": "{{phone}}",
                    "client_id": "{{client_id}}",
                },
                "on_success": {"next_step": 4},
                "on_failure": {"continue": False},
                "required_gates": [],
            },
            {
                "step": 4,
                "name": "notifica_mauro",
                "task_type": "chat",
                "agent_id": "friday",
                "description": "Friday notifica Mauro que o onboarding esta completo.",
                "payload_template": {
                    "original_text": (
                        "Onboarding do cliente {{business_name}} concluido com sucesso! "
                        "Brain ingerido, DNA extraido, KB gerada e system prompt criado. "
                        "Client ID: {{client_id}}. Proximo passo: QA de conversas de teste."
                    ),
                },
                "on_success": {},
                "on_failure": {"continue": True},
                "required_gates": [],
            },
        ],
    },

    # ─────────────────────────────────────────────────────────────────
    # 2. content_production — Content generation from Brain
    # ─────────────────────────────────────────────────────────────────
    {
        "slug": "content_production",
        "name": "Producao de Conteudo via Brain",
        "description": (
            "Consulta Brain por conhecimento relevante -> gera conteudo Instagram "
            "-> notifica para review"
        ),
        "version": 2,
        "active": True,
        "default_priority": 5,
        "steps": [
            {
                "step": 0,
                "name": "brain_query",
                "task_type": "brain_query",
                "agent_id": "brain",
                "description": (
                    "Consulta semantica ao Brain buscando conhecimento relevante para o tema. "
                    "Retorna chunks sintetizados como contexto para geracao."
                ),
                "payload_template": {
                    "query": "{{topic}}",
                },
                "on_success": {"next_step": 1},
                "on_failure": {"continue": True, "next_step": 1},
                "required_gates": [],
            },
            {
                "step": 1,
                "name": "generate_content",
                "task_type": "generate_content",
                "agent_id": "dev",
                "description": (
                    "Gera conteudo completo (texto + hashtags) para Instagram. "
                    "Usa o conhecimento do Brain (step anterior) como contexto. "
                    "Formatos: instagram_post, carousel, story, thread."
                ),
                "payload_template": {
                    "topic": "{{topic}}",
                    "format": "{{format}}",
                    "persona": "{{persona}}",
                    "source_type": "workflow",
                    "source_ref": "content_production",
                    "brain_context": "{{step_0_result.message}}",
                },
                "on_success": {"next_step": 2},
                "on_failure": {"continue": False},
                "required_gates": [],
            },
            {
                "step": 2,
                "name": "notifica_review",
                "task_type": "chat",
                "agent_id": "friday",
                "description": "Notifica Mauro que o conteudo esta pronto para review.",
                "payload_template": {
                    "original_text": (
                        "Conteudo pronto para review! Tema: {{topic}}, formato: {{format}}, "
                        "persona: {{persona}}. Acesse o dashboard para revisar e aprovar."
                    ),
                },
                "on_success": {},
                "on_failure": {"continue": True},
                "required_gates": [],
            },
        ],
    },

    # ─────────────────────────────────────────────────────────────────
    # 3. brain_learning — Ingest + insights + synthesis
    # ─────────────────────────────────────────────────────────────────
    {
        "slug": "brain_learning",
        "name": "Brain Learning Pipeline",
        "description": (
            "Ingestao completa + extracao de insights + sintese cruzada. "
            "Pipeline de aprendizado do Mega Brain."
        ),
        "version": 1,
        "active": True,
        "default_priority": 6,
        "steps": [
            {
                "step": 0,
                "name": "brain_ingest",
                "task_type": "brain_ingest_pipeline",
                "agent_id": "brain",
                "description": (
                    "Ingestao completa: raw storage -> chunking -> canonicalizacao -> embedding. "
                    "Aceita URL ou texto direto."
                ),
                "payload_template": {
                    "source_type": "{{source_type}}",
                    "source_ref": "{{source_ref}}",
                    "title": "{{title}}",
                    "persona": "{{persona}}",
                    "run_dna": True,
                    "run_narrative": False,
                },
                "on_success": {"next_step": 1},
                "on_failure": {"continue": False},
                "required_gates": [],
            },
            {
                "step": 1,
                "name": "extract_insights",
                "task_type": "extract_insights",
                "agent_id": "brain",
                "description": (
                    "Extrai insights acionaveis (frameworks, tecnicas, principios) "
                    "dos chunks ingeridos. Usa Haiku para classificacao rapida."
                ),
                "payload_template": {
                    "source_chunk_ids": "{{step_0_result.chunk_ids}}",
                    "source_raw_ingestion_id": "{{step_0_result.raw_ingestion_id}}",
                    "min_confidence": 0.6,
                    "dry_run": False,
                },
                "on_success": {"next_step": 2},
                "on_failure": {"continue": True, "next_step": 2},
                "required_gates": [],
            },
            {
                "step": 2,
                "name": "cross_source_synthesis",
                "task_type": "cross_source_synthesis",
                "agent_id": "brain",
                "description": (
                    "Sintese cruzada: agrupa insights por dominio e gera documento sintetico. "
                    "Roda apenas se houver massa critica (5+ insights por dominio). "
                    "Usa Sonnet para complexidade cognitiva."
                ),
                "payload_template": {
                    "min_insights_per_domain": 5,
                    "force_domains": "{{force_domains}}",
                },
                "on_success": {},
                "on_failure": {"continue": True},
                "required_gates": [],
            },
        ],
    },
    # ─────────────────────────────────────────────────────────────────
    # 4. aios_pipeline — AIOS Pipeline Enforcement (C2-B2)
    # ─────────────────────────────────────────────────────────────────
    {
        "slug": "aios_pipeline",
        "name": "AIOS Pipeline Enforcement v2",
        "description": (
            "Pipeline completo AIOS v2: @pm -> @architect -> @sm -> @dev -> @qa -> @po -> @devops -> done. "
            "Cobre Fase 1 (planejamento) + Fase 2 (execucao). Enforced por codigo."
        ),
        "version": 2,
        "active": True,
        "default_priority": 9,
        "steps": [
            {"step": 0, "name": "prd_approved",    "task_type": "pipeline_gate", "agent_id": "pm",       "description": "PRD aprovado por @pm. Gate: PRD salvo em docs/prd/ com FRs numerados.",                               "payload_template": {}, "on_success": {"next_step": 1}, "on_failure": {"continue": False}, "required_gates": []},
            {"step": 1, "name": "spec_approved",   "task_type": "pipeline_gate", "agent_id": "architect","description": "Design spec aprovado por @architect. Precisa: step 0 (prd_approved).",                               "payload_template": {}, "on_success": {"next_step": 2}, "on_failure": {"continue": False}, "required_gates": []},
            {"step": 2, "name": "stories_ready",   "task_type": "pipeline_gate", "agent_id": "sm",       "description": "Stories criadas por @sm. Precisa: step 1 (spec_approved).",                                         "payload_template": {}, "on_success": {"next_step": 3}, "on_failure": {"continue": False}, "required_gates": []},
            {"step": 3, "name": "dev_complete",    "task_type": "pipeline_gate", "agent_id": "dev",      "description": "Implementacao pelo @dev. Precisa: step 2 (stories_ready).",                                         "payload_template": {}, "on_success": {"next_step": 4}, "on_failure": {"continue": False}, "required_gates": []},
            {"step": 4, "name": "qa_approved",     "task_type": "pipeline_gate", "agent_id": "qa",       "description": "Validacao pelo @qa. Precisa: step 3 (dev_complete).",                                               "payload_template": {}, "on_success": {"next_step": 5}, "on_failure": {"continue": False}, "required_gates": []},
            {"step": 5, "name": "po_accepted",     "task_type": "pipeline_gate", "agent_id": "po",       "description": "Aceite pelo @po (FRs cruzados contra entrega). Precisa: step 4 (qa_approved).",                     "payload_template": {}, "on_success": {"next_step": 6}, "on_failure": {"continue": False}, "required_gates": []},
            {"step": 6, "name": "devops_deployed", "task_type": "pipeline_gate", "agent_id": "devops",   "description": "Deploy pelo @devops. Health check OK. Precisa: step 5 (po_accepted).",                             "payload_template": {}, "on_success": {"next_step": 7}, "on_failure": {"continue": False}, "required_gates": []},
            {"step": 7, "name": "done",            "task_type": "pipeline_gate", "agent_id": "system",   "description": "Pipeline concluido. Deploy verificado, health OK. Precisa: step 6 (devops_deployed).",              "payload_template": {}, "on_success": {},               "on_failure": {"continue": True},  "required_gates": []},
        ],
    },
],
    },
]


# ── Seed function ──────────────────────────────────────────────────────

async def seed_workflow_templates() -> dict:
    """
    Upsert workflow templates into Supabase.
    Uses slug as unique key — updates existing, inserts new.
    Returns summary of operations.
    """
    inserted = 0
    updated = 0
    errors: list[str] = []

    for template in WORKFLOW_TEMPLATES:
        slug = template["slug"]
        now = datetime.now(timezone.utc).isoformat()

        try:
            # Check if template already exists
            existing = await asyncio.to_thread(
                lambda s=slug: supabase.table("workflow_templates")
                .select("id,version")
                .eq("slug", s)
                .limit(1)
                .execute()
            )

            row = {
                "slug": slug,
                "name": template["name"],
                "description": template["description"],
                "steps": template["steps"],
                "version": template["version"],
                "active": template["active"],
                "default_priority": template["default_priority"],
                "updated_at": now,
            }

            if existing.data:
                existing_version = existing.data[0].get("version", 0)
                if template["version"] <= existing_version:
                    print(f"[seed] skip '{slug}' — version {template['version']} <= existing {existing_version}")
                    continue

                # Update existing
                await asyncio.to_thread(
                    lambda s=slug, r=row: supabase.table("workflow_templates")
                    .update(r)
                    .eq("slug", s)
                    .execute()
                )
                updated += 1
                print(f"[seed] updated '{slug}' to v{template['version']}")
            else:
                # Insert new
                row["created_at"] = now
                await asyncio.to_thread(
                    lambda r=row: supabase.table("workflow_templates")
                    .insert(r)
                    .execute()
                )
                inserted += 1
                print(f"[seed] inserted '{slug}' v{template['version']}")

        except Exception as e:
            error_msg = f"Failed to seed '{slug}': {str(e)[:200]}"
            errors.append(error_msg)
            print(f"[seed] ERROR: {error_msg}")

    return {
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
        "total_templates": len(WORKFLOW_TEMPLATES),
    }


def seed_workflow_templates_sync() -> dict:
    """Synchronous wrapper for seed_workflow_templates."""
    return asyncio.run(seed_workflow_templates())


# ── Template listing (used by router) ─────────────────────────────────

def get_template_definitions() -> list[dict]:
    """
    Returns the in-code template definitions (without DB roundtrip).
    Useful for documentation and validation.
    """
    return [
        {
            "slug": t["slug"],
            "name": t["name"],
            "description": t["description"],
            "version": t["version"],
            "active": t["active"],
            "default_priority": t["default_priority"],
            "total_steps": len(t["steps"]),
            "steps_summary": [
                {
                    "step": s["step"],
                    "name": s["name"],
                    "task_type": s["task_type"],
                    "description": s["description"],
                }
                for s in t["steps"]
            ],
        }
        for t in WORKFLOW_TEMPLATES
    ]
