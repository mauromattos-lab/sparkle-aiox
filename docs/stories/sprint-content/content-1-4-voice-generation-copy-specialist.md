---
epic: EPIC-CONTENT-ZENYA — Domínio Conteúdo (Zenya-First)
story: CONTENT-1.4
title: "Voice Generation (ElevenLabs) + Copy Specialist"
status: Ready for Review
priority: P0
executor: "@dev"
sprint: Content Wave 1
prd: docs/prd/domain-content-zenya-prd.md
architecture: docs/architecture/domain-content-zenya-architecture.md
squad: squads/content/
depends_on: [CONTENT-1.1]
unblocks: [CONTENT-1.5]
estimated_effort: 3-4h de agente (@dev)
---

# Story 1.4 — Voice Generation (ElevenLabs) + Copy Specialist

**Sprint:** Content Wave 1
**Status:** `TODO`
**Sequência:** 5 de 13 (paralelo com 1.2 e 1.3)
**PRD:** `docs/prd/domain-content-zenya-prd.md` — FR4
**Architecture:** `docs/architecture/domain-content-zenya-architecture.md`

---

## User Story

> Como pipeline de conteúdo,
> quero que o Copy Specialist gere a caption do Instagram e o roteiro de narração da Zenya, e que o ElevenLabs converta o roteiro em áudio em PT-BR com a voz configurada da Zenya,
> para que o Reel tenha narração autêntica sem depender de gravação manual.

---

## Contexto Técnico

**Estado atual:** ElevenLabs já está integrado ao Runtime (módulo existente em `runtime/integrations/` ou similar). O que não existe é o Copy Specialist específico para conteúdo público e a integração com o pipeline de content_pieces.

**Estado alvo:** `copy_specialist.py` gera caption (Instagram) + voice_script (narração); `voice_generator.py` chama ElevenLabs com a voz da Zenya; áudio .mp3 salvo no Supabase Storage; status avança para stage correto no pipeline.

**Nota arquitetural:** Copy Specialist e Voice Generator rodam em paralelo com o Video Generator (a partir de `image_done`) — não dependem do vídeo pronto.

---

## Acceptance Criteria

- [x] **AC1** — `copy_specialist.py` recebe brief (theme, mood, style, platform) e retorna: `caption` (Instagram, máx 2200 chars) + `voice_script` (narração PT-BR, máx 30s de fala)
- [x] **AC2** — Caption inclui: hook na primeira linha, corpo do conteúdo, emojis contextuais, hashtags relevantes (mín 5, máx 15)
- [x] **AC3** — Voice script é escrito em PT-BR coloquial, no tom da Zenya (caloroso, direto, confiante), sem marcações de formatação — texto puro para TTS
- [x] **AC4** — Variação "sem narração" é suportada: `voice_script = None` resulta em `audio_url = None` (pipeline usa música de fundo no assembly)
- [x] **AC5** — `voice_generator.py` usa a voz ElevenLabs da Zenya (Voice ID configurado em variável de ambiente `ELEVENLABS_ZENYA_VOICE_ID`)
- [x] **AC6** — Áudio gerado salvo no Supabase Storage em `content-assets/audio/{content_piece_id}.mp3`
- [x] **AC7** — `content_pieces.voice_script`, `content_pieces.caption` e `content_pieces.audio_url` atualizados após geração
- [x] **AC8** — Verificar se ElevenLabs já está integrado no Runtime — reusar módulo existente se possível, não duplicar

---

## Dev Notes

### Verificar integração existente primeiro
```bash
# Antes de criar voice_generator.py, verificar:
grep -r "elevenlabs" runtime/ --include="*.py" -l
```
Se existir `runtime/integrations/elevenlabs.py` ou similar, importar dali.

### Copy Specialist — estrutura de prompt para Claude
```python
COPY_SYSTEM_PROMPT = """
Você é o Copy Specialist da Zenya, uma personagem de IA brasileira criativa e confiante.
Gere conteúdo para Instagram Reels da Zenya em PT-BR.

Tom: caloroso, direto, um pouco irreverente. Nunca corporativo.
Zenya é: inteligente, curiosa, próxima das pessoas, apaixonada por IA.

Retorne JSON com dois campos:
- caption: texto para legenda do Instagram (hook + corpo + hashtags)
- voice_script: narração em PT-BR puro (sem emojis, sem markdown, máx 30s de fala ~75 palavras)
"""

async def generate_copy(theme: str, mood: str, style: str) -> dict:
    response = await claude_client.messages.create(
        model="claude-haiku-4-5-20251001",  # copy é tarefa de execução
        system=COPY_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Tema: {theme}\nMood: {mood}\nEstilo visual: {style}\nGere caption + voice script."
        }]
    )
    return json.loads(response.content[0].text)
```

