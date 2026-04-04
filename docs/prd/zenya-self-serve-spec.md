# B4-03: Zenya Self-Serve — Especificacao de Produto

**ID:** B4-03
**Autor:** @pm (Morgan)
**Data:** 2026-04-04
**Status:** DRAFT
**Prioridade:** Backlog (pos-Sprint 8)

---

## 1. Visao Geral

### O que e "self-serve" para clientes Zenya

Self-serve **nao significa autonomia total**. Significa **"gerenciado com painel de autoatendimento"**. O cliente consegue fazer o dia a dia da sua Zenya — ver metricas, treinar o Brain, ajustar tom — sem precisar abrir ticket ou mandar mensagem pro Mauro.

Mauro (e o time Sparkle) continua como guardioes da qualidade. Toda alteracao que pode impactar a experiencia do usuario final passa por curadoria ou tem limites de seguranca automaticos.

### Analogia

Pense no self-serve como um carro com piloto automatico: o cliente dirige no dia a dia, mas o sistema tem guardrails que impedem o carro de sair da pista. A Sparkle e o engenheiro que mantem o carro.

### Objetivos de negocio

1. **Reduzir carga operacional do Mauro** — 80% das solicitacoes de clientes (FAQ, horario, tom) devem ser resolvidas pelo painel
2. **Aumentar retencao** — cliente que ve metricas e interage com o painel tem mais engajamento e percebe mais valor
3. **Justificar tiers de preco** — funcionalidades escalonadas criam upgrade natural de Basic para Premium
4. **Acelerar onboarding** — cliente pode comecar a alimentar o Brain antes mesmo do kickoff completo

---

## 2. Funcionalidades do Painel do Cliente

### P0 — Essencial (MVP)

#### 2.1 Dashboard de Metricas e Historico de Conversas

**O que ja existe:** O portal (`portal/app/dashboard/page.tsx`) ja exibe metricas Zenya — total de conversas no mes, conversas hoje, taxa de resolucao, conversoes, satisfacao. O componente `DashboardZenya` consome `/api/metrics/zenya`.

**O que falta construir:**

- **Historico de conversas**: lista paginada de conversas (data, resumo, outcome, sentimento)
- **Detalhe de conversa**: visualizar mensagens trocadas entre Zenya e o cliente final (read-only, sem dados sensiveis como telefone completo — mostrar apenas ultimos 4 digitos)
- **Filtros**: por data, outcome (atendido, convertido, escalado), sentimento
- **Exportacao**: CSV do periodo selecionado

**Criterios de aceitacao:**
- [ ] Cliente ve lista de conversas dos ultimos 30 dias com paginacao (20 por pagina)
- [ ] Cada conversa mostra: data/hora, resumo de 1 linha, badge de outcome, icone de sentimento
- [ ] Clicar na conversa abre modal com historico completo de mensagens
- [ ] Telefone do cliente final aparece mascarado (ex: ****-1234)
- [ ] Filtro por data (date range picker) e por outcome funciona
- [ ] Botao "Exportar CSV" gera download com dados do filtro atual
- [ ] Tempo de carregamento < 2 segundos para 30 dias de dados

**Experiencia do usuario:** O cliente abre o painel e em 3 segundos sabe: quantas conversas a Zenya resolveu, qual a satisfacao, e pode explorar qualquer conversa especifica sem precisar pedir pra Sparkle.

---

#### 2.2 Treinamento do Brain — Upload de FAQs, Produtos e Regras

**O que ja existe:** Pipeline de Brain ingest (`sparkle-runtime/runtime/tasks/handlers/brain_ingest.py`) com curadoria (`portal/app/brain/curation/page.tsx`). O curation hoje e acessado pela Sparkle (Mission Control).

**O que falta construir:**

