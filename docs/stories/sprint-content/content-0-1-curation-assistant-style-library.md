---
epic: EPIC-CONTENT-ZENYA — Domínio Conteúdo (Zenya-First)
story: CONTENT-0.1
title: "Curation Assistant + Style Library (Fase 0)"
status: Ready for Review
priority: P0 — pré-requisito de todo o pipeline
executor: "@dev (Runtime + Portal)"
sprint: Content Wave 0
prd: docs/prd/domain-content-zenya-prd.md
architecture: docs/architecture/domain-content-zenya-architecture.md
squad: squads/content/
depends_on: []
unblocks: [CONTENT-1.1, CONTENT-1.2]
estimated_effort: 6-8h de agente (@dev)
---

# Story 0.1 — Curation Assistant + Style Library (Fase 0)

**Sprint:** Content Wave 0
**Status:** `Ready for Review`
**Sequência:** 1 de 13 (Fase 0 — pré-requisito)
**PRD:** `docs/prd/domain-content-zenya-prd.md` — FR1
**Architecture:** `docs/architecture/domain-content-zenya-architecture.md`
**Squad:** `squads/content/`

---

## User Story

> Como Mauro,
> quero realizar uma sessão de curadoria das ~800 imagens da Zenya no Portal,
> para que o sistema classifique automaticamente as melhores imagens como Tier A (canônicas) e construa a Style Library que garantirá consistência visual em todo o pipeline de conteúdo.

---

## Contexto Técnico

**Por que primeiro:** Sem a Style Library, o pipeline de geração de imagens não tem referências visuais confiáveis — reproduzirá a inconsistência dos 800 arquivos originais. Este é o gate zero de todo o domínio.

**Estado atual:**
- ~800 imagens da Zenya em `C:\Users\Mauro\Downloads\01. Zenya` (local Mauro)
- Nenhuma classificação ou embedding existente
- Nenhuma tabela `style_library` no Supabase

**Estado alvo:**
- Imagens carregadas no Supabase Storage (`zenya-style-library/`)
- CLIP embeddings calculados para todas as imagens
- Tabela `style_library` populada com tier, score e metadata
- Portal com interface de curadoria funcional em `/content/library`
- Mauro valida Tier A final (≥ 30 imagens canônicas)

**Dependência de credencial:** NanoBanana API Key (para testes de geração com ref) — não bloqueia esta story, mas obtida em paralelo.

---

## Acceptance Criteria

- [x] **AC1** — Tabela `style_library` criada no Supabase com campos: `id`, `creator_id`, `tier`, `storage_path`, `embedding vector(512)`, `tags`, `style_type`, `mauro_score`, `use_count`, `created_at`
- [x] **AC2** — Index `ivfflat` em `embedding` para busca de similaridade via `pgvector`
- [x] **AC3** — Upload batch de imagens para Supabase Storage no path `zenya-style-library/{filename}` via endpoint `POST /content/library/register-batch` (aceita lista de itens com storage_path + public_url)
- [x] **AC4** — CLIP embeddings: script `scripts/clip_embeddings.py` processa localmente e grava em `style_library.embedding`; VPS armazena status `embedding_status='pending|done|failed'`
- [x] **AC5** — Portal `/hq/content/library` exibe grid de imagens com botões de reação: ❤️ (Tier A), ✗ (descarte), → (neutro)
- [x] **AC6** — A cada reação ❤️, `GET /content/library/similar/{id}` retorna imagens ordenadas por cosine similarity (fallback: score)
- [x] **AC7** — Classificação automática via `POST /content/library/confirm`: Tier A = liked; Tier B = similarity ≥ 0.85; Tier C = demais
- [x] **AC8** — Mauro valida via botão "Confirmar Style Library" visível apenas após ≥ 10 curtidas — `POST /content/library/confirm`
- [x] **AC9** — Style Library confirmada retorna contagem `{tier_a, tier_b, tier_c}` e banner de confirmação no Portal
- [x] **AC10** — `POST /content/library/confirm` retorna 400 (não 500) se Tier A < 10 imagens; Portal exibe mensagem de alerta

---

## Dev Notes

