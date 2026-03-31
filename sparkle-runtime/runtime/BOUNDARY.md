# Fronteira n8n / Sparkle Runtime

## Responsabilidade do n8n
- Receber webhooks externos (Z-API, Meta Ads, Typeform, formulários)
- Executar workflows de clientes existentes (Zenyas em produção via n8n)
- Disparar tarefas simples de manutenção sem lógica de agente

## Responsabilidade do Runtime
- Tudo que envolve decisão de um agente Claude
- Qualquer coisa que precise de estado persistido entre execuções
- Qualquer coisa que precise de observabilidade (logs, métricas, debug)
- Friday, Brain, orquestração de QA, go-live gates

## Ponto de transição (único)
Webhook Z-API cai no n8n → n8n extrai payload mínimo (from, to, type, content) → POST para `POST /runtime/tasks` do Runtime. A partir daí o Runtime é dono. O n8n não acompanha o resultado. O Runtime notifica de volta via Z-API se necessário.

## Regras invioláveis
- Runtime nunca chama n8n diretamente
- n8n nunca lê tabelas do Runtime diretamente (usa endpoint REST se precisar de info)
- Clientes existentes: ficam em n8n até decisão explícita de migrar
- Clientes novos: nascem no Runtime