- **Pagina de upload do cliente**: formulario para enviar conteudo ao Brain
- **Tipos de upload**: FAQ (pergunta + resposta), Informacao de produto, Regra de negocio, Texto livre
- **Preview antes de enviar**: cliente ve como o conteudo sera indexado
- **Status de upload**: fila mostrando "Enviado > Em revisao > Aprovado/Rejeitado"
- **Notificacao**: quando o conteudo for aprovado ou rejeitado, aparecer no painel

**Criterios de aceitacao:**
- [ ] Pagina `/brain/upload` acessivel para clientes com plano Pro ou Premium
- [ ] Formulario com campos: tipo (select), titulo, conteudo (textarea), URL fonte (opcional)
- [ ] Tipo FAQ mostra campos adicionais: pergunta + resposta em formato estruturado
- [ ] Preview renderiza o conteudo antes de enviar
- [ ] Ao enviar, chunk vai para `brain_chunks` com `curation_status = 'pending'` e `client_id` preenchido
- [ ] Lista "Meus envios" mostra uploads do cliente com status atual (pending/approved/rejected)
- [ ] Upload rejeitado mostra o motivo (campo `curation_note`)
- [ ] Limite de 50 uploads pendentes por cliente (prevenir spam)
- [ ] Conteudo com menos de 20 caracteres e rejeitado automaticamente com mensagem explicativa
- [ ] Conteudo com mais de 5.000 caracteres mostra aviso e sugere dividir

**Experiencia do usuario:** O cliente descobre uma pergunta frequente nova dos clientes dele. Abre o painel, clica em "Treinar Brain", digita a pergunta e a resposta, clica em enviar. No dia seguinte, ve que foi aprovado e a Zenya ja sabe responder.

---

### P1 — Importante (segundo release)

#### 2.3 Ajuste de Tom da Zenya

**O que ja existe:** `character_state` no Supabase com `soul_prompt` gerado por Haiku. Client DNA com categorias que incluem tom de comunicacao.

**O que falta construir:**

- **Slider Formal <-> Casual**: controle visual que ajusta o tom entre extremos
- **Selecao de tracos de personalidade**: checkboxes com opcoes como "empatica", "direta", "bem-humorada", "tecnica", "acolhedora", "objetiva"
- **Preview de resposta**: ao mover o slider ou mudar tracos, mostrar exemplo de como a Zenya responderia a 3 perguntas padrao
- **Solicitacao de mudanca**: alteracao nao e imediata — entra como solicitacao para revisao

**Criterios de aceitacao:**
- [ ] Pagina `/zenya/personalidade` acessivel para planos Pro e Premium
- [ ] Slider com 5 niveis: Muito Formal / Formal / Equilibrado / Casual / Muito Casual
- [ ] Selecao de ate 5 tracos de personalidade de uma lista de 12 opcoes pre-definidas
- [ ] Preview mostra resposta simulada para: "Qual o horario de funcionamento?", "Quero fazer uma reclamacao", "Quanto custa o produto X?"
- [ ] Ao salvar, cria registro em nova tabela `zenya_change_requests` com status 'pending'
- [ ] Sparkle recebe notificacao no Mission Control sobre a solicitacao
- [ ] Cliente ve status da solicitacao (Pendente / Aprovado / Ajustado)
- [ ] Slider nao permite valores que violem o tom minimo do nicho (ex: advocacia nao pode ser "Muito Casual")
- [ ] Se soul_prompt atual ja atende, sistema informa "Sua Zenya ja esta configurada assim"

**Experiencia do usuario:** A dona da confeitaria percebe que a Zenya esta formal demais. Abre o painel, move o slider para "Casual", marca "bem-humorada" e "acolhedora", ve o preview e gosta. Clica em salvar. No dia seguinte, recebe notificacao de que foi aprovado e a Zenya ja esta mais descontraida.

---

#### 2.4 Horario de Funcionamento e Respostas Automaticas

**O que ja existe:** Nada especifico no portal. O horario hoje e configurado manualmente no soul_prompt.