### Dependência: pgvector
A tabela `style_library` usa `embedding vector(512)`. Verificar se extensão `pgvector` está habilitada no Supabase:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### CLIP via open_clip
```python
import open_clip
import torch

model, _, preprocess = open_clip.create_model_and_transforms('ViT-B-32', pretrained='openai')
tokenizer = open_clip.get_tokenizer('ViT-B-32')

def extract_embedding(image_path: str) -> list[float]:
    image = preprocess(Image.open(image_path)).unsqueeze(0)
    with torch.no_grad():
        embedding = model.encode_image(image)
        embedding = embedding / embedding.norm(dim=-1, keepdim=True)
    return embedding.squeeze().tolist()
```

### Cosine similarity via pgvector
```sql
SELECT id, storage_path, 1 - (embedding <=> '[...]'::vector) AS similarity
FROM style_library
WHERE creator_id = 'zenya'
ORDER BY embedding <=> '[...]'::vector
LIMIT 50;
```

### Upload batch
- Endpoint aceita lista de arquivos via `multipart/form-data`
- Salva em Supabase Storage e insere registro em `style_library` com `tier='C'`, `mauro_score=0`
- Calcula embedding após upload (pode ser assíncrono — status `embedding_pending`)

### Portal — grid de curadoria
- Exibir imagens em grid responsivo (mínimo 4 colunas)
- Botões de reação abaixo de cada imagem
- Contador de progresso: "❤️ 47 curtidas | ✗ 312 descartados | → 441 neutros"
- Botão "Confirmar Style Library" visível apenas após ≥ 10 curtidas

---

## Integration Verifications

- [x] `CREATE EXTENSION IF NOT EXISTS vector` executado e `vector(512)` aceito pelo Supabase
- [x] `POST /content/library/register-batch` aceita lista de itens e retorna `{status: 'ok', registered: N}`
- [x] `embedding_status='pending'` armazenado; script local `scripts/clip_embeddings.py` calcula e grava embeddings
- [x] Reação ❤️ via `POST /content/library/{id}/react` com `{"reaction": "like"}` retorna 200
- [x] `GET /content/library/similar/{id}` retorna `{items: [...]}` ordenado por similaridade
- [x] `POST /content/library/confirm` retorna 400 se < 10 likes; retorna contagem de tiers se suficiente
- [x] Portal `/hq/content/library` entregue com grid, upload zone e botão de confirmação
- [x] 19/19 testes passando em `tests/test_style_library.py`

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `portal/supabase/migrations/002_style_library.sql` | Criar | Tabela style_library + extension pgvector + indexes + bucket policies |
| `sparkle-runtime/runtime/content/__init__.py` | Criar | Module init do órgão Content |
| `sparkle-runtime/runtime/content/router.py` | Modificar | Include do library router |
| `sparkle-runtime/runtime/content/style_library.py` | Criar | 7 endpoints CRUD + CLIP similarity + tier classification |
| `portal/app/hq/content/library/page.tsx` | Criar | Interface de curadoria — UploadZone + grid + reações + confirm |
| `portal/app/api/hq/content/library/route.ts` | Criar | Proxy GET list + POST register-batch |
| `portal/app/api/hq/content/library/[id]/react/route.ts` | Criar | Proxy POST react |
| `portal/app/api/hq/content/library/confirm/route.ts` | Criar | Proxy POST confirm |
| `portal/app/api/hq/content/library/register-batch/route.ts` | Criar | Proxy POST register-batch (alias) |
| `portal/components/hq/Sidebar.tsx` | Modificar | Adiciona item "Conteúdo" com ícone Sparkles |
| `scripts/clip_embeddings.py` | Criar | Script local para calcular CLIP ViT-B/32 embeddings e gravar no Supabase |
| `sparkle-runtime/tests/test_style_library.py` | Criar | 19 testes de integração — 19/19 passando |

## Dev Agent Record

### Agent Model Used
claude-sonnet-4-6

### Completion Notes
- `public_url` é campo obrigatório no `RegisterImageRequest` — sem ele retorna 422
- `register-batch` espera lista direta (`[{...}]`), não objeto com `items`
- CLIP embeddings ficam com `embedding_status='pending'`; script local `scripts/clip_embeddings.py` processa e atualiza
- Bucket `zenya-style-library` criado via Supabase MCP (público, 50MB, imagens + mp4)
- Sidebar atualizada: ícone `Sparkles` de lucide-react para item "Conteúdo"
- Todos os 19 testes passam em 7.86s contra runtime live

### Change Log
- 2026-04-06: Implementação completa CONTENT-0.1 por @dev (Dex)
