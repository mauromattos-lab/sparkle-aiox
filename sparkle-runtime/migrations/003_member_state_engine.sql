-- ============================================================
-- Migration 003: Member State Engine (S5-02)
-- ============================================================
-- Três tabelas:
--   members             — perfil base do membro (identificado por phone)
--   member_states       — estado EAV: chave/valor por membro (flexível, sem schema fixo)
--   member_interactions — log de interações por membro (personagem, canal, sentimento)
-- ============================================================

-- ============================================================
-- MEMBERS
-- Perfil base de cada usuário/lead que interage com qualquer
-- personagem ou canal da Sparkle.
-- Identificador primário: phone (E.164 ou formato local — sem normalização forçada).
-- ============================================================
CREATE TABLE IF NOT EXISTS members (
    phone           TEXT          PRIMARY KEY,
    name            TEXT,
    email           TEXT,
    tags            JSONB         NOT NULL DEFAULT '[]'::jsonb,
    -- Tags são strings livres: ex. ["vip", "lead-quente", "habito-positivo"]
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_members_email ON members (email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_members_tags  ON members USING gin (tags);

COMMENT ON TABLE  members       IS 'Perfil base de membros/usuários que interagem com personagens Sparkle';
COMMENT ON COLUMN members.phone IS 'Identificador principal — número de telefone (formato livre, sem normalização)';
COMMENT ON COLUMN members.tags  IS 'Array JSON de strings livres para segmentação (ex: ["vip", "lead-quente"])';

-- Trigger updated_at
CREATE OR REPLACE FUNCTION update_members_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_members_updated_at
  BEFORE UPDATE ON members
  FOR EACH ROW EXECUTE FUNCTION update_members_updated_at();


-- ============================================================
-- MEMBER_STATES
-- EAV (Entity-Attribute-Value) para estado do membro.
-- Flexível: qualquer chave pode ser definida por qualquer agente/personagem.
-- Sem schema fixo — evolui conforme os personagens precisam.
--
-- Exemplos de keys:
--   objetivo_saude    → "perder 10kg"
--   humor_hoje        → "ansioso"
--   nivel_habito      → "iniciante"
--   ultimo_check_in   → "2026-04-01"
-- ============================================================
CREATE TABLE IF NOT EXISTS member_states (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    phone       TEXT        NOT NULL REFERENCES members(phone) ON DELETE CASCADE,
    key         TEXT        NOT NULL,
    value       TEXT        NOT NULL,
    set_by      TEXT        NOT NULL DEFAULT 'system',
    -- Quem definiu: agent_id, character slug, "system", "user"
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Unique constraint to enable upsert on_conflict="phone,key"
CREATE UNIQUE INDEX IF NOT EXISTS idx_member_states_phone_key
    ON member_states (phone, key);

CREATE INDEX IF NOT EXISTS idx_member_states_phone  ON member_states (phone);
CREATE INDEX IF NOT EXISTS idx_member_states_key    ON member_states (key);

COMMENT ON TABLE  member_states        IS 'Estado EAV por membro — chave/valor livre, evolui com os personagens';
COMMENT ON COLUMN member_states.key    IS 'Nome do atributo de estado (ex: objetivo_saude, humor_hoje)';
COMMENT ON COLUMN member_states.value  IS 'Valor do atributo (sempre texto — sem tipagem forçada)';
COMMENT ON COLUMN member_states.set_by IS 'Quem definiu o valor: agent_id, character slug ou "system"';

-- Trigger updated_at
CREATE OR REPLACE FUNCTION update_member_states_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_member_states_updated_at
  BEFORE UPDATE ON member_states
  FOR EACH ROW EXECUTE FUNCTION update_member_states_updated_at();


-- ============================================================
-- MEMBER_INTERACTIONS
-- Log de interações: qual personagem, qual canal, resumo, sentimento.
-- Nunca deletado — é o histórico de relacionamento do membro com o universo Sparkle.
-- Usado em get_member_context_for_agent() para injetar memória no system_prompt.
-- ============================================================
CREATE TABLE IF NOT EXISTS member_interactions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    phone           TEXT        NOT NULL REFERENCES members(phone) ON DELETE CASCADE,
    character_id    TEXT,
    -- Slug do personagem (ex: "finch") — nullable se interação foi com agente interno
    channel         TEXT        NOT NULL DEFAULT 'whatsapp',
    -- "whatsapp" | "instagram" | "portal" | "community" | "internal"
    summary         TEXT        NOT NULL DEFAULT '',
    -- Resumo da interação (1-2 frases, gerado por quem registra)
    sentiment       TEXT,
    -- "positivo" | "neutro" | "negativo" | "ansioso" | null (não avaliado)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índice principal: buscar interações por membro em ordem cronológica reversa
CREATE INDEX IF NOT EXISTS idx_member_interactions_phone
    ON member_interactions (phone, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_member_interactions_character
    ON member_interactions (character_id) WHERE character_id IS NOT NULL;

COMMENT ON TABLE  member_interactions              IS 'Log de interações do membro com personagens e canais Sparkle';
COMMENT ON COLUMN member_interactions.character_id IS 'Slug do personagem (ex: finch). Null se interação não foi com personagem.';
COMMENT ON COLUMN member_interactions.summary      IS 'Resumo 1-2 frases da interação — injetado no contexto do agente';
COMMENT ON COLUMN member_interactions.sentiment    IS 'Sentimento observado: positivo, neutro, negativo, ansioso. Null = não avaliado.';


-- ============================================================
-- RLS
-- Service role bypasses RLS (Runtime usa service key).
-- ============================================================
ALTER TABLE members              ENABLE ROW LEVEL SECURITY;
ALTER TABLE member_states        ENABLE ROW LEVEL SECURITY;
ALTER TABLE member_interactions  ENABLE ROW LEVEL SECURITY;