**O que falta construir:**

- **Configuracao de horario**: segunda a domingo, horario de inicio e fim por dia
- **Mensagem fora do horario**: texto customizavel que a Zenya envia quando recebe mensagem fora do expediente
- **Mensagem de feriado**: texto para datas especificas
- **Comportamento fora do horario**: opcoes "Apenas informar horario" / "Coletar dados e avisar que vai retornar" / "Funcionar normalmente (24h)"

**Criterios de aceitacao:**
- [ ] Pagina `/zenya/horario` acessivel para planos Pro e Premium
- [ ] Interface visual tipo grade semanal (seg-dom) com horario de inicio/fim por dia
- [ ] Toggle "Aberto/Fechado" por dia (para quem nao abre aos domingos, ex.)
- [ ] Campo de texto para mensagem fora do horario com placeholder sugerido
- [ ] Opcao de adicionar feriados pontuais (data + mensagem)
- [ ] Select de comportamento fora do horario com 3 opcoes
- [ ] Alteracao de horario e imediata (nao precisa de aprovacao) — e apenas metadata
- [ ] Alteracao de mensagem fora do horario passa por validacao basica (sem palavroes, tamanho minimo 10 caracteres)
- [ ] Zenya respeita o horario configurado nas proximas interacoes (integracao com router do runtime)

**Experiencia do usuario:** Escola que fecha as 18h configura horario e mensagem "Oi! Estamos fechadinhos agora, mas amanha a partir das 8h a Zenya te responde. Pode deixar sua mensagem que nao vamos esquecer!". Fora do horario, os clientes recebem isso automaticamente.

---

### P2 — Desejavel (terceiro release)

#### 2.5 Visualizacao da Base de Conhecimento

**O que ja existe:** Brain chunks no Supabase com dominio, conteudo, source_type. Curadoria no Mission Control.

**O que falta construir:**

- **Pagina "O que a Zenya sabe"**: lista categorizada dos chunks aprovados do cliente
- **Busca**: campo de busca que filtra por conteudo
- **Estatisticas**: total de chunks, distribuicao por dominio, data do ultimo upload
- **Indicador de cobertura**: mapa visual mostrando quais areas do negocio estao bem cobertas vs. gaps

**Criterios de aceitacao:**
- [ ] Pagina `/brain/knowledge` acessivel para planos Premium
- [ ] Lista de chunks aprovados agrupados por dominio com accordion expansivel
- [ ] Cada chunk mostra: titulo, preview de 2 linhas, data de aprovacao, source_type
- [ ] Campo de busca filtra chunks em tempo real (client-side para ate 500 chunks)
- [ ] Card de estatisticas: total de chunks, distribuicao por dominio (mini bar chart)
- [ ] Indicador de cobertura baseado nos dominios: verde (>10 chunks), amarelo (3-10), vermelho (<3)
- [ ] Botao "Treinar mais sobre [dominio]" que redireciona para pagina de upload com dominio pre-selecionado
- [ ] Conteudo dos chunks nunca mostra informacao de outros clientes (filtro `client_id` obrigatorio)

**Experiencia do usuario:** O dono da empresa abre "O que a Zenya sabe" e ve que tem 45 chunks sobre produtos mas apenas 2 sobre trocas e devolucoes. Clica em "Treinar mais sobre atendimento" e adiciona as regras de troca.

---

#### 2.6 Sandbox — Testar a Zenya antes de ir ao Vivo

**O que ja existe:** Nada. Testes hoje sao feitos direto no WhatsApp real.

**O que falta construir:**

- **Chat de teste**: interface tipo WhatsApp dentro do portal
- **Contexto sandbox**: conversas de teste nao sao contabilizadas nas metricas
- **Feedback inline**: botao "Resposta boa" / "Resposta ruim" em cada mensagem da Zenya
- **Reset**: botao para limpar conversa e comecar do zero

