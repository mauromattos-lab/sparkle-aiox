# PRD — Domínio Conteúdo (Zenya-First)

**Versão:** 1.0  
**Data:** 2026-04-06  
**Autor:** @architect (Aria) — Domain Discovery com Mauro  
**Status:** Aprovado para Stories — revisado @pm 2026-04-06  
**Epic:** EPIC-CONTENT-ZENYA

---

## Visão

A Sparkle produz conteúdo autonomamente com a Zenya como criadora/face. O sistema gera, monta e entrega conteúdo pronto para aprovação — Mauro revisa no Portal e aprova em lote. Nenhum conteúdo é publicado sem aprovação humana na Fase 1.

**Resultado esperado:** Zenya publica 5+ peças/dia no Instagram Reels com consistência visual, voz em PT-BR e qualidade cinematic — sem Mauro executar nenhuma etapa de produção.

---

## Contexto e Decisões de Escopo

### Zenya-First
A Zenya é a única personagem com visual estabelecido (~800 arquivos de imagem/vídeo), lore definido e referências suficientes para treinar consistência. O domínio começa com ela — outros criadores (Mauro, clientes) são adaptações futuras do mesmo motor.

### Sem LoRA (por ora)
A consistência visual da Zenya será garantida via **Style Library** — curadoria das melhores imagens como referência para geração. LoRA é o passo seguinte quando o volume de conteúdo aprovado justificar o treinamento.

### Plataforma: Instagram Reels (exclusivo Fase 1)
TikTok e YouTube Shorts são replicados manualmente por Mauro enquanto não há especialistas de plataforma. O pipeline produz no formato 9:16 vertical, compatível com as três plataformas.

### Aprovação: Portal (não WhatsApp)
Conteúdo visual requer tela cheia, preview de vídeo com áudio, e edição de caption. O Portal é a ferramenta de decisão. Friday (WhatsApp) é apenas notificação: "X conteúdos aguardando aprovação."

### Stack de vídeo: Kling API → ComfyUI + RunPod
Kling API para MVP (zero infra, onboarding imediato). Migração para ComfyUI + RunPod quando volume superar ~200 vídeos/mês (break-even econômico). A voz é sempre ElevenLabs (independente do gerador visual).

---

## Fases de Entrega

### Fase 0 — Style Library (pré-requisito)
Curadoria assistida das 800 imagens existentes. Sem esta fase, o pipeline reproduz inconsistência.

### Fase 1 — MVP Pipeline (entrega de valor imediata)
Pipeline completo end-to-end: brief → imagem → vídeo → voz → assembly → aprovação → publicação.

### Fase 2 — Volume e Escala
ComfyUI + RunPod substituindo Kling. Content Calendar automatizado. Research Agent para ideação.

### Fase 3 — Inteligência
Sistema aprende o que Mauro aprova e reduz revisões manuais. Zenya adapta estilo por performance de conteúdo.

---

## Requisitos Funcionais

### FR1 — Curation Assistant (Style Library)

**Fase:** 0  
**Prioridade:** P0 (pré-requisito de todo o resto)

O sistema exibe as ~800 imagens da Zenya no Portal em sessão de curadoria. Mauro reage com ❤️ / ✗ / →. A cada reação positiva, o sistema extrai embedding visual (CLIP) e reordena a fila priorizando imagens visualmente similares.

**Critérios de aceite:**
- [ ] Portal exibe grid de imagens da Zenya para curadoria
- [ ] Mauro reage com ❤️ (Tier A), ✗ (descarte) ou → (neutro)
- [ ] Sistema calcula similaridade CLIP após cada ❤️ e reordena a fila
- [ ] Após sessão, sistema classifica automaticamente: Tier A (canônicas) / Tier B (variações) / Tier C (descarte)
- [ ] Mauro valida o Tier A final antes de confirmar a Style Library
- [ ] Style Library fica armazenada no Supabase Storage com metadata de tier e tags

---

### FR2 — Image Prompt Engineering + Geração

**Fase:** 1  
**Prioridade:** P0

O Image Prompt Engineer gera prompts técnicos de alta qualidade usando como referência obrigatória imagens do Tier A da Style Library. O prompt inclui: estilo visual (cinematográfico ou influencer/natural), lighting, composition, e tokens específicos do modelo.

