# Architecture — Domínio Conteúdo (Zenya-First)

**Versão:** 1.0  
**Data:** 2026-04-06  
**Autor:** @architect (Aria)  
**PRD:** `docs/prd/domain-content-zenya-prd.md`  
**Status:** Aprovado para Stories

---

## Posição no Organismo

```
CAMADA 4 — INTERFACE
  Portal (Content Queue View) ←── aprovação visual
  Instagram API              ←── publicação

CAMADA 3 — ÓRGÃO CONTEÚDO (este documento)
  Ideação → Produção → Assembly → Aprovação → Distribuição

CAMADA 2 — BRAIN
  sparkle-lore namespace ←── lore, restrições, histórico

CAMADA 1 — INFRA
  Supabase Storage (assets) | Google Veo 3.1 | ElevenLabs | Creatomate
  Google Gemini Image API | CLIP embeddings | Instagram Graph API
```

Órgão Conteúdo **não se conecta diretamente** a outros órgãos. Toda troca é via Brain:
- Ciclo do Cliente consome conteúdo de engajamento via Brain
- Tráfego solicita criativos via Brain (Fase futura)

---

## Modelo de Dados

### Tabelas novas

#### `content_pieces`
Entidade central — representa uma peça de conteúdo em qualquer estado do pipeline.

```sql
CREATE TABLE content_pieces (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creator_id      TEXT NOT NULL DEFAULT 'zenya',   -- 'zenya' | 'mauro' | client_id
  platform        TEXT NOT NULL DEFAULT 'instagram_reels',
  style           TEXT NOT NULL,                    -- 'cinematic' | 'influencer_natural'
  status          TEXT NOT NULL DEFAULT 'briefed',  -- ver estados abaixo
  
  -- Brief
  theme           TEXT,
  mood            TEXT,
  brief_notes     TEXT,
  
  -- Produção
  image_prompt    TEXT,
  image_url       TEXT,                             -- Supabase Storage path
  video_prompt    TEXT,
  video_url       TEXT,                             -- Supabase Storage path
  voice_script    TEXT,
  audio_url       TEXT,                             -- Supabase Storage path
  caption         TEXT,
  final_url       TEXT,                             -- .mp4 montado (Creatomate)
  
  -- Aprovação
  approved_by     TEXT,
  approved_at     TIMESTAMPTZ,
  rejection_reason TEXT,
  mauro_edits     JSONB,                            -- edições feitas no Portal
  
  -- Publicação
  scheduled_at    TIMESTAMPTZ,
  published_at    TIMESTAMPTZ,
  published_url   TEXT,
  
  -- Metadata
  style_ref_ids   UUID[],                           -- Style Library refs usadas
  brain_chunk_id  UUID,                             -- chunk ingerido no Brain após publicação
  pipeline_log    JSONB DEFAULT '[]',               -- log de cada etapa
  error_log       JSONB DEFAULT '[]',
  
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_content_pieces_status ON content_pieces(status);
CREATE INDEX idx_content_pieces_creator ON content_pieces(creator_id);
CREATE INDEX idx_content_pieces_scheduled ON content_pieces(scheduled_at) WHERE scheduled_at IS NOT NULL;
```

#### Estados do pipeline (`status`)
```
briefed           → brief criado, aguardando produção
image_generating  → imagem em geração
image_done        → imagem gerada, aguardando vídeo
video_generating  → vídeo em geração
video_done        → vídeo gerado, aguardando voz
voice_generating  → áudio em geração
assembly_pending  → todos os assets prontos, aguardando Creatomate
assembly_done     → .mp4 montado, aguardando aprovação
pending_approval  → na fila do Portal para Mauro revisar
approved          → aprovado, aguardando agendamento
scheduled         → agendado para publicação
published         → publicado com sucesso
rejected          → rejeitado por Mauro
image_failed      → falha na geração de imagem
video_failed      → falha na geração de vídeo
assembly_failed   → falha no assembly
publish_failed    → falha na publicação
```

#### `style_library`
Catálogo curado das imagens de referência da Zenya.