**Criterios de aceitacao:**
- [ ] Pagina `/zenya/sandbox` acessivel para planos Premium
- [ ] Interface de chat com visual similar ao WhatsApp (bolhas, timestamps)
- [ ] Mensagens processadas pelo mesmo pipeline da Zenya real (brain query + character state)
- [ ] Flag `is_sandbox = true` nas conversas de teste — excluidas de metricas
- [ ] Botao de feedback em cada resposta da Zenya (polegar cima/baixo)
- [ ] Feedbacks salvos em tabela `sandbox_feedback` para analise da Sparkle
- [ ] Limite de 50 mensagens por sessao de sandbox (prevenir abuso de API)
- [ ] Botao "Nova conversa" que reseta o contexto
- [ ] Latencia de resposta < 5 segundos (mesmo SLA do WhatsApp real)

**Experiencia do usuario:** Antes de ativar a Zenya para uma data comemorativa (Dia das Maes), o cliente testa perguntas sobre a promocao especial no sandbox. Ve que a Zenya nao sabe sobre o brinde e vai direto pra pagina de upload treinar.

---

### P3 — Futuro (quarto release)

#### 2.7 Mensagens de Saudacao Personalizadas por Horario

**O que falta construir:**

- **3 faixas de saudacao**: manha (6h-12h), tarde (12h-18h), noite (18h-6h)
- **Texto customizavel por faixa**
- **Preview em tempo real**

**Criterios de aceitacao:**
- [ ] Pagina `/zenya/saudacoes` ou secao dentro de `/zenya/personalidade`
- [ ] 3 campos de texto com placeholder sugerido por faixa
- [ ] Preview mostra como fica em cada periodo
- [ ] Alteracao imediata (metadata, nao impacta soul_prompt)
- [ ] Fallback para saudacao generica se alguma faixa estiver vazia

---

#### 2.8 Blocklist de Palavras e Topicos

**O que falta construir:**

- **Lista de palavras bloqueadas**: a Zenya nao usa essas palavras nas respostas
- **Lista de topicos proibidos**: a Zenya redireciona para atendimento humano se o assunto aparecer
- **Palavras sugeridas por nicho**: lista pre-populada com palavras problematicas do segmento

**Criterios de aceitacao:**
- [ ] Pagina `/zenya/restricoes` ou secao dentro de `/zenya/personalidade`
- [ ] Input de tags para adicionar palavras (max 50 palavras)
- [ ] Input de topicos (max 10 topicos) com descricao do que fazer quando aparecer
- [ ] Sugestoes pre-populadas por nicho (ex: saude -> nao diagnosticar, juridico -> nao dar parecer)
- [ ] Alteracao passa por validacao da Sparkle (nao imediata)
- [ ] A Zenya consulta a blocklist antes de responder

---

## 3. Guardrails de Qualidade

O sistema deve impedir que o cliente quebre a propria Zenya. Estas sao as travas de seguranca:

### 3.1 Curadoria de Brain Obrigatoria

| Regra | Implementacao |
|-------|---------------|
| Uploads vao para fila de curadoria | `curation_status = 'pending'` no insert, nunca `'approved'` direto |
| Aprovacao automatica para conteudo de baixo risco | Chunks do tipo FAQ com confidence > 0.9 no embedding podem ser auto-aprovados (feature flag) |
| Limite de uploads pendentes | Max 50 chunks com `curation_status = 'pending'` por `client_id` |
| Conteudo minimo | Rejeicao automatica se < 20 caracteres |
| Conteudo duplicado | Verificacao de similaridade (cosine similarity > 0.95 com chunks existentes) rejeita com aviso |

### 3.2 Limites de Tom

