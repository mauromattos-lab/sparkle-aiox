# Sparkle OS — Processos Operacionais

**Versão:** 1.0 | **Autor:** Orion | **Data:** 2026-03-29
**Status:** OBRIGATÓRIO — todo agente segue estes processos sem exceção.

> Não existe "vou fazer do meu jeito porque é mais rápido".
> Processo existe para eliminar retrabalho, não para criar burocracia.

---

## Princípios Fundamentais

1. **Ritmo de IA, não de humano.** 60h distribuídas em 3 agentes = 15-20h contínuas. Planos não têm prazo humano.
2. **Especialista chama especialista.** Nenhum agente generaliza. UX precisa de pesquisa → chama @analyst com EXA. @dev precisa de spec → chama @architect.
3. **Todo output é input.** Cada entrega deve ser consumível pelo próximo agente sem retrabalho de interpretação.
4. **Nenhum artefato vai para produção sem QA.** Sem exceção. Nem "é só um texto", nem "é só um SQL".
5. **Processo define sequência. Orion define prioridade.** O processo diz COMO. Orion diz QUANDO e em que ordem.

---

## Modelo de Roteamento de IA

| Tarefa | Modelo |
|--------|--------|
| Arquitetura, estratégia, decisão complexa | Opus |
| Implementação, criação de artefatos, código | Sonnet |
| Verificação, auditoria, checklists simples | Haiku |
| Classificação, formatação em n8n (low-criticidade) | Groq (llama-3.1-8b-instant) |

---

## Protocolo de Colaboração Entre Agentes

### Quando chamar especialista vs. fazer você mesmo

| Situação | Ação |
|----------|------|
| @ux precisa de referências visuais atuais | Chama @analyst → EXA busca referências |
| @dev precisa de spec de arquitetura | Chama @architect → blueprint antes de implementar |
| @po precisa de dados de mercado | Chama @analyst → EXA + Apify |
| @qa encontra bug | Reporta para @dev com relatório claro — NÃO conserta |
| @sm identifica gargalo no pipeline | Alerta Orion — NÃO reordena sozinho |
| @devops precisa de schema de banco | Chama @architect para blueprint, não inventa |
| Qualquer agente precisa de docs de biblioteca | Context7 — nunca usa conhecimento de treinamento |

### Formato de handoff entre agentes

Todo agente ao entregar deve incluir no output:
```
STATUS: [AGUARDANDO_QA | AGUARDANDO_PO | PRONTO_PARA_ATIVAR]
PRÓXIMO: @[agente]
ENTREGA: [descrição do que foi feito]
INPUTS_PARA_PRÓXIMO: [o que o próximo agente precisa saber]
PENDÊNCIAS: [o que está bloqueado ou incompleto]
```

---

## Processo 1 — Nova Landing Page por Nicho

**Quando usar:** Criar landing page para novo nicho de cliente Zenya.

```
1. @analyst (EXA)
   → pesquisa dores, desejos e linguagem do nicho
   → entrega: brief com dores reais, termos do setor, benchmarks visuais de referência
   → status: AGUARDANDO_PO

2. @po
   → recebe brief do @analyst
   → cria copy completa: H1, subtítulo, 3 benefícios, depoimento, CTAs, pricing copy
   → entrega: copy_[nicho].md
   → status: AGUARDANDO_UX

3. @ux
   → recebe copy + brief de referências
   → se precisar de mais referências visuais: aciona @analyst com EXA
   → cria brief visual: paleta, componentes, layout hero
   → entrega: ux-brief_[nicho].md
   → status: AGUARDANDO_DEV

4. @dev
   → recebe copy + ux-brief + template base
   → implementa HTML com: data-nicho, UTM, fbq, WA links corretos
   → entrega: landing/[nicho]/index.html
   → status: AGUARDANDO_UX_REVIEW

5. @ux (review)
   → Playwright screenshot em desktop + mobile
   → valida: hierarquia visual, copy aplicada corretamente, responsividade
   → entrega: relatório visual com screenshots
   → status: AGUARDANDO_QA

6. @qa
   → valida: links WA, UTM params, fbq events, deploy workflow, assets existentes
   → entrega: relatório QA com pass/fail por item
   → status: AGUARDANDO_SM | APROVADO_DEPLOY

7. @sm
   → audit completo → go/no-go
   → se aprovado: status PRONTO_DEPLOY

8. @devops
   → push + deploy via GitHub Actions
   → confirma URL em produção
   → status: FUNCIONAL
```