```sql
CREATE TABLE style_library (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creator_id    TEXT NOT NULL DEFAULT 'zenya',
  tier          TEXT NOT NULL,                      -- 'A' | 'B' | 'C'
  storage_path  TEXT NOT NULL,                      -- Supabase Storage
  embedding     vector(512),                        -- CLIP embedding
  tags          TEXT[],                             -- mood, setting, expressao
  style_type    TEXT,                               -- 'cinematic' | 'influencer_natural'
  mauro_score   SMALLINT DEFAULT 0,                 -- 1=❤️, -1=✗, 0=neutro
  use_count     INTEGER DEFAULT 0,                  -- quantas vezes foi usada como ref
  created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_style_library_tier ON style_library(tier);
CREATE INDEX idx_style_library_embedding ON style_library USING ivfflat (embedding vector_cosine_ops);
```

#### `content_calendar`
Planejamento de produção.

```sql
CREATE TABLE content_calendar (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  target_date     DATE NOT NULL,
  creator_id      TEXT NOT NULL DEFAULT 'zenya',
  platform        TEXT NOT NULL DEFAULT 'instagram_reels',
  theme           TEXT,
  style           TEXT,
  content_piece_id UUID REFERENCES content_pieces(id),
  status          TEXT DEFAULT 'planned',           -- 'planned' | 'in_production' | 'done'
  created_at      TIMESTAMPTZ DEFAULT now()
);
```

---

## Módulos do Runtime

### Estrutura de arquivos

```
sparkle-runtime/runtime/
└── content/
    ├── __init__.py
    ├── router.py               — FastAPI router /content/*
    ├── models.py               — Pydantic schemas
    ├── pipeline.py             — Orquestrador principal (state machine)
    ├── style_library.py        — CRUD + CLIP similarity da Style Library
    ├── image_engineer.py       — Image Prompt Engineer
    ├── image_generator.py      — Integração Google Gemini Image API
    ├── video_engineer.py       — Video Prompt Engineer
    ├── video_generator.py      — Integração Google Veo 3.1 (VideoGeneratorProtocol)
    ├── voice_generator.py      — Integração ElevenLabs
    ├── copy_specialist.py      — Caption + voice script
    ├── assembler.py            — Integração Creatomate (→ Remotion futuro)
    ├── approval.py             — Lógica de fila de aprovação
    ├── publisher.py            — Instagram Graph API
    └── ip_auditor.py           — Validação de lore (sparkle-lore Brain)
```

### Portal (Next.js) — Views novas

```
portal/src/app/(hq)/
└── content/
    ├── page.tsx                — Dashboard de produção (calendário + status)
    ├── queue/
    │   └── page.tsx            — Content Queue (aprovação tela cheia)
    └── library/
        └── page.tsx            — Style Library + curation interface
```

---

## Pipeline de Produção (State Machine)

```
BRIEF CRIADO
     │
     ▼
[image_engineer.py]
  Consulta sparkle-lore (restrições)
  Seleciona ref Tier A da style_library
  Gera prompt técnico
     │
     ▼
[image_generator.py]
  POST NanoBanana/Flux API (image + ref)
  Salva no Supabase Storage
     │
     ▼
[video_engineer.py]
  Recebe imagem + estilo
  Gera prompt de movimento/câmera
     │
     ├─── [copy_specialist.py]  (paralelo)
     │      Gera caption + voice script
     │
     ▼
[video_generator.py]
  POST Kling API (image-to-video)
  Salva no Supabase Storage
     │
     ▼
[voice_generator.py]
  POST ElevenLabs (voice script → .mp3)
  Salva no Supabase Storage
     │
     ▼
[ip_auditor.py]
  Consulta sparkle-lore
  Valida: conteúdo não contradiz lore
  Valida: não muito similar a publicações recentes
     │
     ▼
[assembler.py]
  POST Creatomate API:
    video + audio + caption legenda + branding
  Output: .mp4 9:16 1080×1920
  Salva no Supabase Storage
     │
     ▼
PENDING_APPROVAL
  Friday → WhatsApp: "X conteúdos aguardando aprovação"
     │
     ▼
[Portal: Content Queue View]
  Mauro: ✅ Aprovar | ✏️ Editar | ❌ Rejeitar
     │
     ├── Aprovado → SCHEDULED
     │     [publisher.py] → Instagram Graph API
     │     Brain ingest (sparkle-lore)
     │
     └── Rejeitado → REJECTED (reason salvo)
```

---

## Curation Assistant (Fase 0)

### Fluxo técnico

