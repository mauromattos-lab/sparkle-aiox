# Sparkle OS — Processo Operacional v2.0

**Versão:** 2.0 | **Data:** 2026-04-05 | **Substitui:** sparkle-os-processes.md v1.0
**Status:** OBRIGATÓRIO — todo agente, todo squad, todo domínio, sem exceção.

> Este documento é a constituição operacional da Sparkle.
> Não é sugestão. Não tem exceção por urgência. Não tem "essa vez é diferente".
> Se há 100 agentes amanhã, todos seguem este processo.

---

## Princípio Central: Two-Phase Obrigatório

Todo trabalho na Sparkle tem duas fases separadas. Sempre.

```
FASE 1 — PLANEJAMENTO          FASE 2 — EXECUÇÃO
────────────────────           ────────────────────
@pm    → PRD                   @dev    → Implementação
@architect → Spec técnica      @qa     → Validação
@sm    → Stories               @po     → Aceite
                               @devops → Deploy
```

**Regra inviolável:** Nenhum agente da Fase 2 começa antes da Fase 1 estar completa e persistida no Supabase.

**Por que:** Contexto limpo gera resultado 10x. Agente que implementa sem spec inventa arquitetura. Agente que deploya sem QA quebra produção. As duas fases existem porque planejamento e execução são trabalhos cognitivamente diferentes — misturá-los degrada os dois.

---

## Os Gates

Cada transição entre agentes é um gate. Gate tem critério de saída verificável — não é julgamento, é checklist.

### Gate 1 — PRD → Spec Técnica
**Quem:** @pm entrega para @architect
**Critério de saída obrigatório:**
- [ ] PRD salvo em `docs/prd/{nome}.md`
- [ ] Todos os Functional Requirements (FR) listados e numerados
- [ ] Escopo "fora do escopo" explicitado
- [ ] Status gravado: `POST /system/state` com `status: "prd_approved"`

### Gate 2 — Spec → Stories
**Quem:** @architect entrega para @sm
**Critério de saída obrigatório:**
- [ ] Design spec salvo em `docs/stories/{sprint}/design-spec.md`
- [ ] Stack e decisões técnicas documentadas
- [ ] Riscos identificados
- [ ] Status gravado: `POST /system/state` com `status: "spec_approved"`

### Gate 3 — Stories → Implementação
**Quem:** @sm entrega para @dev
**Critério de saída obrigatório:**
- [ ] Cada story tem: título, user story, acceptance criteria numerados, IVs (Integration Verifications)
- [ ] Sequência de stories validada (dependências mapeadas)
- [ ] Status gravado: `POST /system/state` com `status: "stories_ready"`

### Gate 4 — Implementação → QA
**Quem:** @dev entrega para @qa
**Critério de saída obrigatório:**
- [ ] Código implementado e commitado
- [ ] Cada acceptance criterion da story implementado (marcar [x] na story)
- [ ] Nenhum `TODO` ou placeholder em código de produção
- [ ] Status gravado: `POST /system/state` com `status: "dev_complete"`

### Gate 5 — QA → Aceite
**Quem:** @qa entrega para @po
**Critério de saída obrigatório:**
- [ ] Cada acceptance criterion testado e validado
- [ ] Integration Verifications (IVs) executadas
- [ ] Bugs P0/P1 documentados e bloqueantes até resolução
- [ ] Status gravado: `POST /system/state` com `status: "qa_approved"` ou `"qa_failed"`
- [ ] Se QA falhou → volta para @dev com relatório específico (não genérico)

### Gate 6 — Aceite → Deploy
**Quem:** @po entrega para @devops
**Critério de saída obrigatório:**
- [ ] Cada FR do PRD cruzado contra o que foi implementado (nenhum FR esquecido)
- [ ] Story marcada como DONE no arquivo
- [ ] Status gravado: `POST /system/state` com `status: "accepted"`

