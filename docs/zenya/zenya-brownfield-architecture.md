# Zenya — Documento de Arquitetura Atual (Brownfield)

> Estado real do sistema em Março/2026. Base de referência para evolução com agentes AIOS.

## Visão Geral

Zenya é uma secretária virtual de IA que opera via WhatsApp. Ela responde mensagens, gerencia agenda, processa cobranças, faz handoff humano e envia notificações — de forma autônoma, sem intervenção do operador no dia a dia.

Cada cliente recebe sua própria instância da Zenya, configurada para o nicho específico.

---

## Stack Tecnológica

| Componente | Tecnologia | Função |
|---|---|---|
| Hosting | Coolify (Docker) | Orquestra todos os serviços em VPS |
| Motor de automação | n8n | Executa todos os workflows |
| Gestão de conversas | Chatwoot | CRM de mensagens, caixas de entrada por cliente |
| Canal WhatsApp | Z-API | Conexão estável com WhatsApp (pago por instância) |
| Banco de dados | PostgreSQL | Armazenamento de dados dos fluxos |
| Agenda | Google Calendar | Agendamentos e lembretes |
| Arquivos | Google Drive | Envio de documentos para clientes |
| Cobranças | Asaas | Geração de cobranças (opcional por cliente) |
| Voz (WhatsApp/Tel) | Retell | Ligações telefônicas e de WhatsApp (não ativo — custo) |

---

## Fluxos Existentes (13 workflows n8n)

### Core
| # | Workflow | Status | Descrição |
|---|---|---|---|
| 00 | Configurações | Ativo | Variáveis globais do sistema |
| 01 | Secretária v3 | Ativo | Fluxo principal — recebe mensagem, processa, responde |
| 08 | Agente Assistente Interno | Ativo | Suporte interno ao fluxo principal |

### Integrações
| # | Workflow | Status | Descrição |
|---|---|---|---|
| 02 | Google Drive | Opcional | Baixa e envia arquivos para o cliente |
| 03 | Google Calendar — Buscar | Opcional | Consulta janelas disponíveis |
| 04 | Google Calendar — Criar | Opcional | Cria evento de agendamento |
| 04.1 | Atualizar agendamento | Opcional | Edita evento existente |
| 06 | Asaas | Opcional | Gera cobranças e links de pagamento |
| 12 | Gestão de ligações | Inativo | Retell — não configurado por custo |

### Automações de suporte
| # | Workflow | Status | Descrição |
|---|---|---|---|
| 05 | Escalar humano | Ativo | Transfere conversa para atendente humano |
| 05.1 | Escalar humano multi-alerta | Ativo | Envia notificação em outro WhatsApp |
| 07 | Quebrar e enviar mensagens | Ativo | Divide mensagens longas antes de enviar |
| 07.1 | Quebrar mensagens (ZAPI) | Ativo | Versão específica para Z-API |
| 09 | Desmarcar agendamento | Opcional | Cancela evento + envia alerta |
| 10 | Buscar ou criar contato | Ativo | Gerencia contatos no Chatwoot |
| 11 | Lembretes de agendamento | Opcional | Dispara lembretes antes do horário |
| 13 | Recuperação de leads | Opcional | Reengaja leads que não responderam |
| Retell | Secretária v3 voz | Inativo | Fluxo de voz — não configurado |

---

## Fluxo de Atendimento (do ponto de vista do cliente final)

```
Cliente envia mensagem (texto ou áudio)
        ↓
Z-API recebe e repassa ao Chatwoot
        ↓
n8n detecta nova mensagem no fluxo principal (01)
        ↓
Zenya processa com IA (system prompt do cliente)
        ↓
Decide ação:
  ├── Responder → quebra a mensagem (07) → envia pelo Z-API
  ├── Agendar → busca janelas (03) → cria evento (04)
  ├── Cobrar → gera cobrança no Asaas (06)
  ├── Enviar arquivo → busca no Drive (02) → envia
  ├── Escalar humano → (05) → notifica operador (05.1)
  └── Detecta humano respondendo → para de interagir
        ↓
Resposta chega ao cliente via WhatsApp
```

