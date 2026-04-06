---
epic: EPIC-CONTENT-ZENYA — Domínio Conteúdo (Zenya-First)
story: CONTENT-1.1
title: "Migration + Modelo de Dados (content_pieces, calendar)"
status: TODO
priority: P0
executor: "@dev"
sprint: Content Wave 1
prd: docs/prd/domain-content-zenya-prd.md
architecture: docs/architecture/domain-content-zenya-architecture.md
squad: squads/content/
depends_on: [CONTENT-0.1]
unblocks: [CONTENT-1.2, CONTENT-1.3, CONTENT-1.4]
estimated_effort: 2-3h de agente (@dev)
---

# Story 1.1 — Migration + Modelo de Dados

**Sprint:** Content Wave 1
**Status:** `TODO`
**Sequência:** 2 de 13
**PRD:** `docs/prd/domain-content-zenya-prd.md`
**Architecture:** `docs/architecture/domain-content-zenya-architecture.md`

---

## User Story

> Como sistema,
> quero ter as tabelas `content_pieces` e `content_calendar` criadas no Supabase com todos os campos e índices necessários,
> para que o pipeline de conteúdo possa registrar e rastrear cada peça em qualquer estado do ciclo de vida.

---

## Contexto Técnico

**Estado atual:** Nenhuma tabela de conteúdo existe no Supabase.

**Estado alvo:** Tabelas `content_pieces` e `content_calendar` criadas, com índices, e schema validado. Esta story é pré-requisito para todas as stories de produção (1.2–1.6).

---

## Acceptance Criteria

- [ ] **AC1** — Tabela `content_pieces` criada conforme schema da Architecture doc, com todos os campos: `id`, `creator_id`, `platform`, `style`, `status`, `theme`, `mood`, `brief_notes`, `image_prompt`, `image_url`, `video_prompt`, `video_url`, `voice_script`, `audio_url`, `caption`, `final_url`, `approved_by`, `approved_at`, `rejection_reason`, `mauro_edits`, `scheduled_at`, `published_at`, `published_url`, `style_ref_ids`, `brain_chunk_id`, `pipeline_log`, `error_log`, `created_at`, `updated_at`
- [ ] **AC2** — `status` aceita exatamente os 15 estados definidos (via CHECK constraint ou enum): `briefed`, `image_generating`, `image_done`, `video_generating`, `video_done`, `voice_generating`, `assembly_pending`, `assembly_done`, `pending_approval`, `approved`, `scheduled`, `published`, `rejected`, `image_failed`, `video_failed`, `assembly_failed`, `publish_failed`
- [ ] **AC3** — Índices criados: `idx_content_pieces_status`, `idx_content_pieces_creator`, `idx_content_pieces_scheduled`
- [ ] **AC4** — Tabela `content_calendar` criada com: `id`, `target_date`, `creator_id`, `platform`, `theme`, `style`, `content_piece_id` (FK para content_pieces), `status`, `created_at`
- [ ] **AC5** — Migration aplicada com sucesso via `mcp__supabase__apply_migration` sem erros
- [ ] **AC6** — INSERT de teste em `content_pieces` com `status='briefed'` e SELECT confirmam schema correto

---

## Dev Notes

### Schema completo — content_pieces
```sql
CREATE TABLE content_pieces (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creator_id      TEXT NOT NULL DEFAULT 'zenya',
  platform        TEXT NOT NULL DEFAULT 'instagram_reels',
  style           TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'briefed',

  theme           TEXT,
  mood            TEXT,
  brief_notes     TEXT,

  image_prompt    TEXT,
  image_url       TEXT,
  video_prompt    TEXT,
  video_url       TEXT,
  voice_script    TEXT,
  audio_url       TEXT,
  caption         TEXT,
  final_url       TEXT,

  approved_by     TEXT,
  approved_at     TIMESTAMPTZ,
  rejection_reason TEXT,
  mauro_edits     JSONB,

  scheduled_at    TIMESTAMPTZ,
  published_at    TIMESTAMPTZ,
  published_url   TEXT,

  style_ref_ids   UUID[],
  brain_chunk_id  UUID,
  pipeline_log    JSONB DEFAULT '[]',
  error_log       JSONB DEFAULT '[]',

  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_content_pieces_status ON content_pieces(status);
CREATE INDEX idx_content_pieces_creator ON content_pieces(creator_id);
CREATE INDEX idx_content_pieces_scheduled ON content_pieces(scheduled_at)
  WHERE scheduled_at IS NOT NULL;
```

### Schema completo — content_calendar
```sql
CREATE TABLE content_calendar (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  target_date     DATE NOT NULL,
  creator_id      TEXT NOT NULL DEFAULT 'zenya',
  platform        TEXT NOT NULL DEFAULT 'instagram_reels',
  theme           TEXT,
  style           TEXT,
  content_piece_id UUID REFERENCES content_pieces(id),
  status          TEXT DEFAULT 'planned',
  created_at      TIMESTAMPTZ DEFAULT now()
);
```

---

## Integration Verifications

- [ ] `SELECT column_name FROM information_schema.columns WHERE table_name = 'content_pieces'` retorna todos os campos esperados
- [ ] INSERT com `status = 'briefed'` bem-sucedido
- [ ] INSERT com `status = 'invalid_status'` falha com constraint (se implementado como CHECK)
- [ ] Tabela `content_calendar` com FK para `content_pieces` aceita `content_piece_id` válido e rejeita inválido

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `migrations/XXX_content_pieces.sql` | Criar | Tabelas content_pieces + content_calendar + índices |