| Regra | Implementacao |
|-------|---------------|
| Tom tem min/max por nicho | Tabela `niche_tone_rules` com `min_formality` e `max_formality` por nicho |
| Mudanca de tom e solicitacao, nao imediata | Insere em `zenya_change_requests`, Sparkle revisa |
| Preview obrigatorio | Cliente deve ver preview antes de solicitar mudanca |
| Rollback se satisfacao cair | Se `satisfacao` cair > 15% em 48h apos mudanca de tom, reverter automaticamente |

### 3.3 Soul Prompt Protegido

| Regra | Implementacao |
|-------|---------------|
| Cliente nunca edita soul_prompt diretamente | Nao existe interface para isso |
| Mudancas de tom geram sugestao de soul_prompt | Haiku gera novo prompt, Sparkle aprova |
| Historico de versoes do soul_prompt | Tabela `soul_prompt_versions` com timestamp e autor |

### 3.4 Auto-Rollback de Qualidade

| Trigger | Acao |
|---------|------|
| Satisfacao cai > 15% em 48h | Reverter ultima mudanca de tom/soul_prompt |
| Taxa de escalacao sobe > 30% em 24h | Alertar Sparkle + pausar mudancas |
| Cliente final reporta resposta ofensiva | Quarentena imediata do chunk suspeito |
| Brain chunk gera 3+ respostas ruins | Desativar chunk e notificar curadoria |

---

## 4. Requisitos Tecnicos

### 4.1 Paginas do Portal (novas)

| Rota | Descricao | Plano minimo |
|------|-----------|--------------|
| `/conversations` | Historico de conversas | Basic |
| `/conversations/[id]` | Detalhe de conversa (modal ou pagina) | Basic |
| `/brain/upload` | Upload de conteudo para o Brain | Pro |
| `/brain/knowledge` | Visualizacao da base de conhecimento | Premium |
| `/zenya/personalidade` | Ajuste de tom e tracos | Pro |
| `/zenya/horario` | Horario de funcionamento | Pro |
| `/zenya/sandbox` | Chat de teste | Premium |
| `/zenya/saudacoes` | Saudacoes por horario | Premium |
| `/zenya/restricoes` | Blocklist | Premium |

### 4.2 Endpoints de API (novos)

```
GET  /api/conversations              — lista paginada, filtros por query params
GET  /api/conversations/[id]         — detalhe com mensagens
GET  /api/conversations/export       — CSV do periodo

POST /api/brain/upload               — criar chunk pendente
GET  /api/brain/my-uploads           — uploads do cliente com status
GET  /api/brain/knowledge            — chunks aprovados do cliente

GET  /api/zenya/personality           — config atual de tom e tracos
POST /api/zenya/personality/request   — solicitar mudanca de tom
GET  /api/zenya/personality/preview   — preview com parametros novos

GET  /api/zenya/schedule              — horario atual
PUT  /api/zenya/schedule              — atualizar horario
GET  /api/zenya/greetings             — saudacoes por faixa
PUT  /api/zenya/greetings             — atualizar saudacoes

POST /api/zenya/sandbox/message       — enviar mensagem no sandbox
GET  /api/zenya/sandbox/history       — historico da sessao sandbox
POST /api/zenya/sandbox/feedback      — feedback em resposta
POST /api/zenya/sandbox/reset         — resetar sessao

GET  /api/zenya/blocklist             — lista atual
PUT  /api/zenya/blocklist             — atualizar lista
```

### 4.3 Alteracoes de Schema Supabase

#### Novas tabelas