**Formato de resposta:** Por padrão, espelha o formato recebido (texto→texto, áudio→áudio). Configurável via instrução no system prompt.

---

## Processo de Onboarding de Novo Cliente

### O que o cliente precisa fornecer
- Acesso ao Google Calendar (para clientes com agenda)
- Credenciais do Asaas (para clientes com cobrança)
- Informações do negócio para o system prompt (nicho, serviços, tom de voz, horários)

### Passos de configuração (1-2 horas na prática)
1. Duplicar pasta de workflows no n8n
2. Remover workflows não utilizados (ex: Asaas, Calendar, Retell)
3. Criar nova instância na Z-API
4. Criar nova caixa de entrada no Chatwoot vinculada ao novo fluxo
5. Alterar system prompt da Zenya para o nicho do cliente
6. Alterar webhooks para apontar para os novos fluxos
7. Testar fluxo completo

**Prazo contratual:** 15 dias (buffer de segurança — entrega real em 1-2h)

---

## Capacidades por Nicho

### Nativo (funciona em qualquer cliente)
- Atendimento via texto e áudio
- Handoff humano com notificação
- Parar de responder quando humano assume
- Envio de arquivos via Google Drive

### Configurável (ativar por cliente)
- Agendamento via Google Calendar
- Cobranças via Asaas
- Lembretes de agendamento
- Recuperação de leads

### Requer desenvolvimento adicional (por nicho)
- Rastreio de transportadora (ecommerce)
- Consulta de imóveis (imobiliária)
- Integração com app de agendamento terceiro (ex: Doctoralia, Calendly)
- Integração com plataforma de ecommerce (ex: Loja Integrada, Shopify)

### Não ativo (custo/tempo)
- Ligações telefônicas via Retell
- Chamadas de voz WhatsApp via Retell

---

## Limitações e Dívidas Técnicas

### Arquitetura atual
- **Modelo clone por cliente:** Cada cliente tem cópia independente dos workflows. Funciona até ~6 clientes. Acima disso, manutenção vira gargalo — uma correção precisa ser aplicada em cada instância manualmente.
- **Sem versionamento:** Não há controle de qual versão da Zenya cada cliente está usando.

### Dependências de custo
- **Z-API:** Custo por instância. Inviável para demo ou clientes de ticket muito baixo.
- **Retell:** Custo por uso — funcionalidade de voz pausada.

### Conhecimento técnico
- Proprietário consegue alterar: system prompts, webhooks, ativar/desativar workflows, variáveis simples.
- Requer apoio dev: novos fluxos complexos, integrações com autenticação OAuth, lógica condicional avançada.

---

## Modo Demo (Prospecção)

Simulação conectada ao WhatsApp próprio do Mauro. System prompt alterado dinamicamente conforme o nicho do lead. Não possui instância dedicada — reutiliza o fluxo existente.

**Gap identificado:** Não existe uma instância Zenya "vitrine" completa com todas as capacidades ativas para demonstrar o produto em sua versão full.

---

## Próximas Evoluções Mapeadas

| Evolução | Impacto | Requer |
|---|---|---|
| Arquitetura multi-tenant (1 fluxo, N clientes via config) | Alto — escala ilimitada | @architect + @dev |
| Interface visual própria (eliminar Chatwoot para clientes simples) | Médio — reduz dependência | @architect + @dev |
| Instância Zenya vitrine (versão full para demos) | Alto — acelera vendas | Configuração + custo Z-API |
| Ativar Retell (voz) | Médio — diferencial competitivo | Custo + @dev |
| Integrações por nicho (rastreio, imóveis, agendadores) | Alto — amplia mercado | @dev por integração |

---

## Referências

- Workflows: `C:\Users\Mauro\Downloads\02. Mauro\Material Secretária v3\Material Secretária v3\WORKFLOWS\`
- Docker configs: `...\CONFIGURAÇÃO COOLIFY\`
- Schema PostgreSQL: `...\ Configuração Base de Dados Postgres.sql`
- Assets de exemplo (médico): `...\Arquivos da Secretária v3\`

---

*Documento gerado por @analyst (Atlas) em 2026-03-24. Base para work com @architect e @dev.*
