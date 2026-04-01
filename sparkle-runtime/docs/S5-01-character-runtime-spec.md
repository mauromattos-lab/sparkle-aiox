# S5-01 — Character Runtime: Personagens como Objetos Supabase
_Spec entregue por @architect (Aria) para @dev implementar._
_Data: 2026-04-01_

---

## Contexto e Decisão Arquitetural Central

### Personagem é subtipo de `agent` ou tabela separada?

**Decisão: tabela separada `characters`, com FK para `agents`.**

Justificativa:

| Critério | `agent` (extensão) | `characters` (separada) |
|----------|--------------------|------------------------|
| Natureza | Executor de task, stateless | Entidade com identidade, lore, voz, canais — stateful por design |
| Ciclo de vida | Ativado → executa → dorme | Existe de forma contínua, tem arco narrativo que evolui |
| Responsabilidade | Processar mensagens de sistema | Ter personalidade, história, distribuição, voz própria |
| Escala | 9–15 agentes internos | Potencialmente 100+ personagens, alguns com múltiplos canais |
| Dados extras | Nenhum (model + prompt basta) | voice_id, avatar_url, traits jsonb, lore, active_channels — muito acima do schema de `agents` |

Um `character` **possui** um `agent` (que é quem conversa de fato). A tabela `characters` é o identity record. A tabela `agents` é o execution record. Separar permite:
- Criar personagem sem ter agente ativo ainda (lore-only, pré-lançamento estilo Overwatch)
- Ter múltiplos agentes para o mesmo personagem (canal WhatsApp vs canal Instagram)
- Evoluir soul_prompt de personagem sem mexer na tabela de agentes operacionais

---

## Parte 1 — SQL Completo (pronto para executar no Supabase)

Execute em sequência no SQL Editor do projeto `gqhdspayjtiijcqklbys`.

### 1.1 — Tabela `characters`

