---
epic: EPIC-CONTENT-ZENYA — Domínio Conteúdo (Zenya-First)
story: CONTENT-1.6
title: "Pipeline Orchestrator — State Machine Completo"
status: TODO
priority: P0
executor: "@dev"
sprint: Content Wave 1
prd: docs/prd/domain-content-zenya-prd.md
architecture: docs/architecture/domain-content-zenya-architecture.md
squad: squads/content/
depends_on: [CONTENT-1.2, CONTENT-1.3, CONTENT-1.4]
unblocks: [CONTENT-1.7, CONTENT-1.10, CONTENT-1.12]
estimated_effort: 5-6h de agente (@dev)
---

# Story 1.6 — Pipeline Orchestrator — State Machine Completo

**Sprint:** Content Wave 1
**Status:** `TODO`
**Sequência:** 7 de 13
**PRD:** `docs/prd/domain-content-zenya-prd.md` — FR2, FR3, FR4, FR5 (integração)
**Architecture:** `docs/architecture/domain-content-zenya-architecture.md`

---

## User Story

> Como sistema,
> quero um orquestrador central que gerencie o estado de cada content_piece e avance automaticamente cada etapa do pipeline (brief → imagem → vídeo → pending_approval),
> para que uma peça de conteúdo se produza de ponta a ponta sem intervenção manual nas etapas de produção visual.

> **MVP v1.1:** pipeline termina em `video_done → pending_approval`. Voz é aplicada manualmente por Mauro via ElevenLabs voice changer. Assembly (Creatomate) é Fase 2.

---

## Contexto Técnico

**Estado atual:** Módulos individuais criados em 1.2, 1.3, 1.4, 1.5 — mas não há nada que os conecte.

**Estado alvo:** `pipeline.py` orquestra a state machine completa. Cada tick do cron `content_pipeline_tick` (a cada 5 min) avança todas as peças presas em estados de geração. Brief criado via API inicia o pipeline automaticamente.

---

## Acceptance Criteria

- [ ] **AC1** — `POST /content/briefs` cria um `content_piece` com `status='briefed'` e dispara o pipeline automaticamente (não precisa de tick para começar)
- [ ] **AC2** — Pipeline avança: `briefed` → `image_generating` → `image_done` → (copy + video em paralelo via `asyncio.gather`) → `video_done` → `pending_approval`
- [ ] **AC3** — Copy Specialist (`caption` + `voice_script`) roda em paralelo com Video Generator a partir de `image_done`
- [ ] **AC4** — Estado `pending_approval` só é atingido quando: `image_url`, `video_url` e `caption` estão preenchidos (`audio_url` não é requisito — voz é manual)
- [ ] **AC5** — `pipeline_log` registra cada transição de estado com timestamp: `[{"from": "briefed", "to": "image_generating", "at": "..."}]`
- [ ] **AC6** — `GET /content/pieces/{id}` retorna status atual + pipeline_log completo
- [ ] **AC7** — `GET /content/briefs` lista todas as peças com status e campo `current_stage` legível
- [ ] **AC8** — Limite de 5 peças simultâneas em produção (status `image_generating` ou `video_generating` count ≤ 5)
- [ ] **AC9** — `POST /content/pieces/{id}/retry` reinicia peça em estado `*_failed` a partir da etapa que falhou
- [ ] **AC10** — Cron `content_pipeline_tick` (*/5 min) verifica peças em `*_generating` e faz polling para confirmar conclusão (para providers assíncronos como Kling)

---

## Dev Notes

### State machine core
```python
async def advance_pipeline(piece: dict) -> None:
    status = piece["status"]
    piece_id = piece["id"]

    if status == "briefed":
        await set_status(piece_id, "image_generating")
        image_url = await image_generator.generate(...)
        await update_piece(piece_id, {"image_url": image_url})
        await set_status(piece_id, "image_done")

    elif status == "image_done":
        # Paralelo: copy + video
        video_task = asyncio.create_task(generate_video(piece))
        copy_task = asyncio.create_task(generate_copy_and_voice(piece))
        await asyncio.gather(video_task, copy_task)
        await set_status(piece_id, "assembly_pending")

    elif status == "assembly_pending":
        final_url = await assembler.assemble(...)
        await update_piece(piece_id, {"final_url": final_url})
        await set_status(piece_id, "assembly_done")

    elif status == "assembly_done":
        await set_status(piece_id, "pending_approval")
        # Trigger Friday notification (Story 1.12)
```

### Logging de transições
```python
async def set_status(piece_id: str, new_status: str) -> None:
    piece = get_piece(piece_id)
    log_entry = {"from": piece["status"], "to": new_status, "at": now().isoformat()}
    pipeline_log = piece.get("pipeline_log") or []
    pipeline_log.append(log_entry)
    supabase.table("content_pieces").update({
        "status": new_status,
        "pipeline_log": pipeline_log,
        "updated_at": now().isoformat()
    }).eq("id", piece_id).execute()
```

### Controle de concorrência (máx 5 peças)
```python
async def can_start_production() -> bool:
    result = supabase.table("content_pieces") \
        .select("id", count="exact") \
        .in_("status", ["image_generating", "video_generating"]) \
        .execute()
    return result.count < 5
```

### Endpoints principais
```
POST /content/briefs          → cria brief + dispara pipeline
GET  /content/briefs          → lista com status
GET  /content/pieces/{id}     → detalhe + pipeline_log
GET  /content/queue           → pending_approval
POST /content/pieces/{id}/retry → reinicia de etapa failed
```

---

## Integration Verifications

- [ ] `POST /content/briefs` com `{theme, mood, style}` cria peça e inicia pipeline end-to-end
- [ ] Após ~15 min, peça passa de `briefed` para `pending_approval` sem intervenção manual
- [ ] `pipeline_log` registra todas as transições com timestamps
- [ ] `GET /content/queue` retorna peça com `status = "pending_approval"`
- [ ] Com 5 peças em `image_generating`, sexta brief aguarda sem iniciar produção
- [ ] `POST /content/pieces/{id}/retry` em peça `image_failed` reinicia geração de imagem
- [ ] Cron `content_pipeline_tick` avança peças pendentes (testar manualmente chamando endpoint do cron)

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `runtime/content/pipeline.py` | Criar | State machine orquestradora + advance_pipeline() |
| `runtime/content/approval.py` | Criar | Lógica de fila de aprovação (pending_approval → approved/rejected) |
| `runtime/content/router.py` | Atualizar | Adicionar endpoints de briefs, queue, retry |
| `tests/test_pipeline.py` | Criar | Testes: state machine, transições, concorrência, retry |
