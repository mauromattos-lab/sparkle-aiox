---
epic: EPIC-CLIENT-LIFECYCLE — Gestão do Ciclo de Vida do Cliente
story: LIFECYCLE-1.1
title: "Migration e Modelo de Dados (Fundação)"
status: DONE
priority: Alta
executor: "@dev (implementação)"
sprint: Client Lifecycle Wave 1
prd: docs/prd/domain-client-lifecycle-prd.md
architecture: docs/architecture/domain-client-lifecycle-architecture.md
squad: squads/client-lifecycle/
depends_on: []
unblocks: [LIFECYCLE-1.2, LIFECYCLE-1.3, LIFECYCLE-1.4]
estimated_effort: 2-3h de agente (@dev)
---

# Story 1.1 — Migration e Modelo de Dados (Fundação)

**Sprint:** Client Lifecycle Wave 1
**Status:** `DONE`
**Sequência:** 1 de 4
**PRD:** `docs/prd/domain-client-lifecycle-prd.md`
**Architecture:** `docs/architecture/domain-client-lifecycle-architecture.md`
**Squad:** `squads/client-lifecycle/`

---

## User Story

> Como sistema Sparkle Runtime,
> quero ter tabelas estruturadas para armazenar health score, milestones, oportunidades de upsell e NPS dos clientes,
> para que todos os módulos do ciclo de vida tenham uma base de dados consistente e auditável.

---

## Contexto Técnico

**Por que agora:** O domínio Client Lifecycle precisa de persistência estruturada antes que qualquer engine (health score, milestones, intervenção) possa ser construída. Esta story cria a fundação de dados para todas as demais.

**Estado atual:**
- Tabela `zenya_clients` existe no Supabase e contém os clientes ativos
- Não existem tabelas para health score, milestones, upsell ou NPS
- Migrations existentes vão até 013 (ou 014 dependendo do estado atual)

**Estado alvo:**
- Migration `015_client_lifecycle_tables.sql` aplicada
- 4 novas tabelas criadas com FK para `zenya_clients`
- Indexes otimizados para queries frequentes
- RLS habilitado em todas as tabelas

**Arquivo a criar:**
- `sparkle-runtime/migrations/015_client_lifecycle_tables.sql`

**SQL (conforme Architecture Doc Section 3):**

```sql
-- ============================================================
-- Migration 015: Client Lifecycle Tables
-- Domain: client-lifecycle
-- ============================================================

-- 1. client_health — Health Score por cliente
CREATE TABLE IF NOT EXISTS client_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES zenya_clients(id) ON DELETE CASCADE,
    score INTEGER NOT NULL CHECK (score >= 0 AND score <= 100),
    classification TEXT NOT NULL CHECK (classification IN ('healthy', 'attention', 'risk', 'critical')),
    signals JSONB DEFAULT '{}',
    alert_sent BOOLEAN DEFAULT FALSE,
    calculated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_client_health_client_id ON client_health(client_id);
CREATE INDEX idx_client_health_classification ON client_health(classification);
CREATE INDEX idx_client_health_calculated_at ON client_health(calculated_at DESC);

ALTER TABLE client_health ENABLE ROW LEVEL SECURITY;

-- 2. client_milestones — Marcos do cliente
CREATE TABLE IF NOT EXISTS client_milestones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES zenya_clients(id) ON DELETE CASCADE,
    milestone_type TEXT NOT NULL,
    achieved_at TIMESTAMPTZ DEFAULT NOW(),
    ttv_days INTEGER,
    metadata JSONB DEFAULT '{}',
    UNIQUE(client_id, milestone_type)
);

CREATE INDEX idx_client_milestones_client_id ON client_milestones(client_id);
CREATE INDEX idx_client_milestones_type ON client_milestones(milestone_type);

ALTER TABLE client_milestones ENABLE ROW LEVEL SECURITY;

-- 3. upsell_opportunities — Oportunidades de upsell detectadas
CREATE TABLE IF NOT EXISTS upsell_opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES zenya_clients(id) ON DELETE CASCADE,
    opportunity_type TEXT NOT NULL,
    signal TEXT,
    score INTEGER NOT NULL CHECK (score >= 0 AND score <= 100),
    status TEXT NOT NULL DEFAULT 'detected' CHECK (status IN ('detected', 'approached', 'converted', 'dismissed')),
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    approached_at TIMESTAMPTZ,
    notes TEXT
);

CREATE INDEX idx_upsell_opportunities_client_id ON upsell_opportunities(client_id);
CREATE INDEX idx_upsell_opportunities_status ON upsell_opportunities(status);

ALTER TABLE upsell_opportunities ENABLE ROW LEVEL SECURITY;

-- 4. client_nps — Net Promoter Score coletado
CREATE TABLE IF NOT EXISTS client_nps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES zenya_clients(id) ON DELETE CASCADE,
    score INTEGER NOT NULL CHECK (score >= 0 AND score <= 10),
    feedback TEXT,
    collected_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_client_nps_client_id ON client_nps(client_id);
CREATE INDEX idx_client_nps_collected_at ON client_nps(collected_at DESC);

ALTER TABLE client_nps ENABLE ROW LEVEL SECURITY;
```

---

## Acceptance Criteria

- [ ] **AC1** — Migration `015_client_lifecycle_tables.sql` existe em `sparkle-runtime/migrations/`
- [ ] **AC2** — Tabela `client_health` criada com colunas: id, client_id (FK zenya_clients), score (0-100), classification (healthy/attention/risk/critical), signals JSONB, alert_sent boolean, calculated_at
- [ ] **AC3** — Tabela `client_milestones` criada com colunas: id, client_id (FK), milestone_type, achieved_at, ttv_days, metadata JSONB, UNIQUE(client_id, milestone_type)
- [ ] **AC4** — Tabela `upsell_opportunities` criada com colunas: id, client_id (FK), opportunity_type, signal, score (0-100), status (detected/approached/converted/dismissed), detected_at, approached_at, notes
- [ ] **AC5** — Tabela `client_nps` criada com colunas: id, client_id (FK), score (0-10), feedback, collected_at
- [ ] **AC6** — Indexes criados em todas as colunas frequentemente consultadas (client_id, classification, status, collected_at, calculated_at)
- [ ] **AC7** — RLS habilitado em todas as 4 tabelas
- [ ] **AC8** — FK constraints funcionam: inserir com client_id inexistente falha; deletar cliente cascateia

---

## Integration Verifications

- [ ] Migration aplica sem erros via `mcp__supabase__apply_migration`
- [ ] FK constraints validadas: INSERT com client_id invalido retorna erro
- [ ] CASCADE funciona: DELETE em zenya_clients remove registros dependentes
- [ ] RLS policies podem ser consultadas via `pg_policies`
- [ ] Nenhuma tabela existente foi alterada ou quebrada

---

## File List

| Arquivo | Acao |
|---------|------|
| `sparkle-runtime/migrations/015_client_lifecycle_tables.sql` | CRIAR |
