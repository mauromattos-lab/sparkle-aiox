# Sparkle Sales Infrastructure v1 — Brownfield Enhancement PRD

| Campo | Valor |
|---|---|
| Versão | 1.0 |
| Data | 2026-03-24 |
| Autor | @pm (Morgan) |
| Status | Draft — aguarda aprovação |
| Épico | Sparkle Sales Infrastructure v1 |
| Horizonte | 30-45 dias |

---

## 1. Contexto e Objetivo

### Situação atual
Zenya é uma secretária virtual de IA operando via WhatsApp para PMEs. O produto funciona — 5 clientes ativos, MRR R$3.844/mês. Porém, a infraestrutura de vendas é inexistente: sem landing page, sem demo profissional, sem registro de leads. Resultado: 100 leads de um vídeo TikTok → 2 clientes fechados (2% de conversão).

### Problema central
O gargalo não é tráfego, é conversão. Leads chegam sem filtro, sem referência de preço, sem experiência de demo. O tempo do Mauro é desperdiçado em conversas que nunca vão fechar.

### Objetivo
Construir a infraestrutura mínima de vendas que eleva a conversão de 2% para 10-15% — sem construir produto novo, sem mudar o que está funcionando para clientes ativos.

### Fora do escopo (backlog)
- Zenya personagem/influencer (aguarda funil pronto)
- Arquitetura multi-tenant
- Interface visual própria
- Kanban no Chatwoot com IA
- Integrações por nicho (imóveis, rastreio)

---

## 2. Requisitos

### Funcionais
- **FR1:** Landing page pública com proposta de valor, para quem é, quanto custa e CTA para WhatsApp
- **FR2:** Instância Zenya vitrine com todas as capacidades ativas para uso em demos
- **FR3:** Automação de captura de leads (não planilha manual — fluxo que registra automaticamente)
- **FR4:** Checklist padronizado de onboarding documentado e operável sem dev

### Não-Funcionais
- **NFR1:** Tudo operável por Mauro sem ajuda de dev no dia a dia
- **NFR2:** Custo adicional máximo R$200/mês (uma Z-API para a vitrine)
- **NFR3:** Cada story entregue em no máximo 1 semana

### Compatibilidade
- **CR1:** Zero alterações nos workflows dos clientes ativos
- **CR2:** Usar stack existente (Coolify, n8n, Chatwoot) onde possível
- **CR3:** Vitrine roda isolada das instâncias de clientes reais

---

## 3. Stack Técnica

| Entrega | Tecnologia | Justificativa |
|---|---|---|
| Landing page | HTML/CSS simples ou builder (Carrd, etc.) | Rápido, mobile-first, sem infra nova |
| Zenya vitrine | n8n + Z-API + Chatwoot (stack existente) | Sem custo de aprendizado |
| Captura de leads | n8n + Google Sheets API | Automático, zero custo operacional |
| Checklist onboarding | Markdown no AIOS (docs/playbooks/) | Versionável, delegável |

---

## 4. Épico — Sparkle Sales Infrastructure v1

**Meta do épico:** Ter funil de vendas funcional com demo profissional, captura automática de leads e processo de onboarding documentado — em 30-45 dias.

**Critério de sucesso:** Taxa de conversão de leads saindo de 2% para mínimo 8% em 30 dias após go-live da landing page.

---

### Story 1.1 — Checklist de Onboarding Padronizado

**Como** Mauro (operador),
**Quero** um checklist documentado de todos os passos para configurar um cliente novo na Zenya,
**Para que** eu nunca dependa de memória, possa delegar no futuro e reduza o tempo de onboarding.

**Critérios de aceitação:**
1. Checklist cobre todos os passos do processo atual (Z-API → Chatwoot → n8n → system prompt)
2. Inclui quais workflows ativar/desativar por tipo de cliente (clínica, ecommerce, escola, etc.)
3. Inclui checklist de teste antes de entregar ao cliente
4. Documento salvo em `docs/playbooks/zenya-onboarding-checklist.md`
5. Testado nos 3 clientes sendo entregue esta semana

**Prioridade:** Alta — executar imediatamente (esta semana)
**Agente responsável:** @dev + @qa
**Estimativa:** 1-2 dias

---

### Story 1.2 — Automação de Captura de Leads

**Como** Mauro (fundador),
**Quero** que cada lead que chega (WhatsApp, TikTok, indicação) seja registrado automaticamente,
**Para que** eu nunca perca um contato e possa fazer follow-up sistemático.