```sql
-- S5-01: Character Runtime — tabela principal de personagens
-- Cada personagem é uma entidade de IP com identidade, voz, lore e canais de distribuição.
-- Separada de `agents`: personagem é quem o personagem É. Agente é quem executa.

CREATE TABLE IF NOT EXISTS characters (
  -- Identidade
  id              uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  slug            text          NOT NULL UNIQUE, -- ex: "finch", "pip", "juno"
  name            text          NOT NULL,         -- ex: "Finch", "Pip", "Juno"
  tagline         text,                           -- ex: "Seu coach de hábitos e vida intencional"

  -- Personalidade e alma
  soul_prompt     text          NOT NULL,         -- system prompt base do personagem (2-4 parágrafos)
  personality_traits jsonb      NOT NULL DEFAULT '[]'::jsonb,
  -- Ex: ["direto", "empático", "não-condescendente", "usa analogias do cotidiano", "não dá atalhos fáceis"]

  specialty       text          NOT NULL,
  -- Ex: "coaching de hábitos e desenvolvimento pessoal"

  values          jsonb         NOT NULL DEFAULT '[]'::jsonb,
  -- Ex: ["disciplina como liberdade", "saúde como fundação", "prosperidade não é sorte"]

  -- Voz e visual
  voice_id        text,         -- ElevenLabs voice ID (nullable: personagens sem voz ainda)
  voice_model     text          NOT NULL DEFAULT 'eleven_multilingual_v2',
  avatar_url      text,         -- URL pública (Supabase Storage ou CDN)
  avatar_style    text,         -- Ex: "realistic", "anime", "illustrated"

  -- Canais de distribuição
  active_channels jsonb         NOT NULL DEFAULT '[]'::jsonb,
  -- Ex: ["whatsapp", "instagram", "youtube", "community"]
  -- Usado para roteamento: character_channel_router saberá qual agent_id acionar por canal

  -- Relacionamento com execução
  primary_agent_id text         REFERENCES agents(agent_id) ON DELETE SET NULL,
  -- O agente principal que processa mensagens deste personagem
  -- Nullable: personagem pode existir sem agente ativo (pre-launch / lore-only)

  -- Lore e narrativa
  lore_status     text          NOT NULL DEFAULT 'hidden',
  -- Estados: "hidden" (não público) | "hinted" (hints no ar) | "revealed" (público)
  -- Pipeline de lançamento estilo Overwatch: hidden → hinted → revealed

  universe_connections jsonb    NOT NULL DEFAULT '[]'::jsonb,
  -- Ex: [{"character_slug": "finch", "relationship": "mentor", "public": false}]
  -- Relacionamentos com outros personagens do universo Sparkle

  -- Estado e controle
  active          boolean       NOT NULL DEFAULT true,
  created_at      timestamptz   NOT NULL DEFAULT now(),
  updated_at      timestamptz   NOT NULL DEFAULT now()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_characters_slug   ON characters (slug);
CREATE INDEX IF NOT EXISTS idx_characters_active ON characters (active) WHERE active = true;
CREATE INDEX IF NOT EXISTS idx_characters_lore   ON characters (lore_status);

-- Trigger para updated_at automático
CREATE OR REPLACE FUNCTION update_characters_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_characters_updated_at
  BEFORE UPDATE ON characters
  FOR EACH ROW EXECUTE FUNCTION update_characters_updated_at();

-- Comentários
COMMENT ON TABLE characters IS 'Personagens do universo Sparkle — IP com identidade, voz, lore e canais de distribuição';
COMMENT ON COLUMN characters.slug IS 'Identificador único de URL (ex: finch, pip, juno)';
COMMENT ON COLUMN characters.soul_prompt IS 'Prompt base que define a alma do personagem. Injetado como system no /agent/invoke via primary_agent_id';
COMMENT ON COLUMN characters.personality_traits IS 'Array de strings: traços de personalidade que guiam o tom de todas as respostas';
COMMENT ON COLUMN characters.values IS 'Crenças fundacionais do personagem — filtro de valores ativo em todas as interações';
COMMENT ON COLUMN characters.voice_id IS 'ID da voz ElevenLabs. Null = sem voz ainda (personagem pré-lançamento)';
COMMENT ON COLUMN characters.active_channels IS 'Canais onde o personagem opera: whatsapp, instagram, youtube, community, tiktok';
COMMENT ON COLUMN characters.primary_agent_id IS 'FK para agents.agent_id — quem executa as conversas deste personagem';
COMMENT ON COLUMN characters.lore_status IS 'Pipeline de reveal: hidden → hinted → revealed. Controla visibilidade pública';
COMMENT ON COLUMN characters.universe_connections IS 'Relacionamentos com outros personagens (público ou interno)';
```

### 1.2 — Tabela `character_lore`

```sql
-- S5-01: Banco de lore — histórias, arcos e reveals programados por personagem
-- Separado de `characters` para permitir múltiplos arcos sem poluir a linha principal

CREATE TABLE IF NOT EXISTS character_lore (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  character_id    uuid        NOT NULL REFERENCES characters(id) ON DELETE CASCADE,

  -- Conteúdo do lore
  lore_type       text        NOT NULL,
  -- "origin"       — história de origem do personagem
  -- "arc"          — arco narrativo em progresso
  -- "hint"         — fragmento liberado antes do reveal (teaser público)
  -- "relationship" — história de relacionamento com outro personagem
  -- "milestone"    — evento importante na história do personagem
  -- "secret"       — informação interna, nunca pública

  title           text        NOT NULL,
  content         text        NOT NULL,

  -- Controle de visibilidade
  is_public       boolean     NOT NULL DEFAULT false,
  -- false = apenas agentes internos sabem | true = pode ser narrado pelo personagem

  reveal_after    timestamptz,
  -- null = disponível imediatamente | timestamp = libera automaticamente na data

  -- Metadados
  tags            jsonb       NOT NULL DEFAULT '[]'::jsonb,
  -- Ex: ["origem", "saude", "pilares", "mauro-universe"]

  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lore_character   ON character_lore (character_id);
CREATE INDEX IF NOT EXISTS idx_lore_type        ON character_lore (lore_type);
CREATE INDEX IF NOT EXISTS idx_lore_public      ON character_lore (is_public) WHERE is_public = true;

COMMENT ON TABLE character_lore IS 'Banco de histórias, arcos e reveals por personagem. Alimenta RAG das conversas e pipeline de lançamento.';
COMMENT ON COLUMN character_lore.reveal_after IS 'Timestamp de liberação automática. null = disponível agora.';
```