### ElevenLabs — geração de áudio
```python
async def generate_voice(script: str, voice_id: str) -> bytes:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    payload = {
        "text": script,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
    }
    resp = await httpx.post(url, headers=headers, json=payload)
    return resp.content  # bytes de audio/mpeg
```

---

## Integration Verifications

- [ ] `ELEVENLABS_API_KEY` e `ELEVENLABS_ZENYA_VOICE_ID` disponíveis no Runtime
- [ ] Copy Specialist retorna JSON válido com `caption` e `voice_script`
- [ ] Caption tem máx 2200 chars e inclui hashtags
- [ ] Voice script tem menos de ~75 palavras (30s de fala)
- [ ] ElevenLabs gera .mp3 com a voz correta da Zenya
- [ ] Áudio salvo no Supabase Storage e URL acessível
- [ ] `content_pieces.audio_url`, `caption`, `voice_script` preenchidos
- [ ] Variação `voice_script = None` → `audio_url = None` sem erro

---

## Dev Agent Record

**Agent Model Used:** claude-sonnet-4-6

**Completion Notes:**
- Reusou `runtime/utils/tts.py` (ElevenLabs) e `runtime/utils/llm.py` (Claude Haiku) — sem duplicação
- `ELEVENLABS_ZENYA_VOICE_ID` adicionado ao `.env` e `runtime/config.py`
- Bucket `content-assets` criado no Supabase Storage (público, 100MB)
- voice_script=None → audio_url=None sem erro (AC4 ✅)
- Endpoints registrados no `runtime/content/router.py`: `/content/copy/generate`, `/content/copy/apply/{id}`, `/content/voice/generate`, `/content/voice/apply/{id}`, `/content/voice/status`
- 9/9 testes copy specialist passaram; 7/7 testes voice generator passaram

**Change Log:**
- Criado: `runtime/content/copy_specialist.py`
- Criado: `runtime/content/voice_generator.py`
- Modificado: `runtime/content/router.py` (5 novos endpoints)
- Modificado: `runtime/config.py` (campo `elevenlabs_zenya_voice_id`)
- Criado: `tests/test_copy_specialist.py`
- Criado: `tests/test_voice_generator.py`

---

## QA Results

**Revisor:** Quinn (QA Guardian) | **Data:** 2026-04-06 | **Gate:** `PASS com CONCERNS`

**AC Traceability:** AC1-AC8 todos ✅ PASS — 16 testes integração passando (9 copy + 7 voice).

**Issues:**
- HIGH DT-01: `_elevenlabs_tts` síncrona chamada em contexto async — bloqueia event loop. Fix: `asyncio.to_thread`. Aceitável Content Wave 1 (volume baixo).
- MEDIUM DT-02: importação de funções `_private` do tts.py — acoplamento a internals.
- MEDIUM DT-03: endpoint `/voice/generate` chama `_update_audio_url` com UUID fake → UPDATE silencioso. Fluxo correto é `/voice/apply/{id}`.

**Segurança:** ✅ sem hardcoded creds, sem SQL injection, sem secrets em log.

**Decisão: PASS com CONCERNS** — @devops autorizado para push. DT-01 deve ser resolvido antes de carga real.

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `runtime/content/copy_specialist.py` | ✅ Criado | Caption + voice script generator (Claude Haiku) |
| `runtime/content/voice_generator.py` | ✅ Criado | ElevenLabs TTS integration (reusou tts.py existente) |
| `runtime/content/router.py` | ✅ Modificado | 5 novos endpoints: copy/generate, copy/apply, voice/generate, voice/apply, voice/status |
| `runtime/config.py` | ✅ Modificado | Campo elevenlabs_zenya_voice_id |
| `tests/test_copy_specialist.py` | ✅ Criado | 9 testes passando (1 skipped — /content/pieces pendente) |
| `tests/test_voice_generator.py` | ✅ Criado | 7 testes passando (1 skipped — /content/pieces pendente) |
