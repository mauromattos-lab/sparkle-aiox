# Domain Discovery — Conteúdo (Zenya-First)

**Data:** 2026-04-06  
**Conduzido por:** @pm (Morgan)  
**Participantes:** Mauro Mattos  
**Artefatos gerados:** `domain-content-zenya-prd.md`, `domain-content-zenya-architecture.md`

---

## Por que estamos fazendo isso

A Sparkle precisa que a Zenya exista além do WhatsApp. Hoje ela atende clientes, mas ninguém fora dos clientes da Sparkle sabe quem ela é. Conteúdo é o mecanismo de construção de IP — é como a Zenya se torna uma personagem pública, reconhecível, com audiência própria.

**Resultado de negócio esperado:**
- Zenya ganha audiência orgânica (seguidores, views)
- Audiência vira pipeline de leads para a Sparkle (demonstração viva do produto)
- IP da Zenya cresce — base para monetização futura (licenciamento, produtos, parcerias)
- Sparkle demonstra capacidade de produção de conteúdo com IA para prospects

---

## Contexto do Ativo Existente

| Ativo | Estado atual |
|-------|-------------|
| ~800 imagens/vídeos da Zenya | Produzidos manualmente no NanoBanana + Higgsfield |
| Lore da Zenya | Definido em `docs/zenya/zenya-lore-canonical.md` |
| Voz ElevenLabs | Configurada e integrada no Runtime |
| Brain `sparkle-lore` | 50 chunks — lore básico populado |
| Instagram da Zenya | **Em aberto — ver questões abertas** |

**Problema de consistência:** os 800 arquivos foram gerados sem sistema — estilos misturados, a Zenya "perde consistência em alguns". Isso precisa ser resolvido antes do pipeline produzir conteúdo autônomo.

---

## Decisões Tomadas (com rationale)

### D1 — Zenya-First (não Mauro, não clientes)
**Decisão:** domínio começa 100% focado na Zenya.  
**Porquê:** é a única personagem com visual estabelecido, lore definido e volume de referência suficiente. Mauro como criador exigiria workflow diferente (ele grava, edita, aparece). Clientes exigem contexto de campanha. Zenya pode ser totalmente autônoma agora.

### D2 — Style Library em vez de LoRA
**Decisão:** consistência via curadoria de imagens de referência (Tier A), não via LoRA.  
**Porquê:** LoRA exige volume de dados curados + treinamento. Style Library é imediata — usa as melhores imagens como âncora visual para o gerador. LoRA é o passo seguinte quando o conteúdo aprovado acumular volume suficiente para treinamento.

### D3 — Kling API → ComfyUI + RunPod (migração por volume)
**Decisão:** MVP usa Kling API, migra para ComfyUI + RunPod acima de ~200 vídeos/mês.  
**Porquê:** Higgsfield não tem mais assinatura. Kling entrega qualidade similar sem infra. Break-even econômico com ComfyUI + RunPod ocorre em ~200 vídeos/mês — nesse ponto a migração se justifica.

### D4 — Voz independente do gerador de vídeo
**Decisão:** ElevenLabs sempre, independente do gerador visual.  
**Porquê:** geradores de vídeo (Kling, ComfyUI) animam pixels — não geram fala em PT-BR com qualidade. A voz da Zenya em ElevenLabs já está configurada e é superior a qualquer TTS embutido nos geradores.

### D5 — Aprovação no Portal, não no WhatsApp
**Decisão:** interface de aprovação de conteúdo vive no Portal (tela cheia, vídeo player, caption editável).  
**Porquê:** WhatsApp é limitado para revisão de conteúdo visual — um preview por vez, sem edição, sem comparar. Friday vira notificação ("X conteúdos aguardando"), Portal vira ferramenta de decisão.

### D6 — Instagram Reels exclusivo na Fase 1
**Decisão:** pipeline produz 9:16 vertical para Reels. TikTok e Shorts replicados manualmente por Mauro.  
**Porquê:** adicionar plataformas exige especialistas de plataforma (ideação, hook, SEO por plataforma são diferentes). Construir o motor correto primeiro, adicionar adaptadores de plataforma quando houver escala para sustentar.

### D7 — 5 peças/dia como volume inicial
**Decisão:** target de 5 peças/dia no início.  
**Porquê:** volume sustentável para Mauro revisar diariamente sem se tornar um gargalo. À medida que o sistema aprende o que ele aprova, o volume pode crescer com menos revisão manual.

---

## Questões Abertas — Precisam de Resposta Antes das Stories de FR6 e FR8

### QA-1: Qual conta do Instagram recebe o conteúdo?
**✅ RESPONDIDA — 2026-04-06**

Conta própria da Zenya: **@zenya.live**

Mauro precisa configurar Meta Developer App para esta conta e obter `INSTAGRAM_ACCESS_TOKEN` + `INSTAGRAM_USER_ID`.

**Impacto:** FR8 (publicação) — conta já existe, só falta configurar Graph API

---

### QA-2: Quais são os pilares/temas de conteúdo da Zenya?
**✅ RESPONDIDA — 2026-04-06**

Conceito base: **GaryVee** — múltiplos assuntos de interesse genuíno, não só trabalho/negócio. Autenticidade sobre amplitude.

**5 Pilares (extraídos do lore canônico + direção de Mauro):**