**Critérios de aceite:**
- [ ] Image Prompt Engineer recebe brief (tema, mood, estilo) e retorna prompt completo
- [ ] Toda geração usa ao menos 1 imagem Tier A como referência de estilo
- [ ] Suporte a dois estilos base: `cinematic` e `influencer_natural`
- [ ] Geração via NanoBanana/Flux API com referência de imagem
- [ ] Output armazenado no Supabase Storage com metadata (prompt, estilo, referência usada)
- [ ] Geração falha graciosamente se Style Library não tiver imagens Tier A disponíveis

---

### FR3 — Video Prompt Engineering + Geração

**Fase:** 1  
**Prioridade:** P0

O Video Prompt Engineer recebe a imagem gerada e produz um prompt de movimento/câmera otimizado para o modelo de vídeo ativo (Kling API na Fase 1). O prompt descreve movimento orgânico consistente com o estilo da Zenya.

**Critérios de aceite:**
- [ ] Video Prompt Engineer recebe imagem + estilo e retorna prompt de vídeo
- [ ] Integração com Kling API: imagem → vídeo (formato 9:16, duração 5-10s)
- [ ] Abstração de provider: trocar Kling por ComfyUI+RunPod sem mudar a interface
- [ ] Vídeo gerado armazenado no Supabase Storage
- [ ] Falha da API de vídeo não bloqueia o pipeline — conteúdo vai para fila com status `video_failed`

---

### FR4 — Voice Generation (ElevenLabs)

**Fase:** 1  
**Prioridade:** P0

Zenya narra o conteúdo em PT-BR usando a voz ElevenLabs já configurada. O Copy Specialist gera o roteiro de narração junto com a caption. A geração de áudio é independente da geração visual.

**Critérios de aceite:**
- [ ] Copy Specialist gera: caption (Instagram) + narração (roteiro para voz)
- [ ] ElevenLabs gera áudio da narração com a voz da Zenya
- [ ] Áudio armazenado no Supabase Storage como arquivo .mp3
- [ ] Conteúdo sem narração (apenas música) é suportado como variação

---

### FR5 — Assembly (Creatomate)

**Fase:** 1  
**Prioridade:** P0

O sistema monta o Reel final combinando: vídeo gerado + áudio ElevenLabs + legenda animada + branding Sparkle/Zenya. Output: arquivo .mp4 pronto para publicação.

**Critérios de aceite:**
- [ ] Assembly combina: vídeo + áudio + legenda + logo/branding
- [ ] Output .mp4 em formato 9:16, resolução mínima 1080×1920
- [ ] Legenda sincronizada com narração (se houver)
- [ ] Creatomate API como provider inicial (abstração para Remotion futuro)
- [ ] Assembly falha graciosamente — status `assembly_failed` na fila

---

### FR6 — Content Calendar e Ideação

**Fase:** 1 (básico) / Fase 2 (automatizado)

O calendário define o que produzir, quando e com qual estilo. Na Fase 1, briefs são criados manualmente ou por template. Na Fase 2, o Research Agent alimenta ideação com trending.

**Critérios de aceite (Fase 1):**
- [ ] Criação de brief via Portal: tema, mood, estilo (cinematic/influencer), data alvo
- [ ] Fila de produção visível no Portal (status de cada peça no pipeline)
- [ ] Máximo 5 peças simultâneas em produção por vez (controle de carga)

---

### FR7 — Approval Queue (Portal)

**Fase:** 1  
**Prioridade:** P0

Interface de aprovação no Portal: tela cheia, uma peça por vez, vídeo com autoplay, caption editável, botões de ação. Friday notifica via WhatsApp quando há peças aguardando.

**Critérios de aceite:**
- [ ] Portal exibe fila de conteúdo `pending_approval`
- [ ] Visualização: preview fullscreen (imagem ou vídeo player)
- [ ] Navegação: anterior / próximo com contador ("3 de 5 hoje")
- [ ] Caption exibida abaixo do preview com botão de edição inline
- [ ] Ações: ✅ Aprovar | ✏️ Editar | ❌ Rejeitar
- [ ] Aprovação em lote: "Aprovar todos restantes"
- [ ] Friday envia mensagem WhatsApp quando fila tem ≥ 1 item pendente
- [ ] Rejeição requer motivo (texto livre) — salvo para aprendizado futuro