```sql
-- Solicitacoes de mudanca de tom/personalidade
CREATE TABLE zenya_change_requests (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  client_id     UUID NOT NULL REFERENCES clients(id),
  request_type  TEXT NOT NULL,  -- 'tone', 'traits', 'soul_prompt'
  current_value JSONB,
  requested_value JSONB,
  status        TEXT DEFAULT 'pending',  -- pending, approved, rejected, rolled_back
  reviewer_note TEXT,
  reviewed_at   TIMESTAMPTZ,
  applied_at    TIMESTAMPTZ,
  rolled_back_at TIMESTAMPTZ,
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- Versoes do soul_prompt para rollback
CREATE TABLE soul_prompt_versions (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  client_id     UUID NOT NULL REFERENCES clients(id),
  soul_prompt   TEXT NOT NULL,
  version       INTEGER NOT NULL,
  change_source TEXT,  -- 'manual', 'tone_request', 'auto_rollback'
  active        BOOLEAN DEFAULT false,
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- Horario de funcionamento por cliente
CREATE TABLE zenya_schedule (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  client_id     UUID NOT NULL REFERENCES clients(id) UNIQUE,
  schedule      JSONB NOT NULL,  -- {"mon": {"open": "08:00", "close": "18:00"}, ...}
  off_hours_message TEXT,
  off_hours_behavior TEXT DEFAULT 'inform',  -- inform, collect, always_on
  holidays      JSONB,  -- [{"date": "2026-05-10", "message": "..."}]
  updated_at    TIMESTAMPTZ DEFAULT now()
);

-- Saudacoes personalizadas
CREATE TABLE zenya_greetings (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  client_id     UUID NOT NULL REFERENCES clients(id) UNIQUE,
  morning       TEXT,  -- 6h-12h
  afternoon     TEXT,  -- 12h-18h
  evening       TEXT,  -- 18h-6h
  updated_at    TIMESTAMPTZ DEFAULT now()
);

-- Feedback do sandbox
CREATE TABLE sandbox_feedback (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  client_id     UUID NOT NULL REFERENCES clients(id),
  message_id    TEXT,
  feedback      TEXT NOT NULL,  -- 'positive', 'negative'
  zenya_response TEXT,
  user_message  TEXT,
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- Regras de tom por nicho
CREATE TABLE niche_tone_rules (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  niche           TEXT NOT NULL UNIQUE,
  min_formality   INTEGER DEFAULT 1,  -- 1-5 scale
  max_formality   INTEGER DEFAULT 5,
  blocked_traits  TEXT[],  -- tracos nao permitidos para o nicho
  suggested_traits TEXT[],
  created_at      TIMESTAMPTZ DEFAULT now()
);

-- Blocklist por cliente
CREATE TABLE zenya_blocklist (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  client_id     UUID NOT NULL REFERENCES clients(id) UNIQUE,
  blocked_words TEXT[],
  blocked_topics JSONB,  -- [{"topic": "diagnostico", "action": "escalate", "message": "..."}]
  status        TEXT DEFAULT 'pending',  -- pending, approved
  updated_at    TIMESTAMPTZ DEFAULT now()
);
```

#### Alteracoes em tabelas existentes

```sql
-- Adicionar campos em brain_chunks para rastreabilidade de uploads do cliente
ALTER TABLE brain_chunks ADD COLUMN IF NOT EXISTS uploaded_by TEXT;  -- 'client', 'sparkle', 'auto'
ALTER TABLE brain_chunks ADD COLUMN IF NOT EXISTS upload_source TEXT;  -- 'portal_upload', 'api_ingest', 'onboarding'

-- Adicionar flag de sandbox em zenya_conversations
ALTER TABLE zenya_conversations ADD COLUMN IF NOT EXISTS is_sandbox BOOLEAN DEFAULT false;

-- Adicionar campo de formality no character_state
ALTER TABLE character_state ADD COLUMN IF NOT EXISTS formality_level INTEGER DEFAULT 3;
ALTER TABLE character_state ADD COLUMN IF NOT EXISTS personality_traits TEXT[];
```

### 4.4 Integracoes com Sistemas Existentes