### Gate 7 — Deploy → Funcional
**Quem:** @devops confirma
**Critério de saída obrigatório:**
- [ ] Deploy executado na VPS
- [ ] Health check OK
- [ ] Sem erros nos logs pós-deploy
- [ ] Status gravado: `POST /system/state` com `status: "funcional", "verified": true`

---

## Fonte de Verdade Única

**O estado de qualquer item vive no Supabase. Não em markdown. Não na memória de sessão.**

### Antes de começar qualquer trabalho:
```
GET https://runtime.sparkleai.tech/system/state?sprint_item=ITEM-ID
```
Leia o estado atual. Se o estado não bater com o que você assumia, corrija o banco — não assuma.

### Ao concluir qualquer gate:
```json
POST https://runtime.sparkleai.tech/system/state
{
  "sprint_item": "ITEM-ID",
  "status": "gate_status",
  "verified": true,
  "verification_source": "o que foi verificado",
  "notes": "resumo específico do que foi feito",
  "handoff_to": "@próximo-agente",
  "completed": false
}
```

**`completed: true` só quando @devops confirmar deploy funcional.**

---

## Formato de Handoff — Inviolável

Todo agente ao concluir seu gate entrega este bloco completo ao próximo. Sem este bloco, o próximo agente não começa.

```
---
GATE_CONCLUÍDO: [número e nome do gate]
STATUS: [AGUARDANDO_QA | AGUARDANDO_PO | AGUARDANDO_DEVOPS | FUNCIONAL | FAILED]
PRÓXIMO: @[agente]
SPRINT_ITEM: [ID]

ENTREGA:
  - [arquivo: path completo]
  - [configuração: valores específicos]
  - [ID crítico: valor]

SUPABASE_ATUALIZADO: sim | não
  
PROMPT_PARA_PRÓXIMO: |
  Você é @[agente]. Contexto direto — comece aqui.

  O QUE FOI FEITO:
  [Dados específicos: paths, IDs, valores — nunca descrições genéricas]

  SUA TAREFA:
  [Instrução direta e verificável]

  CRITÉRIOS DE SAÍDA DO SEU GATE:
  - [ ] [item verificável]
  - [ ] [item verificável]

  SE aprovado: STATUS = [X], PRÓXIMO = @[agente]
  SE reprovado: STATUS = [Y], PRÓXIMO = @[agente que falhou]

PENDÊNCIAS (não bloqueantes):
  - [item específico]
---
```

**Por que o PROMPT_PARA_PRÓXIMO existe:** O próximo agente começa em contexto limpo. Ele não leu a conversa anterior. Ele não sabe o que você fez. A inteligência de "o que o próximo precisa saber" fica no agente que acabou de trabalhar — não em Orion, não em Mauro.

---

## Contexto Limpo por Agente

Cada agente recebe apenas o contexto necessário para o seu gate. Não a conversa inteira. Não o histórico de sessões.

**O que todo agente lê ao ser ativado:**
1. `AGENT_CONTEXT.md` — ecossistema geral
2. O PROMPT_PARA_PRÓXIMO do handoff anterior
3. Os arquivos específicos mencionados no handoff
4. `GET /system/state?sprint_item=X` — estado atual no banco

**O que todo agente NÃO lê:**
- Conversas anteriores de outras sessões
- Todos os docs de arquitetura
- Work logs completos
- Qualquer coisa não mencionada no handoff

**Por que:** Contexto limpo = foco total na tarefa. Agente que lê tudo fica confuso, toma decisões baseadas em informação desatualizada, e gera output genérico.

---

## Roteamento de Modelos

| Tipo de trabalho | Modelo | Por que |
|-----------------|--------|---------|
| PRD, arquitetura, decisão complexa | Opus | Raciocínio estratégico |
| Implementação, código, stories | Sonnet | Execução eficiente |
| QA checklist, validação simples | Sonnet ou Haiku | Verificação focada |
| Classificação, formatação (n8n) | Groq llama-3.1-8b | Low-criticidade, barato |