**Critérios de aceitação:**
1. Fluxo n8n captura leads que entram pelo WhatsApp da Sparkle e registra em Google Sheets
2. Campos mínimos: nome, telefone, origem, data, status, próximo passo
3. Mauro consegue atualizar status sem abrir o n8n (direto na planilha)
4. Notificação no WhatsApp do Mauro a cada novo lead registrado
5. Documentação de como usar em `docs/playbooks/lead-tracking.md`

**Prioridade:** Alta
**Agente responsável:** @dev
**Estimativa:** 2-3 dias

---

### Story 1.3 — Zenya Vitrine (Demo Profissional)

**Como** Mauro (vendedor),
**Quero** uma instância Zenya com todas as capacidades ativas e persona profissional,
**Para que** eu possa demonstrar o produto completo para prospects sem impactar clientes ativos.

**Critérios de aceitação:**
1. Instância separada na Z-API conectada ao Chatwoot (caixa de entrada "Sparkle Demo")
2. System prompt genérico apresentando a Zenya como produto da Sparkle
3. Agenda, cobrança (Asaas sandbox), handoff humano e notificação todos funcionando
4. Áudio e texto ambos operacionais
5. Script de demo documentado em `docs/playbooks/demo-script.md` com roteiro de 5 minutos

**Prioridade:** Alta
**Agente responsável:** @dev + @devops
**Estimativa:** 3-4 dias

---

### Story 1.4 — Landing Page Sparkle/Zenya

**Como** prospect,
**Quero** entender o que é a Zenya, se é para mim e quanto custa antes de entrar em contato,
**Para que** eu chegue ao WhatsApp da Sparkle já qualificado e com expectativa alinhada.

**Critérios de aceitação:**
1. Página mobile-first com: proposta de valor, para quem é, o que faz, quanto custa (a partir de R$497/mês), CTA para WhatsApp
2. Inclui pelo menos 1 case ou depoimento (pode ser genérico inicialmente)
3. Carrega em menos de 3 segundos no celular
4. URL própria (domínio Sparkle ou subdomínio)
5. CTA do TikTok atualizado para apontar para a página

**Prioridade:** Média-alta
**Agente responsável:** @dev
**Estimativa:** 3-5 dias

---

### Story 1.5 — Atualização do Funil TikTok

**Como** Mauro (criador de conteúdo),
**Quero** que os leads do TikTok cheguem à landing page em vez de tentar me encontrar nos comentários,
**Para que** eu pare de perder leads que não veem minha resposta no DM.

**Critérios de aceitação:**
1. Bio do TikTok atualizada com link para landing page
2. Template de comentário padrão criado: "Acesse o link na bio para ver se faz sentido pro seu negócio"
3. Pinned comment nos vídeos existentes com maior engajamento atualizado
4. Documento com script de CTA para novos vídeos em `docs/playbooks/tiktok-cta-script.md`

**Prioridade:** Média — executar após Story 1.4
**Agente responsável:** @pm + Mauro
**Estimativa:** 1 dia

---

## 5. Roadmap Visual

```
Semana 1 (agora)
├── Story 1.1 — Checklist onboarding      ← enquanto entrega os 3 clientes
└── Story 1.2 — Captura automática leads

Semana 2
└── Story 1.3 — Zenya vitrine

Semana 3
├── Story 1.4 — Landing page
└── Story 1.5 — Funil TikTok

Semana 4+
└── Primeiros resultados de conversão → ajustes
    Backlog → próximo épico
```

---

## 6. Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Z-API da vitrine ser bloqueada | Baixa | Alto | Usar número dedicado, sem disparos |
| Landing page não converter | Média | Médio | Testar CTA antes de investir em tráfego pago |
| Onboarding dos 3 clientes atrasar | Baixa | Alto | Story 1.1 é prioridade desta semana |

---

## 7. Próximos Passos

1. **@sm** — Criar sprint da Semana 1 com Story 1.1 e 1.2
2. **@po** — Detalhar stories e criar tasks executáveis
3. **@dev** — Implementar Story 1.2 (automação de leads)
4. **Mauro** — Executar Story 1.1 durante entrega dos 3 clientes

---

*PRD criado por @pm (Morgan) em 2026-03-24. Aprovação do Mauro necessária para iniciar execução.*