| Sistema | Integracao necessaria |
|---------|-----------------------|
| Brain Pipeline (Runtime) | Receber chunks via API com `uploaded_by = 'client'`, respeitar limite e validacoes |
| Character State | Ler/gravar formality_level e personality_traits |
| Soul Prompt Generator (Haiku) | Gerar novo prompt a partir de tone+traits solicitados |
| Zenya Router (Runtime) | Consultar `zenya_schedule` antes de processar mensagem |
| Zenya Router (Runtime) | Consultar `zenya_blocklist` antes de enviar resposta |
| Curadoria (Mission Control) | Exibir `zenya_change_requests` pendentes para aprovacao |
| Metricas (Quality Monitor) | Monitorar satisfacao pos-mudanca para trigger de auto-rollback |

---

## 5. Caminho de Migracao

Transicao gradual dos clientes existentes, minimizando risco:

### Fase 1 — Dashboard Read-Only (2-3 semanas)

**Escopo:** Metricas + historico de conversas (P0)

**O que muda para o cliente:**
- Acessa o portal e ve metricas detalhadas
- Pode navegar pelo historico de conversas
- Pode exportar dados

**O que muda para a Sparkle:**
- Nada. E apenas leitura. Zero risco.

**Criterio de go/no-go:** 3 clientes usando o dashboard por 1 semana sem bugs criticos.

**Clientes alvo:** Todos os clientes Zenya ativos (Basic, Pro, Premium).

### Fase 2 — Brain Training (2-3 semanas)

**Escopo:** Upload de conteudo + curadoria (P0)

**O que muda para o cliente:**
- Pode enviar FAQs, informacoes de produto, regras de negocio
- Ve status dos uploads (pendente/aprovado/rejeitado)

**O que muda para a Sparkle:**
- Fila de curadoria agora recebe uploads de clientes alem dos auto-ingest
- Precisa revisar uploads de cliente em ate 24h uteis (SLA)

**Criterio de go/no-go:** 5 uploads aprovados por 2 clientes diferentes sem problemas de qualidade.

**Clientes alvo:** Plano Pro e Premium.

### Fase 3 — Personalidade + Horario (3-4 semanas)

**Escopo:** Ajuste de tom + horario de funcionamento (P1)

**O que muda para o cliente:**
- Pode solicitar mudanca de tom (com preview)
- Pode configurar horario de funcionamento

**O que muda para a Sparkle:**
- Revisa solicitacoes de mudanca de tom
- Monitor de qualidade pos-mudanca ativo

**Criterio de go/no-go:** Auto-rollback testado e funcionando. Nenhuma queda de satisfacao > 5% em pilotos.

**Clientes alvo:** Plano Pro e Premium (exceto clientes novos com menos de 30 dias).

### Fase 4 — Self-Serve Completo (4-6 semanas)

**Escopo:** Base de conhecimento + sandbox + saudacoes + blocklist (P2-P3)

**O que muda para o cliente:**
- Painel completo com todas as funcionalidades

**O que muda para a Sparkle:**
- Operacao passa a ser monitoramento ativo em vez de execucao manual
- Sparkle como guardia de qualidade, nao como executor

**Criterio de go/no-go:** Metricas de satisfacao estaveis por 2 semanas com Fases 1-3 ativas.

**Clientes alvo:** Plano Premium.

---

## 6. Impacto em Precificacao

### Tiers atuais vs. novas funcionalidades

| Funcionalidade | Basic (R$297) | Pro (R$650) | Premium (R$897+) |
|----------------|:---:|:---:|:---:|
| Dashboard de metricas | SIM | SIM | SIM |
| Historico de conversas | SIM | SIM | SIM |
| Exportacao CSV | -- | SIM | SIM |
| Upload de conteudo (Brain training) | -- | SIM | SIM |
| Ajuste de tom (slider + tracos) | -- | SIM | SIM |
| Horario de funcionamento | -- | SIM | SIM |
| Visualizacao da base de conhecimento | -- | -- | SIM |
| Sandbox (chat de teste) | -- | -- | SIM |
| Saudacoes personalizadas | -- | -- | SIM |
| Blocklist de palavras/topicos | -- | -- | SIM |
| SLA de curadoria | 48h | 24h | 12h |

