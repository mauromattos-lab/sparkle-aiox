# Design Spec — Client Lifecycle Wave 1 (Fundacao)

**Sprint:** Client Lifecycle Wave 1
**Domain:** client-lifecycle
**PRD:** `docs/prd/domain-client-lifecycle-prd.md`
**Architecture:** `docs/architecture/domain-client-lifecycle-architecture.md`
**Stories:** 4 (LIFECYCLE-1.1 a 1.4)

---

## Objetivo

Construir a fundacao do dominio Client Lifecycle: modelo de dados, health score engine, relatorios automaticos, deteccao de inatividade e rastreamento de milestones/TTV. Ao final da Wave 1, a Sparkle passa de gestao reativa para gestao proativa de clientes.

---

## Grafo de Dependencias

```
LIFECYCLE-1.1 (Migration / Modelo de Dados)
    ├──> LIFECYCLE-1.2 (Health Score Engine)
    │        └──> LIFECYCLE-1.3 (Relatorio + Intervencao)
    └──> LIFECYCLE-1.4 (Milestones + TTV)
```

**Paralelismo possivel:** Apos 1.1 concluida, 1.2 e 1.4 podem rodar em paralelo. 1.3 depende de 1.2.

---

## Estrutura de Arquivos (visao final Wave 1)

```
sparkle-runtime/
├── migrations/
│   └── 015_client_lifecycle_tables.sql    # Story 1.1
├── runtime/
│   ├── client_health/
│   │   ├── __init__.py                     # Story 1.2
│   │   ├── router.py                       # Story 1.2
│   │   ├── calculator.py                   # Story 1.2
│   │   ├── reporter.py                     # Story 1.3
│   │   └── intervention.py                 # Story 1.3
│   └── onboarding/
│       ├── service.py                      # Story 1.4 (modificar)
│       └── router.py                       # Story 1.4 (modificar)
└── main.py                                 # Stories 1.2, 1.3 (registrar router + crons)
```

---

## Modelo de Dados

### Tabelas novas (Migration 015)

| Tabela | Proposito | FK |
|--------|-----------|----|
| `client_health` | Health score calculado periodicamente | zenya_clients.id |
| `client_milestones` | Marcos da jornada do cliente | zenya_clients.id |
| `upsell_opportunities` | Oportunidades de upsell detectadas | zenya_clients.id |
| `client_nps` | Net Promoter Score coletado | zenya_clients.id |

Todas com RLS habilitado e indexes em colunas de consulta frequente.

### Diagrama ER simplificado

```
zenya_clients (1) ──> (*) client_health
zenya_clients (1) ──> (*) client_milestones
zenya_clients (1) ──> (*) upsell_opportunities
zenya_clients (1) ──> (*) client_nps
```

---

## Health Score Engine — Design Tecnico

### Formula

```
score = (volume_score * 0.30) +
        (payment_score * 0.25) +
        (access_score * 0.20) +
        (support_score * 0.15) +
        (checkin_score * 0.10)
```

Cada sinal individual e normalizado para 0-100 antes da ponderacao.

### Sinais — Calculo Individual

| Sinal | Input | Score 100 | Score 0 | Fonte |
|-------|-------|-----------|---------|-------|
| volume | Msgs processadas 7d | >= media historica do cliente | 0 msgs | zenya_messages / logs |
| payment | Status pagamento | Em dia | Inadimplente 30d+ | zenya_clients.payment_status |
| access | Ultimo acesso/interacao | Ultimos 3 dias | 30d+ sem acesso | zenya_clients ou logs |
| support | Tickets abertos | 0 tickets | 3+ tickets | support_tickets (se existir) |
| checkin | Resposta ao checkin | Respondeu ultimo | Ignorou 2+ | client_checkins (se existir) |

**Nota para @dev:** Sinais cujas tabelas-fonte ainda nao existem (support_tickets, client_checkins) devem retornar score default de 50 (neutro). Implementar com interface que permita adicionar novas fontes sem refatorar o calculator.

### Classificacao

