---
epic: EPIC-CLIENT-LIFECYCLE — Gestao do Ciclo de Vida do Cliente
story: LIFECYCLE-1.3
title: "Relatorio Semanal e Intervencao"
status: DONE
priority: Alta
executor: "@dev (implementacao)"
sprint: Client Lifecycle Wave 1
prd: docs/prd/domain-client-lifecycle-prd.md
architecture: docs/architecture/domain-client-lifecycle-architecture.md
squad: squads/client-lifecycle/
depends_on: [LIFECYCLE-1.2]
unblocks: []
estimated_effort: 6-8h de agente (@dev)
---

# Story 1.3 — Relatorio Semanal e Intervencao

**Sprint:** Client Lifecycle Wave 1
**Status:** `DONE`
**Sequência:** 3 de 4
**PRD:** `docs/prd/domain-client-lifecycle-prd.md`
**Architecture:** `docs/architecture/domain-client-lifecycle-architecture.md`
**Squad:** `squads/client-lifecycle/`

---

## User Story

> Como gestor da Sparkle,
> quero receber relatorios semanais automaticos sobre cada cliente e que o sistema intervenha automaticamente quando detectar inatividade prolongada,
> para que nenhum cliente fique sem acompanhamento e sinais de churn sejam tratados antes que se tornem cancelamentos.

---

## Contexto Tecnico

**Por que agora:** O health score (Story 1.2) gera os dados, mas sem acao automatica sao apenas numeros. O relatorio semanal e o mecanismo de intervencao transformam dados em acao — comunicacao proativa com o gestor e com o cliente.

**Dependencia:** Story 1.2 (health score engine deve estar funcional)

**Estado atual:**
- Nao existe geracao automatica de relatorios por cliente
- Nao ha deteccao de inatividade
- Z-API esta configurada e funcional para envio de mensagens WhatsApp

**Estado alvo:**
- `reporter.py`: gera e envia relatorio semanal por cliente via WhatsApp
- `intervention.py`: detecta inatividade 3+ semanas e age automaticamente
- 2 crons registrados

**Arquivos a criar em `runtime/client_health/`:**

```
runtime/client_health/
    reporter.py       # Geracao e envio de relatorio semanal
    intervention.py   # Deteccao de inatividade e reativacao
```

### reporter.py — Relatorio Semanal

**Logica:**
1. Consulta health score mais recente de cada cliente
2. Consulta metricas da semana (msgs processadas, tickets, etc.)
3. Formata relatorio em texto WhatsApp (max 500 chars)
4. Envia via Z-API para o numero do gestor (Mauro)

**Formato WhatsApp (max 500 chars):**
```
📊 *Relatorio Semanal — {nome_cliente}*

🟢 Health Score: {score}/100 ({classificacao})

📈 *Metricas da Semana:*
• Mensagens processadas: {volume}
• Pagamento: {status_pagamento}
• Ultimo acesso: {dias} dias atras

💡 *Destaque:* {highlight}

📋 *Recomendacao:* {recomendacao}
```

**Cron:** `client_report_weekly` — segunda-feira 09h BRT (1h apos recalculo do health score)

### intervention.py — Intervencao por Inatividade

**Logica:**
1. Consulta clientes com 3+ semanas sem atividade (0 msgs processadas por 21 dias)
2. Envia mensagem de reativacao para o WhatsApp DO CLIENTE (nao do gestor)
3. Se inatividade > 4 semanas: escala para Friday (notifica Mauro via Friday)
4. Registra intervencao no log

**Mensagem de reativacao (exemplo):**
```
Oi {nome}! 👋 Aqui e da Sparkle.

Notamos que a {nome_zenya} nao recebeu mensagens recentemente.
Precisa de algum ajuste? Estamos aqui pra ajudar! 💬

Responda "ajuda" e nosso time entra em contato.
```

**Escalacao para Friday:**
```json
POST /tasks
{
    "type": "friday_alert",
    "payload": {
        "alert": "client_inactive",
        "client_id": "...",
        "client_name": "...",
        "inactive_weeks": 4,
        "message": "Cliente {nome} esta inativo ha {semanas} semanas. Intervencao automatica ja enviada sem resposta."
    }
}
```

**Cron:** `intervention_check` — diariamente as 10h BRT

---

## Acceptance Criteria

- [ ] **AC1** — Arquivo `runtime/client_health/reporter.py` criado com funcao de geracao de relatorio
- [ ] **AC2** — Relatorio formatado para WhatsApp com max 500 caracteres, usando emojis como marcadores
- [ ] **AC3** — Relatorio inclui: health score, classificacao, metricas da semana, destaque e recomendacao
- [ ] **AC4** — Relatorio enviado via Z-API para numero do gestor
- [ ] **AC5** — Cron `client_report_weekly` registrado para segunda-feira 09h BRT
- [ ] **AC6** — Arquivo `runtime/client_health/intervention.py` criado com deteccao de inatividade
- [ ] **AC7** — Intervencao detecta clientes com 3+ semanas sem atividade (0 msgs em 21 dias)
- [ ] **AC8** — Mensagem de reativacao enviada via Z-API para o WhatsApp DO CLIENTE
- [ ] **AC9** — Escalacao para Friday ativada quando inatividade > 4 semanas (via POST /tasks com type friday_alert)
- [ ] **AC10** — Cron `intervention_check` registrado para execucao diaria as 10h BRT
- [ ] **AC11** — Todas as intervencoes sao logadas (quem, quando, tipo, resultado)

---

## Integration Verifications

- [ ] Reporter gera relatorio valido para cliente com health score calculado
- [ ] Reporter lida gracefully com cliente sem health score (pula ou gera relatorio parcial)
- [ ] Z-API recebe chamada correta para envio de mensagem (formato, numero, conteudo)
- [ ] Intervention detecta corretamente clientes inativos vs ativos
- [ ] Intervention nao envia mensagem duplicada no mesmo dia para o mesmo cliente
- [ ] Escalacao para Friday cria task com payload correto
- [ ] Ambos os crons aparecem na lista de crons registrados
- [ ] Relatorio nao excede 500 caracteres em nenhum cenario

---

## File List

| Arquivo | Acao |
|---------|------|
| `runtime/client_health/reporter.py` | CRIAR |
| `runtime/client_health/intervention.py` | CRIAR |
| `main.py` | MODIFICAR (registrar 2 crons) |
