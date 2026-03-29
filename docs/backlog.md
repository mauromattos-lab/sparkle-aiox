# Sparkle — Backlog de Ideias e Demandas

> Qualquer ideia nova vai aqui primeiro. @po organiza e prioriza.
> Regra: ideia nova não vira ação imediata, vira registro.

---

## Ideias Capturadas

### [ZENYA] Kanban no Chatwoot — fazer.ai
- **Origem:** fazer.ai (Lucas Moreira) — produto brasileiro, Kanban embutido no Chatwoot
- **O que é:** Cards do funil = conversas WhatsApp. Drag-and-drop entre fases. Node n8n próprio.
- **Preço:** R$129,90/mês por instalação (não por cliente — custo fixo se multi-tenant)
- **Avaliado em:** 2026-03-27 — vídeo YT analisado (IBq5t6FUZH0)
- **Conclusão:** Complemento, não substitui Z-API nem IA. Resolve funil visual — clientes atuais não estão pedindo.
- **Candidato ideal quando chegar a hora:** Gabriela Consórcio (vive de pipeline de leads)
- **Risco:** Usa Baileys (risco ban WA) — manter Z-API para clientes com volume alto
- **Status:** Backlog baixa prioridade — reavaliar quando cliente pedir funil visual

### [ZENYA] Integração de busca de imóveis (nicho imobiliária)
- **Origem:** Ideia do Mauro — nicho com alta demanda
- **O que é:** Zenya consulta base de imóveis e responde com opções para o lead
- **Recurso:** Tem vídeo no YouTube mostrando o fluxo completo — trazer link quando for executar
- **Impacto:** Alto — abre nicho de imobiliárias
- **Status:** Backlog — executar quando aparecer lead imobiliária

### [ZENYA] Integração com plataformas de ecommerce (rastreio de pedidos)
- **Origem:** Cliente ecommerce atual pode precisar
- **O que é:** Zenya consulta status de pedido via API da transportadora/plataforma
- **Impacto:** Médio — necessário para escalar em ecommerce
- **Status:** Backlog

### [SPARKLE] Zenya como influencer no Instagram/TikTok
- **Origem:** Visão estratégica do Mauro
- **O que é:** Zenya como personagem AI influencer — prova técnica + canal de aquisição + IP
- **Stack em estudo:** RunPod + ComfyUI para geração realista
- **Impacto:** Alto — Layer 1.5 do império Sparkle
- **Status:** Backlog — executar após infraestrutura de vendas estar no ar

### [ZENYA] Interface visual própria (eliminar Chatwoot para clientes simples)
- **Origem:** Ideia do Mauro
- **O que é:** Dashboard simples para o cliente acompanhar atendimentos sem precisar do Chatwoot
- **Impacto:** Médio — reduz dependência de ferramenta externa
- **Status:** Backlog — Layer 2

### [SPARKLE] Gestor de Tráfego Pago com IA
- **Origem:** Referência de Alan Nicolas e Tiago Finch
- **O que é:** Agente que conecta via API (Meta Ads, Google Ads, TikTok Ads) — puxa performance, analisa, pausa campanhas ruins, aumenta budget das boas, gera relatório automático para o cliente
- **Impacto:** Alto — novo produto Sparkle + otimiza cliente de tráfego atual (R$1.500/mês)
- **Recursos:** Meta Ads API, Google Ads API, TikTok Ads API
- **Status:** Backlog

### [SPARKLE / INFRA] Onboarding padronizado de clientes
- **Origem:** Mauro — 2026-03-28
- **O que é:** Tabela `clients` no Supabase como single source of truth para todos os agentes e squads. Cada cliente cadastrado com: nome, nicho, localização, Instagram, WhatsApp, ad_account_id, chatwoot_inbox_id, zenya_workflow_id, status. Agentes consultam essa tabela por `client_id` sem precisar de contexto manual.
- **Conecta com:** auto-onboarding (agentes extraem contexto do cliente automaticamente), Friday (consulta clientes por voz), squads (recebem client_id e puxam tudo)
- **Impacto:** Alto — elimina retrabalho de passar contexto manualmente para cada agente/squad
- **Status:** Backlog — executar logo após entregas Confeitaria/Ensinaja/Gabriela

### [ZENYA / INFRA] Arquitetura de atualização multi-cliente
- **Origem:** Mauro — 2026-03-27
- **O que é:** Quando tivermos 10+ clientes Zenya e quisermos adicionar uma feature (ex: Kanban, rastreio, novo módulo), como propagamos para todos sem fazer cliente por cliente manualmente?
- **Questões a responder:** Subworkflow compartilhado vs. workflow por cliente? Template central com herança? Versionamento de workflows?
- **Impacto:** Alto — define escalabilidade da operação Zenya
- **Status:** Backlog — discutir quando chegarmos a 4-5 clientes ativos

---

## Como usar este backlog

1. Surgiu ideia → adiciona aqui com uma linha de contexto
2. Menciona para o @po na próxima sessão
3. @po prioriza e coloca no sprint quando for a hora
4. Nunca interrompe o sprint atual por ideia nova (a não ser que seja urgente)