**Gate obrigatório:** @qa deve reportar ZERO bugs críticos antes de @sm liberar.

---

## Processo 2 — Novo Cliente Zenya (Onboarding)

**Quando usar:** Novo contrato assinado, implementar Zenya do zero.

```
1. Mauro
   → preenche checklist de onboarding (nome, produto, público, número WA, concorrentes, tom)
   → entrega: briefing preenchido

2. @analyst (Apify + EXA)
   → scraping site + Instagram do cliente
   → pesquisa concorrentes do nicho
   → entrega: brief de negócio com produtos, preços, linguagem, diferencial
   → status: AGUARDANDO_DEV

3. @dev
   → cria system prompt baseado no brief + template de persona Zenya
   → cria KB inicial (mínimo 30 registros) no Supabase
   → configura system prompt no n8n (PUT API)
   → entrega: system-prompt.md + confirmação de KB
   → status: AGUARDANDO_PO

4. @po
   → review do system prompt: tom de voz, alinhamento com SOUL.md, copy das respostas
   → entrega: system-prompt_v2.md com ajustes
   → status: AGUARDANDO_QA

5. @qa
   → executa test-plan do cliente: 20+ conversas de teste por categoria
   → valida: identidade, escalamento humano, edge cases
   → entrega: relatório de teste com pass/fail
   → status: AGUARDANDO_DEV (se bug) | AGUARDANDO_DEVOPS (se aprovado)

6. @devops
   → configura n8n: clonar workflows, ativar, configurar variáveis
   → configura Chatwoot: inbox + webhook + número Z-API
   → entrega: IDs dos workflows ativos
   → status: AGUARDANDO_SM

7. @sm
   → audit pré-go-live: todos os itens do checklist de ativação
   → go/no-go
   → se aprovado: status AGUARDANDO_MAURO

8. Mauro
   → toggle manual dos workflows (bug n8n #21614)
   → mensagem para cliente: "Zenya está no ar"
   → status: FUNCIONAL
```

---

## Processo 3 — Novo Workflow n8n

**Quando usar:** Criar workflow novo (não clone de existente).

```
1. @architect
   → blueprint: nodes, conexões, lógica de decisão, tratamento de erros
   → entrega: blueprint_[nome].md com diagrama textual
   → status: AGUARDANDO_DEV

2. @dev
   → implementa JSON seguindo blueprint
   → regras obrigatórias:
     - Info node com variáveis hardcoded (proibido $env.*)
     - continueOnFail: true em todos os HTTP Requests
     - Error handler antes do Responder
   → entrega: n8n-workflows/[nome].json
   → status: AGUARDANDO_QA

3. @qa
   → valida estrutura: Info node presente, sem $env.*, continueOnFail presente
   → valida lógica: nodes conectados corretamente, fallbacks mapeados
   → entrega: relatório QA
   → status: AGUARDANDO_DEV (se bug) | PRONTO_PUT (se aprovado)

4. @dev
   → PUT via n8n API
   → confirma HTTP 200 + versionId
   → status: ARTEFATO (aguarda toggle manual)

5. Mauro
   → toggle manual no UI n8n (bug #21614 — webhooks só registram após toggle)
   → status: FUNCIONAL
```

---

## Processo 4 — Planejamento de Nova Fase/Iniciativa Grande

**Quando usar:** Qualquer iniciativa que dure mais de 1 sprint (ex: Fase 2 — Conteúdo).

