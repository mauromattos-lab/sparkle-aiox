---
epic: EPIC-CONTENT-WAVE2 — Domínio Conteúdo Wave 2 (Estabilização + Volume)
story: CONTENT-2.4
title: "Bucket content-assets Público no Supabase Storage"
status: Done
priority: P0
executor: "@dev"
sprint: Content Wave 2
prd: docs/prd/domain-content-wave2-prd.md
architecture: docs/architecture/domain-content-wave2-architecture.md
squad: squads/content/
depends_on: []
unblocks: [CONTENT-2.1, CONTENT-2.5]
estimated_effort: "1h de agente (@dev)"
---

# Story 2.4 — Bucket content-assets Público no Supabase Storage

**Sprint:** Content Wave 2
**Status:** `Done`
**PRD:** `docs/prd/domain-content-wave2-prd.md` — FR-W2-04
**Architecture:** `docs/architecture/domain-content-wave2-architecture.md` — FR-W2-04

> **Paralelismo:** Esta story não depende de nenhuma outra. Deve ser executada primeiro (é pré-requisito de CONTENT-2.1) — pode rodar imediatamente ao iniciar o Bloco A.

---

## User Story

> Como publisher de conteúdo,
> quero que os arquivos de vídeo e imagem no bucket `content-assets` sejam publicamente acessíveis via URL sem autenticação,
> para que a Instagram Graph API consiga baixar os arquivos ao criar o container de mídia.

---

## Contexto Técnico

**Estado atual:**
- O bucket `content-assets` pode estar configurado como privado (não verificado na Wave 1).
- A Instagram Graph API exige que a URL do arquivo de vídeo/imagem seja publicamente acessível (sem token de autenticação) para criar o container de mídia.
- `image_generator.py` e `video_generator.py` podem estar usando `createSignedUrl()` — URLs com expiração que quebram o Brain ingest e o Portal após expirar.

**Estado alvo:**
- Bucket `content-assets` configurado como público no Supabase.
- `image_generator.py` e `video_generator.py` usam `getPublicUrl()` — URLs permanentes sem expiração.
- `publisher.py` usa `public_url` (não `signed_url`) ao submeter para a Graph API.
- Documentado em `BOUNDARY.md`: bucket é público por design (Instagram requirement).

---

## Acceptance Criteria

- [x] **AC1** — Verificar status do bucket via MCP Supabase: `SELECT name, public FROM storage.buckets WHERE name = 'content-assets'`. Se `public = false`, executar `UPDATE storage.buckets SET public = true WHERE name = 'content-assets'`.

- [x] **AC2** — URL pública de um arquivo no bucket é acessível sem autenticação: `curl -I "https://gqhdspayjtiijcqklbys.supabase.co/storage/v1/object/public/content-assets/{algum_arquivo}"` retorna HTTP 200 (não 400 ou 401).

- [x] **AC3** — Auditoria de `image_generator.py`: confirmar que usa `getPublicUrl()` (URL permanente) e não `createSignedUrl()` (URL com expiração). Se usar `createSignedUrl()`, substituir por `getPublicUrl()`.

- [x] **AC4** — Auditoria de `video_generator.py`: mesma verificação e correção do AC3.

- [x] **AC5** — `runtime/BOUNDARY.md` atualizado com a seguinte nota: "Bucket `content-assets`: público por design. Requisito da Instagram Graph API — a URL de vídeo submetida ao `_create_media_container()` precisa ser acessível sem autenticação. Nunca usar signed URLs para assets de conteúdo."

---

## Dev Notes

### Verificação e configuração do bucket via MCP Supabase

```sql
-- Passo 1: verificar status atual
SELECT name, public, created_at
FROM storage.buckets
WHERE name = 'content-assets';

-- Passo 2: se public = false, tornar público
UPDATE storage.buckets
SET public = true
WHERE name = 'content-assets';
```

Esta operação **não é uma migration versionada** — é configuração de infraestrutura executada diretamente via MCP Supabase.

### Formato de URL pública correta

```
https://gqhdspayjtiijcqklbys.supabase.co/storage/v1/object/public/content-assets/{path}
```

Nunca usar o formato de signed URL:
```
https://gqhdspayjtiijcqklbys.supabase.co/storage/v1/object/sign/content-assets/{path}?token=...
```

### Padrão a verificar em image_generator.py e video_generator.py

Buscar por `createSignedUrl` nos arquivos — se presente, substituir pela chamada pública equivalente do cliente Supabase Python.

### Impacto de não fazer esta story antes de CONTENT-2.1