```python
def classify(score: int) -> str:
    if score >= 80: return "healthy"
    if score >= 60: return "attention"
    if score >= 40: return "risk"
    return "critical"
```

### Endpoints

| Metodo | Path | Descricao | Response |
|--------|------|-----------|----------|
| GET | `/health/{client_id}` | Score atual | `{score, classification, signals, calculated_at}` |
| GET | `/health/all` | Todos os clientes | `[{client_id, client_name, score, classification}]` |
| POST | `/health/recalculate` | Forca recalculo | `{recalculated: N, summary: {healthy: X, attention: Y, ...}}` |
| GET | `/health/{client_id}/history` | Historico | `{items: [{score, classification, calculated_at}], total}` |

### Cron

- Nome: `health_score_weekly`
- Schedule: `0 11 * * 1` (08h BRT = 11h UTC, segunda-feira)
- Acao: recalcula score de todos os clientes ativos e persiste em `client_health`

---

## Relatorio Semanal — Design Tecnico

### Fluxo

```
Cron (seg 09h BRT)
  └──> Para cada cliente ativo:
       ├── Consulta health score mais recente
       ├── Consulta metricas da semana
       ├── Formata texto (max 500 chars)
       └── Envia via Z-API para gestor
```

### Formato

Template com emojis como marcadores visuais. Max 500 chars para caber em uma tela de WhatsApp sem scroll.

### Intervencao por Inatividade

```
Cron (diario 10h BRT)
  └──> Consulta clientes com 0 msgs nos ultimos 21 dias
       ├── Se 21-28 dias: envia msg reativacao para o CLIENTE
       └── Se > 28 dias: escala para Friday (alerta para Mauro)
```

**Dedup:** nao enviar mais de 1 mensagem de reativacao por semana para o mesmo cliente.

---

## Milestones e TTV — Design Tecnico

### Milestones

| Tipo | Trigger automatico | Acao apos registro |
|------|--------------------|--------------------|
| `zenya_active` | Zenya responde 1a msg real | Envia parabens ao gestor |
| `first_real_message` | 1a msg de cliente real | Calcula TTV, envia parabens |
| `first_week_report` | 7d apos zenya_active, volume > 0 | Nenhuma acao extra |
| `aha_moment_30d` | 30d apos zenya_active, health >= 60 | Nenhuma acao extra |

### TTV

```python
ttv_days = (first_real_message.achieved_at - client.contract_date).days
```

Armazenado no campo `ttv_days` do milestone `first_real_message`.

### Idempotencia

`track_milestone()` deve ser idempotente: se o milestone ja existe (UNIQUE constraint), nao insere duplicado e nao envia mensagem novamente. Usar `ON CONFLICT DO NOTHING` ou catch de IntegrityError.

---

## Integracoes Externas

| Sistema | Uso | Modulo |
|---------|-----|--------|
| Z-API | Envio de relatorios e mensagens de reativacao/parabens | reporter.py, intervention.py, service.py |
| Supabase | Persistencia de health scores, milestones, queries | Todos os modulos |
| Friday (via Runtime tasks) | Escalacao de alertas de inatividade | intervention.py |

---

## Riscos e Mitigacoes

| Risco | Mitigacao |
|-------|-----------|
| Tabelas-fonte de sinais nao existem ainda | Sinais sem fonte retornam 50 (neutro), interface extensivel |
| Z-API rate limits | Enviar relatorios com delay entre mensagens (1s entre cada) |
| Volume de dados historico insuficiente | Calcular media historica com fallback para media global |
| Cron falha silenciosamente | Registrar execucao em `cron_executions` (tabela existente) |

---

## Criterios de Conclusao da Wave 1

Wave 1 esta concluida quando:

1. Migration 015 aplicada e todas as 4 tabelas existem no Supabase
2. Health score calculavel para qualquer cliente ativo
3. Relatorio semanal gerado e enviado automaticamente
4. Intervencao por inatividade funcional com escalacao
5. Milestones rastreados e TTV calculado
6. Todos os crons registrados e executando
7. QA validou todos os ACs de todas as 4 stories