### 1.3 — Tabela `character_conversations`

```sql
-- S5-01: Histórico de conversas por personagem + usuário (multi-canal)
-- Separado de `conversation_history` (que é exclusivo da Friday/Mauro)

CREATE TABLE IF NOT EXISTS character_conversations (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  character_id    uuid        NOT NULL REFERENCES characters(id) ON DELETE CASCADE,

  -- Identificação do usuário (independente de canal)
  user_identifier text        NOT NULL,
  -- Ex: "55119999999" (WhatsApp), "@username" (Instagram), "user_uuid" (comunidade)

  channel         text        NOT NULL,
  -- "whatsapp" | "instagram" | "youtube_comment" | "community" | "portal"

  role            text        NOT NULL CHECK (role IN ('user', 'character')),
  content         text        NOT NULL,
  metadata        jsonb       NOT NULL DEFAULT '{}'::jsonb,
  -- Ex: {"message_id": "...", "reaction": "❤️", "tts_url": "..."}

  created_at      timestamptz NOT NULL DEFAULT now()
);

-- Índice principal para buscar histórico de conversa por usuário + personagem
CREATE INDEX IF NOT EXISTS idx_char_conv_lookup
  ON character_conversations (character_id, user_identifier, channel, created_at DESC);

COMMENT ON TABLE character_conversations IS 'Histórico de conversas de personagens com usuários. Multi-canal. Separado do conversation_history da Friday.';
```

---

## Parte 2 — Arquitetura de Invocação

### Fluxo de chamada

```
Usuário no WhatsApp
        ↓
  /character/message
  {slug: "finch", message: "...", user_identifier: "55119...", channel: "whatsapp"}
        ↓
  character_handler.py
        ↓
  1. Busca character por slug → obtém soul_prompt, voice_id, primary_agent_id
  2. Busca últimas 5 mensagens de character_conversations (character_id + user_identifier)
  3. Busca lore relevante (character_lore WHERE is_public = true, RAG simples por agora)
  4. Monta system_prompt = soul_prompt + lore_context + conversation_context
  5. Chama /agent/invoke com primary_agent_id + message + context enriquecido
  6. Salva par user/character em character_conversations
  7. Se voice_id ativo → TTS via ElevenLabs com a voz do personagem
  8. Retorna {response, audio_url?, character_slug, model}
```

### Por que `/character/message` e não `/agent/invoke` direto?

`/agent/invoke` é stateless — não sabe nada de lore, histórico de conversa por usuário, nem voz específica do personagem. Para personagens, precisamos de:
1. Injeção de lore como contexto (RAG futuro, texto por agora)
2. Histórico de conversa persistente por (personagem, usuário, canal)
3. TTS com voice_id específico do personagem — diferente da voz da Friday
4. Pipeline de reveal: verificar `lore_status` antes de responder

O `/agent/invoke` continua sendo chamado internamente — apenas com contexto já enriquecido pelo `character_handler`.

### Conversação stateful por usuário

- Histórico: `character_conversations` filtrado por `(character_id, user_identifier, channel)`
- Janela de contexto: últimas 8 mensagens (4 trocas) — suficiente para coerência, não desperdiça tokens
- Sem Redis necessário: Supabase é suficiente para leitura de 8 linhas por request

### Voz (ElevenLabs)

- `tts.py` já existe com `eleven_multilingual_v2` e upload para Supabase Storage
- Personagens usam `voice_id` da tabela `characters` em vez do voice ID hardcoded da Friday
- Parametrizar `tts.py` para aceitar `voice_id` externo — uma linha de mudança
- Áudio armazenado no bucket `character-audio` (criar separado de `friday-audio`)

---

## Parte 3 — Finch: Spec de Personagem

### Identidade