O Publisher (CONTENT-2.1) submete a URL do vídeo para `_create_media_container()` da Graph API. Se a URL for uma signed URL expirada ou uma URL privada, a API retorna erro 400. Esta story deve ser concluída e verificada (AC2 especificamente) antes de tentar qualquer publicação no Instagram.

---

## Integration Verifications

- [x] `SELECT public FROM storage.buckets WHERE name = 'content-assets'` retorna `true`
- [x] `curl -I "https://gqhdspayjtiijcqklbys.supabase.co/storage/v1/object/public/content-assets/style-library/841c06bf-1035-4fb5-a6a6-0e2ef34e3365.png"` retorna 200
- [x] `image_generator.py` não contém `createSignedUrl` — usa `get_public_url()` (linha 137)
- [x] `video_generator.py` não contém `createSignedUrl` — usa `get_public_url()` (linha 145)
- [x] `runtime/BOUNDARY.md` contém nota sobre bucket público por design

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| Supabase Storage (via MCP) | Configurar | UPDATE storage.buckets SET public = true WHERE name = 'content-assets' |
| `runtime/content/image_generator.py` | Verificar / Modificar | Auditar uso de signed vs public URL; corrigir se necessário |
| `runtime/content/video_generator.py` | Verificar / Modificar | Auditar uso de signed vs public URL; corrigir se necessário |
| `runtime/BOUNDARY.md` | Modificar | Adicionar nota sobre bucket content-assets público por design |

---

## Dev Agent Record

**Executor:** @dev
**Agent Model:** claude-sonnet-4-6
**Completed:** 2026-04-07
**Completion Notes:** Bucket `content-assets` verificado via MCP Supabase — já estava configurado como público (`public = true`), nenhuma alteração necessária. URL pública testada com curl: HTTP 200 confirmado usando arquivo real do bucket (`style-library/841c06bf-1035-4fb5-a6a6-0e2ef34e3365.png`). Auditoria de `image_generator.py` e `video_generator.py` confirmou uso de `supabase.storage.from_(CONTENT_BUCKET).get_public_url(path)` em ambos — nenhuma ocorrência de `createSignedUrl` ou `signed_url`. `runtime/BOUNDARY.md` criado no repositório local (existia apenas na worktree) com seção dedicada ao bucket content-assets.
**Change Log:**
- `sparkle-runtime/runtime/BOUNDARY.md` — Criado (restaurado do worktree + seção Storage adicionada)
- `docs/stories/sprint-content/content-2-4-bucket-storage-publico.md` — ACs marcados [x], Integration Verifications marcadas, status → Ready for Review, Dev Agent Record preenchido

---

## QA Results

**Revisor:** Quinn (@qa)
**Data:** 2026-04-07
**Resultado:** PASS

| AC | Status | Nota |
|----|--------|------|
| AC1 | PASS | Verificado via MCP Supabase (`execute_sql`): `SELECT name, public FROM storage.buckets WHERE name = 'content-assets'` retornou `{"name":"content-assets","public":true}`. Nenhuma alteração necessária. |
| AC2 | PASS | Bucket confirmado público (AC1). Dev reportou `curl -I` com HTTP 200 no arquivo `style-library/841c06bf-1035-4fb5-a6a6-0e2ef34e3365.png`. AC2 é consequência direta do bucket estar público — evidência suficiente. |
| AC3 | PASS | `sparkle-runtime/runtime/content/image_generator.py` linha 137: `supabase.storage.from_(CONTENT_BUCKET).get_public_url(path)`. Grep em todo o módulo content não encontrou nenhuma ocorrência de `signed`, `createSignedUrl` ou `sign/`. |
| AC4 | PASS | `sparkle-runtime/runtime/content/video_generator.py` linha 145: `supabase.storage.from_(CONTENT_BUCKET).get_public_url(path)`. Mesma auditoria: zero ocorrências de signed URL em qualquer arquivo `.py` do módulo. |
| AC5 | PASS | `sparkle-runtime/runtime/BOUNDARY.md` contém seção "Storage: Bucket content-assets" com nota completa: bucket público por design, requisito Instagram Graph API, formatos correto/proibido, e referência explícita a `image_generator.py` e `video_generator.py`. Texto alinhado ao AC. |

**Observação:** O Dev Agent Record cita `image_engineer.py`/`video_engineer.py` no texto de conclusão, mas os arquivos que efetivamente fazem operações de Storage (upload + `get_public_url`) são `image_generator.py`/`video_generator.py` — que é o que a story especifica na File List e o que foi verificado. Os `*_engineer.py` são construtores de prompt sem acesso ao Storage. Não há impacto no resultado, mas o Dev deve padronizar a nomenclatura nos registros futuros.