```
1. Mauro
   → visão + contexto (áudio transcrito ou texto direto)
   → entrega: briefing da iniciativa

2. @analyst (EXA + Apify) — PARALELO com 3
   → pesquisa de mercado: players, preços, benchmarks, gaps
   → pesquisa técnica: stack disponível, custos, casos de uso
   → entrega: docs/strategy/[iniciativa]-research.md

3. @architect — PARALELO com 2
   → blueprint técnico preliminar baseado na visão do Mauro
   → identifica dependências, riscos, decisões de stack
   → entrega: docs/architecture/blueprint-[iniciativa].md

4. @pm
   → recebe outputs de 2 + 3
   → cria PRD formal (personas, features, critérios de aceitação)
   → entrega: docs/prd/[iniciativa].md
   → status: AGUARDANDO_PO

5. @po
   → avalia produto: viabilidade, pricing, posicionamento
   → revisa PRD com lente de produto
   → entrega: docs/reviews/po-[iniciativa].md

6. @sm
   → avalia capacidade: o que existe, o que falta, sequência ideal
   → propõe breakdown em sprints
   → entrega: docs/sprints/[iniciativa]-sprint-plan.md

7. Orion
   → sintetiza tudo → plano de execução
   → atualiza agent-queue.md com novos itens
   → inicia execução em paralelo (desbloqueados primeiro)
```

---

## Processo 5 — Criação de Novo Agente/Squad

**Quando usar:** Identificar necessidade de especialização que não existe.

```
1. Orion
   → identifica gap: função repetitiva sem agente, ou agente genérico demais
   → entrega: briefing do agente necessário

2. @architect
   → define escopo: O que faz. O que NÃO faz. Com quem colabora.
   → define ferramentas obrigatórias (da agent-toolkit-standard.md)
   → entrega: spec do agente

3. @squad-creator
   → cria definição YAML do agente
   → inclui: persona, comandos, dependências, ferramentas, regras de handoff
   → entrega: squads/[nome]/

4. @qa
   → valida: ferramentas mapeadas, handoffs definidos, processos incluídos
   → entrega: relatório de validação

5. Orion
   → ativa agente em sessão de teste
   → valida comportamento real
   → adiciona ao ecossistema (atualiza agent-toolkit-standard.md)
```

---

## Processo 6 — Conteúdo IA (Fase 2 — quando ativo)

**Quando usar:** Criar conteúdo para perfil Instagram de cliente ou personagem Sparkle.

```
1. @content-strategist (a criar)
   → recebe: persona do negócio + KB do Supabase + métricas recentes
   → cria: plano de conteúdo semanal (3-4 Reels + 2-3 Carrosseis + Stories diários)
   → entrega: content-plan_[cliente]_[semana].md

2. @prompt-engineer (a criar — especialista cinematográfico)
   → recebe: plano de conteúdo + brief visual da marca
   → cria: prompts para imagem/vídeo (foto, cinema, série, drama, narrativa)
   → entrega: prompts_[cliente]_[semana].json

3. @dev
   → executa geração via Replicate API (MVP) ou RunPod (escala)
   → entrega: assets gerados + metadados

4. @ux
   → review visual dos assets
   → valida: consistência de marca, qualidade técnica
   → entrega: aprovados ou lista de ajustes

5. @po
   → review de copy das legendas
   → valida: tom de voz, CTA, hashtags
   → entrega: conteúdo aprovado para publicação

6. @dev / n8n
   → agenda publicação via Instagram Graph API
   → confirma horário ideal por nicho
   → status: FUNCIONAL (publicado)
```

---

## Auditoria de Processos — @sm

**Frequência:** Semanal
**Responsável:** @sm

Checklist:
- [ ] Todo item em agent-queue.md tem responsável e status correto?
- [ ] Algum item está em AGUARDANDO_QA há mais de 48h sem movimento?
- [ ] Todos os workflows n8n ativos têm continueOnFail e Info node?
- [ ] Ferramentas do agent-toolkit-standard.md estão sendo usadas (não só documentadas)?
- [ ] Algum agente está generalizando (fazendo tarefa de outro especialista)?
- [ ] Processos deste documento foram seguidos nos itens entregues?

---

## Regra de Ouro

> Quando um agente termina sua parte, não espera. Marca status, define próximo, passa o bastão.
> Orion não precisa estar no meio de cada handoff — só em gates estratégicos.

---

*Atualizar quando novos processos forem identificados. Orion mantém este documento.*
