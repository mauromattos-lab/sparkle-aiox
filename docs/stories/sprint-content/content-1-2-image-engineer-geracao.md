---
epic: EPIC-CONTENT-ZENYA — Domínio Conteúdo (Zenya-First)
story: CONTENT-1.2
title: "Image Prompt Engineer + Geração NanoBanana"
status: TODO
priority: P0
executor: "@dev"
sprint: Content Wave 1
prd: docs/prd/domain-content-zenya-prd.md
architecture: docs/architecture/domain-content-zenya-architecture.md
squad: squads/content/
depends_on: [CONTENT-1.1]
unblocks: [CONTENT-1.3, CONTENT-1.5]
estimated_effort: 4-5h de agente (@dev)
blocker: "NANOBANA_API_KEY — Mauro obtém em nanobanana.ai"
---

# Story 1.2 — Image Prompt Engineer + Geração NanoBanana

**Sprint:** Content Wave 1
**Status:** `TODO`
**Sequência:** 3 de 13 (paralelo com 1.3 e 1.4)
**PRD:** `docs/prd/domain-content-zenya-prd.md` — FR2
**Architecture:** `docs/architecture/domain-content-zenya-architecture.md`

---

## User Story

> Como pipeline de conteúdo,
> quero gerar imagens da Zenya usando um prompt técnico especializado com referência obrigatória de uma imagem Tier A da Style Library,
> para que cada imagem produzida mantenha consistência visual com o cânone da personagem.

---

## Contexto Técnico

**Estado atual:** Nenhuma integração com NanoBanana/Flux existe no Runtime.

**Estado alvo:** `image_engineer.py` gera prompt técnico completo; `image_generator.py` envia para NanoBanana com imagem de referência Tier A; imagem gerada salva no Supabase Storage; `content_pieces.status` avança de `briefed` → `image_generating` → `image_done`.

**⚠️ BLOCKER:** `NANOBANA_API_KEY` precisa estar em variável de ambiente antes do @dev testar esta story.

---

## Acceptance Criteria

- [ ] **AC1** — `image_engineer.py` recebe brief (theme, mood, style) e retorna prompt técnico completo incluindo: estilo visual, lighting, composition, tokens específicos do modelo Flux
- [ ] **AC2** — Toda chamada de geração seleciona ao menos 1 imagem Tier A da `style_library` como referência visual (aleatória entre as disponíveis, ou a mais usada)
- [ ] **AC3** — Suporte a dois estilos base: `cinematic` (iluminação dramática, profundidade de campo, cinematográfico) e `influencer_natural` (luz natural, casual, próximo à câmera)
- [ ] **AC4** — `image_generator.py` chama NanoBanana/Flux API com `image_strength` entre 0.35–0.55 e a referência Tier A
- [ ] **AC5** — Imagem gerada salva no Supabase Storage em `content-assets/images/{content_piece_id}.png`
- [ ] **AC6** — `content_pieces.image_url` atualizado com o path de Storage; `status` avança para `image_done`
- [ ] **AC7** — Falha na API NanoBanana atualiza `status = 'image_failed'` e registra erro em `error_log` — não bloqueia outras peças no pipeline
- [ ] **AC8** — Geração falha com mensagem clara se Style Library não tiver imagens Tier A disponíveis (não tenta gerar sem referência)

---

## Dev Notes

### Estrutura de prompt — estilo cinematic
```python
def build_cinematic_prompt(theme: str, mood: str) -> str:
    return (
        f"{theme}, {mood} mood, "
        "ultra-realistic portrait, cinematic lighting, "
        "dramatic shadows, shallow depth of field, "
        "85mm lens, golden hour, "
        "Brazilian woman with dark features, "
        "high-end fashion editorial, 8k resolution"
    )
```

### Estrutura de prompt — estilo influencer_natural
```python
def build_influencer_prompt(theme: str, mood: str) -> str:
    return (
        f"{theme}, {mood} mood, "
        "natural lighting, authentic lifestyle, "
        "close to camera, warm tones, "
        "Brazilian woman with dark features, "
        "social media portrait, candid, vibrant"
    )
```

### Seleção de referência Tier A
```python
async def get_tier_a_reference(style: str) -> StyleLibraryItem:
    # Prioriza imagens com style_type correspondente ao brief
    # Fallback: qualquer Tier A se style_type não bater
    result = supabase.table("style_library") \
        .select("*") \
        .eq("tier", "A") \
        .eq("style_type", style) \
        .order("use_count", desc=False) \  # prioriza menos usadas
        .limit(5) \
        .execute()
    if not result.data:
        # fallback sem filtro de style_type
        result = supabase.table("style_library") \
            .select("*").eq("tier", "A").limit(5).execute()
    if not result.data:
        raise ValueError("Style Library sem imagens Tier A — execute curadoria primeiro")
    return random.choice(result.data)
```

### Incrementar use_count após uso
```python
supabase.table("style_library") \
    .update({"use_count": ref["use_count"] + 1}) \
    .eq("id", ref["id"]).execute()
```

### Salvar referências usadas em content_pieces
```python
supabase.table("content_pieces") \
    .update({"style_ref_ids": [ref["id"]], "status": "image_generating"}) \
    .eq("id", piece_id).execute()
```

---

## Integration Verifications

- [ ] `NANOBANA_API_KEY` presente em variável de ambiente do Runtime
- [ ] Chamada de geração com estilo `cinematic` retorna imagem válida
- [ ] Chamada de geração com estilo `influencer_natural` retorna imagem válida
- [ ] Imagem salva no Supabase Storage e URL acessível publicamente
- [ ] `content_pieces.status` = `image_done` após geração bem-sucedida
- [ ] `content_pieces.status` = `image_failed` após falha de API (simular com key inválida)
- [ ] Geração sem Tier A disponível retorna erro 400 com mensagem clara (não 500)

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `runtime/content/image_engineer.py` | Criar | Prompt engineer: build_cinematic_prompt, build_influencer_prompt, get_tier_a_reference |
| `runtime/content/image_generator.py` | Criar | NanoBanana/Flux API integration: generate_image() |
| `tests/test_image_engineer.py` | Criar | Testes: prompt building, tier A selection, fallback, error handling |