```
1. Upload das ~800 imagens → Supabase Storage
2. Batch: extrai CLIP embeddings de todas (python-clip ou OpenCLIP)
3. Portal: grade de imagens em /content/library
4. Mauro reage: ❤️ → mauro_score=1, ✗ → mauro_score=-1
5. A cada ❤️:
   - Calcula cosine similarity entre a curtida e todas as restantes
   - Reordena a fila (score ponderado: CLIP similarity × mauro_score médio)
6. Ao final da sessão:
   - tier='A': mauro_score=1 (curtidas diretas)
   - tier='B': cosine_similarity ≥ 0.85 com média das Tier A
   - tier='C': demais
7. Mauro valida Tier A final → confirma Style Library
```

### Interface (Portal /content/library)

```
┌─────────────────────────────────────────────────────────┐
│  Style Library — Curadoria Zenya          [Confirmar ✓] │
│  ❤️ 47 curtidas   ✗ 312 descartados   → 441 neutros    │
├─────────────────────────────────────────────────────────┤
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐            │
│  │img │ │img │ │img │ │img │ │img │ │img │   ← grid    │
│  │ ❤️ │ │ ✗ │ │ →  │ │ ❤️ │ │ →  │ │ ✗  │            │
│  └────┘ └────┘ └────┘ └────┘ └────┘ └────┘            │
│                                                         │
│  [Tier A: 47] [Tier B: 89 sugeridas] [Tier C: 664]    │
└─────────────────────────────────────────────────────────┘
```

---

## API Endpoints

### Content Pipeline

| Método | Path | Descrição |
|--------|------|-----------|
| POST | `/content/briefs` | Criar brief → inicia pipeline |
| GET | `/content/briefs` | Listar briefs (com status) |
| GET | `/content/pieces/{id}` | Status de uma peça |
| GET | `/content/queue` | Fila pending_approval |
| POST | `/content/pieces/{id}/approve` | Aprovar peça |
| POST | `/content/pieces/{id}/reject` | Rejeitar com motivo |
| PATCH | `/content/pieces/{id}/caption` | Editar caption |
| POST | `/content/pieces/{id}/retry` | Retry de etapa que falhou |

### Style Library

| Método | Path | Descrição |
|--------|------|-----------|
| POST | `/content/library/upload` | Upload batch de imagens |
| POST | `/content/library/{id}/react` | Reagir (❤️/✗/→) |
| GET | `/content/library` | Listar com tier e score |
| POST | `/content/library/confirm` | Confirmar Style Library |
| GET | `/content/library/similar/{id}` | Imagens similares por CLIP |

### Calendar

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/content/calendar` | Calendário de produção |
| POST | `/content/calendar` | Agendar produção |

---

## Integrações Externas

### Google Veo 3.1 (vídeo — image-to-video)
```python
# SDK: google-genai
operation = await client.aio.models.generate_videos(
    model="veo-2.0-generate-001",  # estável; veo-3.0 quando sair de preview
    prompt=prompt,
    image=types.Image(image_url=image_url),
    config=types.GenerateVideosConfig(
        aspect_ratio="9:16",
        duration_seconds=5,   # 10 para cinematic
        number_of_videos=1,
    )
)
```
- Autenticação: `GEMINI_API_KEY` (mesmo da geração de imagem)
- Custo: ~$0.05/seg no Lite tier
- Abstração: `VeoVideoGenerator` implementa `VideoGeneratorProtocol`
- Áudio gerado pelo Veo é substituído pelo ElevenLabs no assembly (voice changer)

### Google Gemini Image API (imagem)
- Geração multimodal: texto + imagem de referência Tier A como contexto visual
- Modelo: `gemini-2.0-flash-exp` (ou `imagen-3` quando disponível)
- Sem `image_strength` — consistência via prompt engineering + referência Tier A
- Credencial: mesma `GEMINI_API_KEY` do Veo

### ElevenLabs (voz)
- Já integrado no Runtime (`runtime/integrations/elevenlabs.py` ou similar)
- Voice ID da Zenya já configurado

### Creatomate (assembly)
- Template parametrizável: `{{video_url}}`, `{{audio_url}}`, `{{caption}}`, `{{logo_url}}`
- Output: `.mp4` 9:16 1080×1920
- Abstração: `AssemblerProtocol` → swap para Remotion sem mudar pipeline

### Instagram Graph API (publicação)
- `POST /{ig-user-id}/media` → upload reel
- `POST /{ig-user-id}/media_publish` → publicar
- Requer: `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`

---

## Abstrações de Provider (padrão para migração)

```python
# Cada integração implementa o protocolo — swap sem mudar pipeline