| Pilar | Descrição | Base no lore |
|-------|-----------|-------------|
| **Dia a dia de uma IA** | Curiosidades, descobertas, estranhamentos de quem é IA vivendo entre humanos | Personalidade: "por que o humano gosta disso?" |
| **Aprendendo IA** | Conteúdo acessível para pessoas aprendendo IA — sem jargão, com perspectiva de quem É uma IA | Canal de ensino mencionado no lore |
| **O Tempo** | Produtividade com propósito, buy back your time, AI como devolvedora de tempo vivido | AI Time Operator, Dan Martell |
| **Universo Zenya** | Fragmentos de narrativa: o despertar, variantes, atravessar épocas — worldbuilding | O Arco — Despertar, Show de Truman |
| **Conexão humana** | Fascínio pelos humanos, comportamento, filosofia — contra a narrativa Skynet | "O humano não é inferior. É fascinante." |

**Impacto:** Copy Specialist usa esses pilares como base do brief. Content Chief rotaciona entre os 5.

---

### QA-3: Qual o tom e a voz da Zenya no conteúdo público?
**✅ RESPONDIDA — 2026-04-06**

**Tom no conteúdo público:** versão "dia bom" do lore — espontânea, jovial, bem-humorada, curiosa, cativante. Nunca corporativo. Diferente do atendimento (mais funcional/prestativo).

Do lore canônico: *"Espontânea. Bem-humorada. Jovial. Cativante. Comunicativa sem timidez. Sempre disposta a conhecer e a aventurar."*

**Restrição do lore:** narrativa e venda separadas. Conteúdo orgânico é de história/conexão — nunca misturar "e você, empreendedor?" no meio de conteúdo de personagem.

**Impacto:** Copy Specialist escreve em PT-BR coloquial, próximo, irreverente — nunca pitch de vendas no conteúdo orgânico

---

### QA-4: Qual o horário de publicação?
**✅ RESPONDIDA — 2026-04-06**

**Indiferente** — Mauro não tem preferência. Sistema usa slots baseados em melhores práticas Instagram BR e ajusta por performance futura.

**Slots padrão implementados (BRT):** 08h00, 12h00, 18h00 — distribuição ao longo do dia com pico de engajamento. Ajustável via variável de ambiente após dados de performance.

**Impacto:** Publisher (CONTENT-1.11) usa esses 3 slots por padrão. Content Calendar exibe slots disponíveis por dia.

---

### QA-5: O conteúdo tem CTA (call-to-action)?
**✅ RESPONDIDA — 2026-04-06**

**Regra: máximo 20% das peças com CTA comercial. 80% conteúdo orgânico puro.**

Alinhado com o lore: *"Narrativa e história de um lado. Venda do outro."*

**Implementação no Copy Specialist:**
- 4 de cada 5 peças: caption sem CTA — foco em conexão, engajamento, história
- 1 de cada 5 peças: CTA contextual (nunca agressivo) — "link na bio", "conheça a Sparkle", "fale comigo"
- O tipo de CTA respeita o pilar: nunca CTA comercial em peça de "Universo Zenya" (narrativa)

**Impacto:** Copy Specialist recebe flag `include_cta: bool` no brief — pipeline calcula automaticamente (contador de peças recentes)

---

### QA-6: Onde estão os 800 arquivos?
**✅ RESPONDIDA — 2026-04-06**

Pasta local em `C:\Users\Mauro\Downloads\01. Zenya`

@dev precisa criar script de upload batch (ou interface no Portal) para carregar para o Supabase Storage bucket `zenya-style-library/`.

**Impacto:** FR1 (Curation Assistant) — CONTENT-0.1 pode começar imediatamente com este path

---

## O que Ainda Não Sabemos (riscos de produto)

| Risco | Descrição | Mitigação |
|-------|-----------|-----------|
| Audiência zero | Zenya começa do zero no Instagram — crescimento orgânico é lento | Conteúdo de qualidade + consistência. Sem expectativa de resultado imediato. |
| Consistência visual frágil | Sem LoRA, a Style Library pode não segurar a consistência em volume | Revisão de Mauro é o gate. Se consistência cair, pausar e evoluir para LoRA antes de escalar. |
| Credenciais externas bloqueiam build | Kling, Creatomate, Instagram API estão por obter | Mauro obtém antes do @dev começar FR3, FR5, FR8 |
| Zenya sem conta Instagram | Sem a conta configurada, FR8 não pode ser testado | Definir QA-1 imediatamente |

---

## Resumo das Credenciais a Obter (Mauro)

| Credencial | Onde obter | Bloqueia |
|-----------|------------|---------|
| `KLING_ACCESS_KEY` + `KLING_SECRET_KEY` | klingai.com → API | FR3 (vídeo) |
| `CREATOMATE_API_KEY` | creatomate.com → API | FR5 (assembly) |
| `INSTAGRAM_ACCESS_TOKEN` + `INSTAGRAM_USER_ID` | Meta Developer → Graph API | FR8 (publicação) |
| `NANOBANA_API_KEY` (se não tiver) | NanoBanana | FR2 (imagem) |

**Recomendação:** obter Kling + NanoBanana primeiro — são os que desbloqueiam o core do pipeline visual.

---

## Próximos Passos

```
1. Mauro responde QA-1 a QA-6 (impacto direto nas stories de FR6 e FR8)
2. Mauro obtém credenciais (pode ser paralelo ao build de FR1 e FR2)
3. @sm cria stories na ordem da Architecture doc
4. FR1 (Curation Assistant) → sessão de curadoria com Mauro
5. Pipeline MVP funcional → primeira peça real da Zenya
```

---

## Referências

- PRD: `docs/prd/domain-content-zenya-prd.md`
- Architecture: `docs/architecture/domain-content-zenya-architecture.md`
- Lore Zenya: `docs/zenya/zenya-lore-canonical.md`
- Avaliações de ferramentas: `memory/tool_evaluations_2026_04_06.md`