---

### FR8 — Publicação (Instagram Reels)

**Fase:** 1  
**Prioridade:** P1

Conteúdo aprovado é publicado automaticamente no Instagram Reels via API no horário agendado.

**Critérios de aceite:**
- [ ] Conteúdo aprovado vai para fila `scheduled` com timestamp de publicação
- [ ] Publicação automática via Instagram Graph API no horário configurado
- [ ] Status atualizado após publicação: `published` com URL do post
- [ ] Falha de publicação notifica Friday; conteúdo fica em `publish_failed` para retentar

---

### FR9 — Brain Integration

**Fase:** 1  
**Prioridade:** P1

O pipeline consulta o Brain (namespace `sparkle-lore`) antes de produzir. O conteúdo publicado é ingerido de volta ao Brain para evitar repetição.

**Critérios de aceite:**
- [ ] Image Prompt Engineer consulta `sparkle-lore` para restrições de personagem
- [ ] Conteúdo publicado é ingerido no namespace `sparkle-lore` com metadata (tema, data, performance)
- [ ] IP Auditor valida que o conteúdo não contradiz o lore antes da publicação
- [ ] Conteúdo muito similar a algo publicado nos últimos 7 dias é sinalizado

---

## Métricas de Sucesso

| Métrica | Meta Fase 1 | Como Medir |
|---------|-------------|------------|
| Taxa de aprovação sem edição | ≥ 70% das peças | Registro de `mauro_edits` vazio no approve |
| Rejeição por inconsistência Zenya | < 10% | `rejection_reason` contendo "inconsistência" |
| Throughput do pipeline | 5 peças/dia sem intervenção técnica | `pipeline_log` sem erros manuais |
| Latência end-to-end | < 15 min por peça | `created_at` → `assembly_done` |
| Custo por peça | < R$5 | Soma Kling + ElevenLabs + Creatomate |

---

## Requisitos Não-Funcionais

| NFR | Valor | Justificativa |
|-----|-------|---------------|
| Volume | 5 peças/dia (Fase 1) | Calendário editorial sustentável |
| Latência do pipeline | < 15 min por peça | Geração de imagem + vídeo + assembly |
| Consistência visual | Tier A obrigatório como referência | Sem LoRA, a Style Library é o único guardião |
| Aprovação humana | 100% das peças (Fase 1) | Mauro valida antes de qualquer publicação |
| Custo de geração | < R$5 por peça (Fase 1) | Kling API + ElevenLabs + Creatomate |
| Disponibilidade do pipeline | Best effort — falhas não bloqueiam outras peças | Cada peça é independente |

---

## Fora de Escopo (Fase 1)

- Conteúdo do Mauro (não é Zenya)
- Criativos de anúncio para clientes
- TikTok e YouTube Shorts (publicação automática)
- LoRA training da Zenya
- Research Agent automatizado
- Aprovação parcialmente automática
- Outros personagens além da Zenya

---

## Dependências

| Dependência | Status | Bloqueante para |
|-------------|--------|-----------------|
| Style Library (FR1) | A construir | FR2, FR3, todo o pipeline |
| ElevenLabs voice Zenya | Já integrado | FR4 |
| Brain namespace sparkle-lore | Funcional (50 chunks) | FR9 |
| Portal Next.js | Funcional | FR7 (Content Queue View) |
| Kling API key | ⚠️ BLOCKER — Mauro obtém em klingai.com | FR3 |
| Creatomate API key | ⚠️ BLOCKER — Mauro obtém em creatomate.com | FR5 |
| Instagram Graph API | ⚠️ BLOCKER — Mauro configura Meta Developer App + Business Account | FR8 |

---

## Referências

- Architecture: `docs/architecture/domain-content-zenya-architecture.md`
- Organism Blueprint: `memory/project_organism_blueprint.md`
- Organ+Squad Model: `memory/architecture_organ_squad_model.md`
- Tool Evaluations: `memory/tool_evaluations_2026_04_06.md`