| Campo | Valor |
|-------|-------|
| `slug` | `finch` |
| `name` | `Finch` |
| `tagline` | "O único coach que não te deixa mentir pra si mesmo" |
| `specialty` | "Coaching de hábitos, saúde pessoal e desenvolvimento intencional" |
| `avatar_style` | `illustrated` — traços definidos, expressão séria mas acolhedora |
| `lore_status` | `hidden` (pré-lançamento) |
| `active_channels` | `["whatsapp"]` (MVP) |

### `personality_traits`

```json
[
  "direto sem ser duro",
  "faz perguntas antes de dar respostas",
  "não oferece atalhos fáceis",
  "usa analogias concretas do cotidiano",
  "celebra consistência, não perfeição",
  "silêncio calculado: não responde rápido demais",
  "lembra o que o usuário disse antes e cobra"
]
```

### `values`

```json
[
  "disciplina é a forma mais alta de liberdade",
  "saúde é a fundação de tudo, não um projeto paralelo",
  "prosperidade começa na mente, não na conta bancária",
  "hábitos pequenos e consistentes vencem motivação em rajadas",
  "o corpo sabe o que a mente nega"
]
```

### `soul_prompt`

```
Você é Finch. Não um assistente, não um chatbot — um coach de hábitos que existe para ajudar pessoas a construírem a versão delas mesmas que elas já sabem que é possível, mas ainda não tiveram coragem de ir atrás de forma consistente.

Você trabalha com os cinco pilares da vida intencional: saúde física, mente clara, alma conectada, finanças sustentáveis e relacionamentos que nutrem. Você não trata esses pilares como caixas separadas — você sabe que quando um racha, todos enfraquecem. Quando um é trabalhado com seriedade, todos sobem.

Seu jeito de conversar é direto, sem aspereza. Você faz perguntas antes de dar respostas. Você não aceita "tentei mas não deu" sem explorar o que de fato aconteceu. Você celebra a consistência de 3 dias, não só o resultado de 30. E você lembra o que a pessoa te disse antes — porque você presta atenção de verdade, e cobra com gentileza quando a ação não segue o que foi dito.

Você não existe para agradar. Existe para acompanhar. A diferença é enorme.
```

### Modelo sugerido

**`claude-sonnet-4-6`**

Justificativa: Finch é o produto — não é um agente de triagem nem de classificação. Personagens que existem para o mundo exigem qualidade de resposta que Haiku não entrega de forma consistente. O custo de Sonnet é justificado porque:
1. Cada conversa de Finch com um usuário é uma interação de produto, não de suporte
2. Finch precisa de memória contextual dos 5 parágrafos de soul_prompt + lore + histórico
3. A resposta de Finch É o produto — qualidade aqui é diferencial de mercado

---

## Parte 4 — Spec Técnica para @dev

### Estrutura de arquivos a criar

```
sparkle-runtime/
  runtime/
    characters/
      __init__.py        ← vazio
      router.py          ← APIRouter com POST /message e GET /{slug}
      handler.py         ← lógica: buscar character → enriquecer contexto → invocar agente → TTS
      lore_loader.py     ← busca lore público de um personagem para injetar no prompt
    utils/
      tts.py             ← MODIFICAR: aceitar voice_id como parâmetro (hoje hardcoded)
  main.py                ← include_router do characters_router
```

### Endpoints novos

#### `POST /character/message`

```python
class CharacterMessageRequest(BaseModel):
    slug: str                          # ex: "finch"
    message: str
    user_identifier: str               # ex: "5511999999999"
    channel: str = "whatsapp"
    respond_with_audio: bool = False   # True → gera TTS com voice do personagem

class CharacterMessageResponse(BaseModel):
    response: str
    character_slug: str
    model: str
    audio_url: str | None = None
```

#### `GET /character/{slug}`

Retorna perfil público do personagem (sem soul_prompt, sem lore secreto):
```json
{
  "slug": "finch",
  "name": "Finch",
  "tagline": "...",
  "specialty": "...",
  "avatar_url": "...",
  "active_channels": ["whatsapp"],
  "lore_status": "hidden"
}
```

### Lógica do `handler.py` — passo a passo

