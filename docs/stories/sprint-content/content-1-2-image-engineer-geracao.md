---
epic: EPIC-CONTENT-ZENYA — Domínio Conteúdo (Zenya-First)
story: CONTENT-1.2
title: "Image Prompt Engineer + Geração Gemini Image"
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
blocker: "GEMINI_API_KEY — Mauro obtém em aistudio.google.com (gratuito)"
---

# Story 1.2 — Image Prompt Engineer + Geração Gemini Image

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

**Estado atual:** Nenhuma integração com Gemini Image existe no Runtime.

**Estado alvo:** `image_engineer.py` gera prompt técnico completo; `image_generator.py` envia para Google Gemini Image API com imagem de referência Tier A como contexto multimodal; imagem gerada salva no Supabase Storage; `content_pieces.status` avança de `briefed` → `image_generating` → `image_done`.

**⚠️ BLOCKER:** `GEMINI_API_KEY` precisa estar em variável de ambiente antes do @dev testar esta story. Obter em aistudio.google.com (gratuito).

---

## Acceptance Criteria

- [ ] **AC1** — `image_engineer.py` recebe brief (theme, mood, style) e retorna prompt técnico completo incluindo: estilo visual, lighting, composition, tokens específicos do modelo Flux
- [ ] **AC2** — Toda chamada de geração seleciona ao menos 1 imagem Tier A da `style_library` como referência visual (aleatória entre as disponíveis, ou a mais usada)
- [ ] **AC3** — Suporte a dois estilos base: `cinematic` (iluminação dramática, profundidade de campo, cinematográfico) e `influencer_natural` (luz natural, casual, próximo à câmera)
- [ ] **AC4** — `image_generator.py` chama Google Gemini Image API com prompt multimodal: texto descritivo da Zenya + imagem Tier A como referência de estilo visual (sem `image_strength` — consistência via prompt engineering)
- [ ] **AC5** — Imagem gerada salva no Supabase Storage em `content-assets/images/{content_piece_id}.png`
- [ ] **AC6** — `content_pieces.image_url` atualizado com o path de Storage; `status` avança para `image_done`
- [ ] **AC7** — Falha na API NanoBanana atualiza `status = 'image_failed'` e registra erro em `error_log` — não bloqueia outras peças no pipeline
- [ ] **AC8** — Geração falha com mensagem clara se Style Library não tiver imagens Tier A disponíveis (não tenta gerar sem referência)

---

## Dev Notes

### Estrutura de prompt — estilo cinematic
```python
ZENYA_BASE_DESCRIPTION = (
    "Zenya, uma personagem de IA brasileira. "
    "Mulher brasileira, traços marcantes, expressão confiante e acolhedora, "
    "cabelos escuros, aparência moderna e sofisticada. "
    "Mantenha exatamente o estilo visual da imagem de referência fornecida."
)

def build_cinematic_prompt(theme: str, mood: str) -> str:
    return (
        f"{ZENYA_BASE_DESCRIPTION} "
        f"Tema: {theme}. Mood: {mood}. "
        "Iluminação cinematográfica dramática, sombras profundas, "
        "profundidade de campo rasa, lente 85mm, hora dourada, "
        "editorial de moda high-end, resolução 8k."
    )
```

### Estrutura de prompt — estilo influencer_natural
```python
def build_influencer_prompt(theme: str, mood: str) -> str:
    return (
        f"{ZENYA_BASE_DESCRIPTION} "
        f"Tema: {theme}. Mood: {mood}. "
        "Luz natural, lifestyle autêntico, próxima à câmera, "
        "tons quentes, retrato para redes sociais, espontâneo, vibrante."
    )
```

### Chamada Gemini Image (multimodal)
```python
import google.generativeai as genai
from google.generativeai import types

async def generate_image(prompt: str, reference_image_url: str) -> bytes:
    client = genai.Client(api_key=settings.gemini_api_key)
    # Referência Tier A como âncora visual
    image_part = types.Part.from_uri(reference_image_url, mime_type="image/png")
    response = await client.aio.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=[image_part, prompt],
    )
    return response.candidates[0].content.parts[0].inline_data.data
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

- [ ] `GEMINI_API_KEY` presente em variável de ambiente do Runtime
- [ ] Chamada de geração com estilo `cinematic` retorna imagem válida da Zenya
- [ ] Chamada de geração com estilo `influencer_natural` retorna imagem válida da Zenya
- [ ] Imagem salva no Supabase Storage e URL acessível publicamente
- [ ] `content_pieces.status` = `image_done` após geração bem-sucedida
- [ ] `content_pieces.status` = `image_failed` após falha de API (simular com key inválida)
- [ ] Geração sem Tier A disponível retorna erro 400 com mensagem clara (não 500)

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `runtime/content/image_engineer.py` | Criar | Prompt engineer: build_cinematic_prompt, build_influencer_prompt, get_tier_a_reference |
| `runtime/content/image_generator.py` | Criar | Google Gemini Image API (multimodal): generate_image() |
| `tests/test_image_engineer.py` | Criar | Testes: prompt building, tier A selection, fallback, error handling |