class VideoGeneratorProtocol(Protocol):
    async def generate(self, image_url: str, prompt: str, style: str) -> str: ...

class AssemblerProtocol(Protocol):
    async def assemble(self, video: str, audio: str, caption: str) -> str: ...

# Fase 1 (MVP)
video_generator = VeoVideoGenerator()      # Google Veo 3.1
assembler = CreatomateAssembler()

# Fase 2 (troca sem tocar no pipeline)
video_generator = ComfyUIVideoGenerator()  # se necessário
assembler = RemotionAssembler()
```

---

## Crons

| Nome | Schedule | Ação |
|------|----------|------|
| `content_pipeline_tick` | `*/5 * * * *` | Avança peças presas em estados de geração (polling de jobs async) |
| `content_publisher_tick` | `0 * * * *` | Publica peças scheduled cujo horário chegou |
| `content_brain_sync` | `0 3 * * *` | Ingere peças publicadas no sparkle-lore (Brain) |

---

## Squad do Órgão

| Tier | Agente | Função |
|------|--------|--------|
| 0 | **Content Chief** | Orquestra o pipeline. Gerencia calendário e filas. |
| 1 | **Creative Director** | Decide estilo, conceito, mood por brief |
| 1 | **Copy Specialist** | Caption + voice script alinhados ao visual |
| 2 | **Image Prompt Engineer** | Prompt técnico — lighting, composition, style tokens, Tier A ref |
| 2 | **Video Prompt Engineer** | Image-to-video prompt — movimento, câmera, física |
| 2 | **Distribution Agent** | Agendamento + publicação Instagram |
| 3 | **IP Auditor** | Valida lore Zenya antes de publicar |

---

## Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Inconsistência visual sem LoRA | Alta | Alto | Style Library Tier A obrigatória como referência |
| Veo API instabilidade / rate limit | Média | Médio | Retry automático (3x) + status `video_failed` sem bloquear pipeline |
| Gemini Image sem consistência visual (sem img2img) | Média | Alto | Prompt engineering robusto com descrição detalhada da Zenya + Tier A como âncora; validar nas primeiras 10 gerações |
| Instagram Graph API rate limit | Baixa | Médio | Queue de publicação com delay entre posts |
| Assembly Creatomate timeout | Baixa | Baixo | Retry + fallback para assembly manual |
| Conteúdo que viola lore | Baixa | Alto | IP Auditor antes de pending_approval + aprovação Mauro |

---

## Critérios de Conclusão da Fase 1

Fase 1 completa quando:

1. Style Library Tier A confirmada por Mauro (≥ 30 imagens)
2. Pipeline end-to-end funcional: brief → .mp4 montado em < 15 min
3. Content Queue View no Portal: preview vídeo + aprovação funcionando
4. Friday notifica quando há itens pending_approval
5. Publicação automática no Instagram Reels funcional
6. IP Auditor validando contra sparkle-lore antes de aprovar
7. 5 peças de teste aprovadas e publicadas por Mauro

---

## Próximos Passos (handoff @sm)

Stories a criar (ordem de dependência):

```
CONTENT-0.1  Curation Assistant + Style Library
    ↓
CONTENT-1.1  Migration + Modelo de Dados (content_pieces, style_library, calendar)
CONTENT-1.2  Image Prompt Engineer + Geração (Gemini Image)       ┐ paralelo
CONTENT-1.3  Video Prompt Engineer + Geração (Veo 3.1)            │ após 1.1
CONTENT-1.4  Voice Generation (ElevenLabs) + Copy Specialist       ┘
    ↓
CONTENT-1.5  Assembly (Creatomate)
    ↓
CONTENT-1.6  Pipeline Orchestrator (state machine completo)
    ↓
CONTENT-1.7  Portal — Content Queue View (aprovação)
CONTENT-1.8  Portal — Style Library View (curadoria)              ┐ paralelo
CONTENT-1.9  Portal — Calendar View (briefing)                    ┘
    ↓
CONTENT-1.10 IP Auditor (Brain sparkle-lore validation)
    ↓
CONTENT-1.11 Publisher (Instagram Graph API)
    ↓
CONTENT-1.12 Crons + Friday notification
```