**Regra:** Subagentes DEVEM especificar modelo. Nunca herdar por padrão sem decidir conscientemente.

---

## Roteamento de Agentes

Orion orquestra. Nunca executa o que é de especialista.

| Situação | Agente obrigatório |
|----------|--------------------|
| Criar PRD, definir escopo, priorizar | `@pm` |
| Decisão arquitetural, design de sistema | `@architect` |
| Criar/detalhar stories | `@sm` |
| Implementar código, deploy, debug | `@dev` |
| Validar, testar, QA | `@qa` |
| Aceitar stories, validar PRD vs entrega | `@po` |
| Deploy, infra, CI/CD, MCPs | `@devops` |
| Pesquisa de mercado, análise competitiva | `@analyst` |
| Criar novo squad, definir agentes | `@squad-creator` |

---

## Squad Pattern — Para Qualquer Domínio

Quando um novo domínio da Sparkle precisar de agentes próprios (ex: squad de tráfego pago, squad de conteúdo, squad de vendas), o padrão é sempre o mesmo:

```
1. @squad-creator define os agentes do squad
2. Cada agente tem: nome, papel, gates que opera, ferramentas disponíveis
3. O squad herda este processo — gates, handoffs, fonte de verdade
4. @pm cria PRD antes de qualquer implementação do squad
5. O squad opera como empresa com departamentos — paralelo onde possível
```

**Não existe squad sem processo.** Um squad sem gates é um grupo de agentes improvisando.

---

## Paralelismo vs. Sequencial

**Paralelo:** quando não há dependência entre itens
```
Item A (frontend) ──────────────────→ Gate 4
Item B (backend)  ──────────────────→ Gate 4
Item C (migrations) ────────────────→ Gate 4
                                       ↓
                               QA valida os 3
```

**Sequencial:** quando há dependência real
```
Migration criada → Deploy migration → Implementar handler que usa a migration
```

**Regra:** Se tem 8 itens desbloqueados → 8 agentes em paralelo. Não 3. Gates de um item não bloqueiam gates de outro item independente.

---

## O que Nunca Fazer

| Proibido | Por que |
|----------|---------|
| Implementar sem PRD aprovado | Inventa arquitetura, gera retrabalho |
| Pular gate de QA "porque é simples" | QA existe exatamente para o que parece simples |
| Salvar estado só em markdown | Markdown não é consultável entre sessões |
| Agente assume estado sem consultar o banco | Estado muda entre sessões sem o agente saber |
| Orion implementar código diretamente | Orion orquestra, @dev implementa |
| @dev fazer QA do próprio código | Conflito de interesses, cria ponto cego |
| Ativar em produção sem @devops | @devops é o único gate de deploy |
| Testar com cliente real sem aprovação Mauro | Gate obrigatório: teste isolado → aprovação → ativação |

---

## Checklist de Início de Sessão

Todo agente ao ser ativado executa esta sequência antes de qualquer ação:

```
1. Ler AGENT_CONTEXT.md
2. GET /system/state — verificar estado atual dos itens relevantes
3. Ler o PROMPT_PARA_PRÓXIMO do handoff recebido
4. Confirmar: o gate anterior foi concluído? (verificar no banco, não assumir)
5. Só então começar o trabalho do gate atual
```

Se o gate anterior não foi concluído no banco → reportar para Orion antes de prosseguir.

---

## Referências

- Metodologia base: AIOX Squad (two-phase approach, contexto limpo, PRD→Arch→Stories→Code)
- PRDs referência: `docs/prd/pipeline-comercial-prd.md`, `docs/prd/zenya-onboarding-system-prd.md`
- Contexto dos agentes: `AGENT_CONTEXT.md`
- Estado do sistema: `docs/agent-queue.md` (leitura humana) + Supabase `agent_work_items` (fonte de verdade)

---

*Sparkle OS Process v2.0 — Todo agente segue. Todo squad herda. Sem exceção.*
