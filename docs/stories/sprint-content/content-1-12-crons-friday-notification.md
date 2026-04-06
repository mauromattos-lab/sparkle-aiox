---
epic: EPIC-CONTENT-ZENYA — Domínio Conteúdo (Zenya-First)
story: CONTENT-1.12
title: "Crons + Friday Notification (WhatsApp)"
status: TODO
priority: P1
executor: "@dev"
sprint: Content Wave 1
prd: docs/prd/domain-content-zenya-prd.md
architecture: docs/architecture/domain-content-zenya-architecture.md
squad: squads/content/
depends_on: [CONTENT-1.6, CONTENT-1.7, CONTENT-1.11]
unblocks: []
estimated_effort: 3-4h de agente (@dev)
---

# Story 1.12 — Crons + Friday Notification

**Sprint:** Content Wave 1
**Status:** `TODO`
**Sequência:** 13 de 13 (última — fecha o loop)
**PRD:** `docs/prd/domain-content-zenya-prd.md` — FR7 (Friday) + FR8 (publicação automática)
**Architecture:** `docs/architecture/domain-content-zenya-architecture.md`

---

## User Story

> Como sistema,
> quero que três crons mantenham o pipeline funcionando automaticamente (tick de produção, tick de publicação, sync com Brain) e que a Friday notifique Mauro via WhatsApp quando houver conteúdo aguardando aprovação,
> para que o pipeline seja verdadeiramente autônomo e Mauro só precise abrir o Portal quando tiver algo para revisar.

---

## Contexto Técnico

**Estado atual:** Nenhum cron do domínio Content existe. Friday notifica sobre clientes mas não sobre conteúdo.

**Estado alvo:** 3 crons registrados no Runtime + Friday enviando mensagem WhatsApp quando fila de aprovação tem ≥ 1 item.

---

## Acceptance Criteria

### Crons

- [ ] **AC1** — Cron `content_pipeline_tick` registrado no Runtime com schedule `*/5 * * * *`: avança peças presas em estados de geração (faz polling de jobs assíncronos no Kling, Creatomate)
- [ ] **AC2** — Cron `content_publisher_tick` registrado com schedule `0 * * * *`: verifica peças com `status = 'scheduled'` cujo `scheduled_at <= now()` e publica via `publisher.py`
- [ ] **AC3** — Cron `content_brain_sync` registrado com schedule `0 3 * * *` (3h BRT): ingere peças `published` do dia anterior no Brain `sparkle-lore` que ainda não têm `brain_chunk_id`
- [ ] **AC4** — Falha em qualquer cron é registrada em `error_log` da peça afetada e não para os demais crons

### Friday Notification

- [ ] **AC5** — Quando uma peça atinge `status = 'pending_approval'`, sistema verifica se já há notificação enviada no último 1h — se não, Friday envia mensagem WhatsApp para Mauro
- [ ] **AC6** — Mensagem Friday: `"🎬 X conteúdo(s) da Zenya aguardando sua aprovação no Portal — acesse: [link /content/queue]"`
- [ ] **AC7** — Friday não envia notificação duplicada: se já enviou sobre a fila nas últimas 1h, aguarda acumular mais antes de notificar novamente
- [ ] **AC8** — Friday notifica também em caso de `publish_failed`: `"⚠️ Falha ao publicar conteúdo da Zenya — verifique em: [link /content/]"`

---

## Dev Notes

### Registro dos crons no Runtime
Verificar como crons são registrados no Runtime atual (provavelmente em `runtime/crons/` ou similar):

```python
# runtime/crons/content.py

async def content_pipeline_tick():
    """*/5 * * * * — Avança peças em geração"""
    # Buscar peças em estados de polling assíncrono
    stuck_pieces = supabase.table("content_pieces") \
        .select("*") \
        .in_("status", ["image_generating", "video_generating", "assembly_pending"]) \
        .execute()
    
    for piece in stuck_pieces.data:
        try:
            await pipeline.check_and_advance(piece)
        except Exception as e:
            log_error(piece["id"], f"pipeline_tick error: {e}")

async def content_publisher_tick():
    """0 * * * * — Publica peças scheduled"""
    due_pieces = supabase.table("content_pieces") \
        .select("*") \
        .eq("status", "scheduled") \
        .lte("scheduled_at", now().isoformat()) \
        .execute()
    
    for piece in due_pieces.data:
        try:
            await publisher.publish(piece)
        except Exception as e:
            await set_status(piece["id"], "publish_failed")
            await friday_notify_publish_failed(piece)
            log_error(piece["id"], f"publisher error: {e}")

async def content_brain_sync():
    """0 3 * * * — Sync Brain"""
    unsynced = supabase.table("content_pieces") \
        .select("*") \
        .eq("status", "published") \
        .is_("brain_chunk_id", "null") \
        .execute()
    
    for piece in unsynced.data:
        chunk_id = await ip_auditor.ingest_to_brain(piece, piece["published_url"])
        supabase.table("content_pieces") \
            .update({"brain_chunk_id": chunk_id}) \
            .eq("id", piece["id"]).execute()
```

### Friday notification — pending_approval
```python
async def friday_notify_pending_approval() -> None:
    """Chamado quando peça atinge pending_approval"""
    # Anti-spam: não notificar se já notificou na última 1h
    last_notif = await get_last_content_notification()
    if last_notif and (now() - last_notif) < timedelta(hours=1):
        return
    
    pending_count = supabase.table("content_pieces") \
        .select("id", count="exact") \
        .eq("status", "pending_approval") \
        .execute().count
    
    msg = f"🎬 {pending_count} conteúdo(s) da Zenya aguardando aprovação no Portal"
    await zapi_send_message(MAURO_WHATSAPP, msg)
    await record_content_notification()
```

### Integração com pipeline.py
Em `pipeline.py`, após `set_status(piece_id, "pending_approval")`:
```python
# Trigger Friday notification (non-blocking)
asyncio.create_task(friday_notify_pending_approval())
```

---

## Integration Verifications

- [ ] Cron `content_pipeline_tick` avança peças presas (chamar endpoint manualmente para testar)
- [ ] Cron `content_publisher_tick` publica peça `scheduled` com horário vencido
- [ ] Cron `content_brain_sync` ingere peças sem `brain_chunk_id`
- [ ] Friday envia mensagem WhatsApp quando peça atinge `pending_approval`
- [ ] Friday não envia duplicatas em menos de 1h
- [ ] Friday notifica falha de publicação (`publish_failed`)
- [ ] Falha em uma peça não impede processamento das demais no mesmo tick

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `runtime/crons/content.py` | Criar | 3 crons: pipeline_tick, publisher_tick, brain_sync |
| `runtime/content/pipeline.py` | Atualizar | Trigger Friday notification ao atingir pending_approval |
| `runtime/content/publisher.py` | Atualizar | Trigger Friday notification em publish_failed |
| `tests/test_content_crons.py` | Criar | Testes: tick lógica, publisher tick, brain sync, Friday anti-spam |
