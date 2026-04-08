-- Migration 018 — W1-FRIDAY-1: Tabela mauro_dna
-- Armazena os traços do DNA do Mauro de forma estruturada.
-- Acesso restrito a service_role (RLS habilitado).

CREATE TABLE IF NOT EXISTS mauro_dna (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dna_type TEXT NOT NULL CHECK (dna_type IN (
        'valores',
        'preferencias',
        'cultura_pop',
        'tom_comunicacao',
        'pilares_pessoais',
        'visao_negocio',
        'gatilhos_atencao'
    )),
    key TEXT NOT NULL,
    content TEXT NOT NULL,
    confidence FLOAT DEFAULT 0.8,
    source TEXT NOT NULL CHECK (source IN ('conversa', 'manual', 'extraction')),
    extracted_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para consultas frequentes
CREATE INDEX IF NOT EXISTS idx_mauro_dna_type ON mauro_dna (dna_type);
CREATE INDEX IF NOT EXISTS idx_mauro_dna_key ON mauro_dna (key);

-- RLS: acesso somente via service_role
ALTER TABLE mauro_dna ENABLE ROW LEVEL SECURITY;

-- Bloqueia todo acesso público (anon role)
CREATE POLICY "mauro_dna_no_public_access"
    ON mauro_dna
    FOR ALL
    TO public
    USING (false);