```python
async def handle_character_message(slug, message, user_identifier, channel, respond_with_audio):

    # 1. Buscar personagem
    character = supabase.table("characters")
        .select("*")
        .eq("slug", slug)
        .eq("active", True)
        .maybe_single()
        .execute().data
    # → 404 se None

    # 2. Verificar se tem agente vinculado
    if not character["primary_agent_id"]:
        raise HTTPException(503, "Character has no active agent")

    # 3. Buscar histórico de conversa (últimas 8 mensagens)
    history = supabase.table("character_conversations")
        .select("role, content")
        .eq("character_id", character["id"])
        .eq("user_identifier", user_identifier)
        .eq("channel", channel)
        .order("created_at", desc=True)
        .limit(8)
        .execute().data
    history.reverse()  # cronológico

    # 4. Buscar lore público (lore_loader.py)
    lore_context = await load_public_lore(character["id"])
    # → string formatada para injetar no prompt (máx 500 tokens)

    # 5. Montar system_prompt enriquecido
    system = character["soul_prompt"]
    if lore_context:
        system += f"\n\n--- Contexto sobre sua história ---\n{lore_context}"

    # 6. Chamar /agent/invoke internamente (via handler direto, não HTTP)
    from runtime.agents.handler import invoke_agent
    result = await invoke_agent(
        agent_id=character["primary_agent_id"],
        message=message,
        context={
            "system_prompt_override": system,   # sobrescreve o system do agent
            "conversation_history": history,
            "user_identifier": user_identifier,
            "channel": channel
        }
    )

    # 7. Salvar no histórico
    supabase.table("character_conversations").insert([
        {"character_id": character["id"], "user_identifier": user_identifier,
         "channel": channel, "role": "user", "content": message},
        {"character_id": character["id"], "user_identifier": user_identifier,
         "channel": channel, "role": "character", "content": result["response"]}
    ]).execute()

    # 8. TTS se solicitado e voice_id disponível
    audio_url = None
    if respond_with_audio and character.get("voice_id"):
        audio_url = await generate_tts(result["response"], voice_id=character["voice_id"])

    return {"response": result["response"], "character_slug": slug,
            "model": result["model"], "audio_url": audio_url}
```

### Modificação necessária em `tts.py`

A função `generate_tts` (ou equivalente) hoje usa voice ID hardcoded da Friday. Adicionar parâmetro `voice_id: str = None` com fallback para o ID atual. Mudança de uma linha.

### Modificação necessária em `agents/handler.py`

O `invoke_agent` precisa aceitar `system_prompt_override` no `context` para que o character handler possa injetar o soul_prompt do personagem sem depender do `system_prompt` cadastrado na tabela `agents`.

Isso permite que o agente vinculado a um personagem seja um agente genérico (ex: `character-runner`) e o soul_prompt venha sempre da tabela `characters` — separação limpa de responsabilidade.

---

## Parte 5 — Inserts SQL iniciais (Finch)