### Logica de upgrade

- **Basic -> Pro**: "Voce sabe que a Zenya resolveu 87% das conversas no mes? Com o plano Pro, voce pode treinar ela com suas proprias FAQs e ajustar o tom. Veja o preview."
- **Pro -> Premium**: "Seus clientes amam a Zenya! Com o plano Premium, voce pode testar novas respostas no sandbox antes de ativar e ver exatamente o que ela sabe."

### Impacto financeiro estimado

- **Hipotese conservadora**: 30% dos clientes Basic fazem upgrade para Pro (+R$353/cliente)
- **Hipotese conservadora**: 20% dos clientes Pro fazem upgrade para Premium (+R$247/cliente)
- **Reducao de churn**: dashboard com metricas visiveis reduz churn estimado em 15-20% (baseado em benchmarks SaaS B2B PME)

---

## 7. Metricas de Sucesso

| Metrica | Meta | Como medir |
|---------|------|------------|
| Adocao do painel | 60% dos clientes acessam pelo menos 1x/semana | Login analytics |
| Reducao de tickets | -50% de solicitacoes operacionais para Mauro | Contagem manual (1o mes) |
| Uploads de Brain | 5+ uploads/mes por cliente Pro/Premium | `brain_chunks WHERE uploaded_by = 'client'` |
| Upgrade rate | 20% de upgrades em 90 dias | Tracking de mudanca de plano |
| Satisfacao pos-self-serve | Sem queda (manter > 80%) | `zenya_conversations.sentiment` |
| Tempo medio de curadoria | < 24h para Pro, < 12h para Premium | `brain_chunks.curated_at - created_at` |

---

## 8. Riscos e Mitigacoes

| Risco | Impacto | Mitigacao |
|-------|---------|-----------|
| Cliente treina Brain com conteudo ruim | Zenya responde errado, cliente final insatisfeito | Curadoria obrigatoria + auto-rollback |
| Cliente muda tom para algo inadequado | Experiencia do cliente final piora | Limites por nicho + aprovacao obrigatoria + rollback automatico |
| Sobrecarga de curadoria | Sparkle nao consegue revisar a tempo | Auto-aprovacao com feature flag para conteudo de baixo risco (FAQ com alta confidence) |
| Cliente nao usa o painel | Investimento em desenvolvimento sem retorno | Fase 1 e read-only (baixo custo), gamificacao ja existe para engajamento |
| Dados sensiveis expostos | Telefone de cliente final visivel | Mascaramento obrigatorio (ultimos 4 digitos) |

---

## 9. Dependencias

| Dependencia | Status | Bloqueio |
|-------------|--------|----------|
| Portal Next.js funcional | EXISTE | Nenhum |
| Brain pipeline com curadoria | EXISTE | Nenhum |
| Character state no Supabase | EXISTE | Nenhum |
| Client DNA extraction | EXISTE | Nenhum |
| Tabela zenya_conversations | EXISTE | Nenhum |
| Soul prompt generation (Haiku) | EXISTE | Nenhum |
| Zenya router no Runtime | EXISTE | Integrar consulta de schedule e blocklist |
| Quality monitor (auto-rollback) | NAO EXISTE | Precisa ser construido antes da Fase 3 |
| Feature flags no portal | NAO EXISTE | Precisa ser construido para controlar acesso por plano |

---

## 10. Proximos Passos

1. **@architect (Aria)**: Revisar schema SQL e propor ajustes arquiteturais
2. **@dev**: Implementar Fase 1 (dashboard read-only) como primeiro deliverable
3. **@qa**: Definir test plan para cada fase com edge cases
4. **@po**: Validar priorizacao e criterios de aceitacao
5. **Mauro**: Aprovar tiers de precificacao e strategy de upgrade

---

*Documento gerado por @pm (Morgan) | Sparkle AIOX | B4-03*