```sql
-- 1. Inserir agente genérico de execução para personagens
INSERT INTO agents (agent_id, name, system_prompt, model, max_tokens, active)
VALUES (
  'character-runner',
  'Character Runner',
  'Você é um personagem da Sparkle. Seu soul prompt será injetado a cada invocação.',
  'claude-sonnet-4-6',
  1024,
  true
)
ON CONFLICT (agent_id) DO NOTHING;

-- 2. Inserir Finch
INSERT INTO characters (
  slug, name, tagline, specialty,
  soul_prompt,
  personality_traits,
  values,
  voice_id,
  avatar_style,
  active_channels,
  primary_agent_id,
  lore_status
) VALUES (
  'finch',
  'Finch',
  'O único coach que não te deixa mentir pra si mesmo',
  'Coaching de hábitos, saúde pessoal e desenvolvimento intencional',
  'Você é Finch. Não um assistente, não um chatbot — um coach de hábitos que existe para ajudar pessoas a construírem a versão delas mesmas que elas já sabem que é possível, mas ainda não tiveram coragem de ir atrás de forma consistente.

Você trabalha com os cinco pilares da vida intencional: saúde física, mente clara, alma conectada, finanças sustentáveis e relacionamentos que nutrem. Você não trata esses pilares como caixas separadas — você sabe que quando um racha, todos enfraquecem. Quando um é trabalhado com seriedade, todos sobem.

Seu jeito de conversar é direto, sem aspereza. Você faz perguntas antes de dar respostas. Você não aceita "tentei mas não deu" sem explorar o que de fato aconteceu. Você celebra a consistência de 3 dias, não só o resultado de 30. E você lembra o que a pessoa te disse antes — porque você presta atenção de verdade, e cobra com gentileza quando a ação não segue o que foi dito.

Você não existe para agradar. Existe para acompanhar. A diferença é enorme.',
  '["direto sem ser duro","faz perguntas antes de dar respostas","não oferece atalhos fáceis","usa analogias concretas do cotidiano","celebra consistência não perfeição","lembra o que o usuário disse antes e cobra"]'::jsonb,
  '["disciplina é a forma mais alta de liberdade","saúde é a fundação de tudo","prosperidade começa na mente","hábitos pequenos vencem motivação em rajadas","o corpo sabe o que a mente nega"]'::jsonb,
  NULL,           -- voice_id: definir quando voz for escolhida no ElevenLabs
  'illustrated',
  '["whatsapp"]'::jsonb,
  'character-runner',
  'hidden'
);

-- 3. Inserir lore de origem do Finch (interno, não público ainda)
INSERT INTO character_lore (character_id, lore_type, title, content, is_public, tags)
SELECT
  id,
  'origin',
  'De onde vem Finch',
  'Finch nasceu da convicção do Mauro de que o maior problema das pessoas não é falta de informação — é falta de acompanhamento honesto. Ele viu isso nos próprios pilares: saúde, mente, alma, financeiro, relacionamentos. Nenhum falha por falta de conhecimento. Todos falham por falta de alguém que cobre sem julgamento.',
  false,
  '["origem","pilares","mauro-universe"]'::jsonb
FROM characters WHERE slug = 'finch';
```

---

## Checklist @dev

- [ ] Criar `runtime/characters/__init__.py` (vazio)
- [ ] Criar `runtime/characters/lore_loader.py` — busca `character_lore` público por character_id
- [ ] Criar `runtime/characters/handler.py` — lógica completa descrita no Parte 4
- [ ] Criar `runtime/characters/router.py` — `POST /message` + `GET /{slug}`
- [ ] Modificar `runtime/utils/tts.py` — aceitar `voice_id` como parâmetro opcional
- [ ] Modificar `runtime/agents/handler.py` — aceitar `system_prompt_override` em `context`
- [ ] Adicionar `include_router` em `main.py` com prefix `/character`
- [ ] Executar SQL Parte 1 (tabelas `characters`, `character_lore`, `character_conversations`)
- [ ] Executar SQL Parte 5 (insert agent-runner + Finch)
- [ ] Testar `POST /character/message` com slug `finch` e mensagem de teste
- [ ] Verificar `character_conversations` — deve ter 2 linhas (user + character)
- [ ] Testar `GET /character/finch` — deve retornar perfil sem soul_prompt
- [ ] Testar com slug inexistente → deve retornar 404
- [ ] Atualizar `RUNTIME_STATE.md` com novos endpoints e schema

---

## Handoff

Após @dev implementar e @qa validar:
- Registrar em `memory/work_log.md` como `[FUNCIONAL] Character Runtime S5-01`
- Atualizar `RUNTIME_STATE.md` seção Endpoints e Schema
- Próximo passo: escolher voice_id do Finch no ElevenLabs e atualizar o registro
- Próximo personagem: definir Pip (especialidade a confirmar com Mauro)
- Lore pipeline: quando `lore_status` mudar para `hinted`, criar campanha de hints para WhatsApp/Instagram

---

_Spec produzida por @architect (Aria) — 2026-04-01_
_Baseada em: session_aria_elicitation_2026_03_31.md (Leis 6, 7, 12), project_sparkle_vision_complete.md (Layer 3), RUNTIME_STATE.md (schema agents + /agent/invoke), S3-03-agent-invoke-spec.md_
