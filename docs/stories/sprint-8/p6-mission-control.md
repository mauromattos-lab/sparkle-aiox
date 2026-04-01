# [P6] Mission Control — Visibilidade de Agentes em Tempo Real

**Sprint:** 8 | **Status:** AGUARDANDO_QA | **Responsável:** @dev
**Prioridade:** P6 — MÉDIA | **Estimativa:** M (4–6h @dev + 1–2h @qa)

---

## User Story

Como Mauro, quero abrir o Portal no celular e ver em tempo real quais agentes estão ativos, o que cada um está fazendo e quais itens estão bloqueados, para que eu não precise perguntar à Friday "onde estamos?" e o sistema me dê essa visibilidade proativamente.

---

## Contexto Técnico

**Problema atual:** O sistema opera, entrega e registra — mas é invisível para Mauro. Ele precisa abrir o Supabase Studio ou perguntar para a Friday para saber o que está acontecendo. Isso viola a Lei 11 (visibilidade e controle do sistema).

**Infraestrutura disponível (zero nova infra):**
- Tabela `agent_work_items` no Supabase — criada em 2026-04-01
- Supabase Realtime disponível (anon key em `NEXT_PUBLIC_SUPABASE_ANON_KEY` no portal)
- Portal Next.js ativo na porta 3000 (`/opt/sparkle-portal/portal/`)
- `portal/lib/supabase.ts` com client Supabase já configurado

**O que construir:**
- Rota `/mission-control` no portal Next.js
- Hook `useAgentWorkItems` com subscription Supabase Realtime + fallback polling 30s
- Componente `AgentCard` com 5 estados visuais distintos
- Auto-priority sorting: error > active > blocked > idle > done

**Mapeamento de status banco → card:**
| Banco | AgentCard |
|-------|-----------|
| `pendente` | idle (cinza) |
| `em_execucao` | active (roxo, pulse) |
| `aguardando_qa` / `blocked` | blocked (amarelo) |
| `aprovado_qa` / `funcional` | done (verde) |
| `erro` | error (vermelho, glow) |

**Arquivos a criar:**
- `portal/app/mission-control/page.tsx`
- `portal/hooks/useAgentWorkItems.ts`
- `portal/components/AgentCard.tsx`

**Arquivos a modificar:**
- `portal/app/layout.tsx` — adicionar link "Mission Control" na nav

**Pré-condição:** `agent_work_items` com replication habilitada para Supabase Realtime. Se não estiver: `ALTER PUBLICATION supabase_realtime ADD TABLE agent_work_items;`

---

## Acceptance Criteria

- [ ] AC-1: Rota `/mission-control` carrega em < 2 segundos (first contentful paint)
- [ ] AC-2: `AgentCard` atualiza status em < 1 segundo após UPDATE em `agent_work_items` (validar com INSERT manual no Supabase Studio durante QA)
- [ ] AC-3: 5 estados visuais são distintos e identificáveis sem precisar ler a legenda (cores + glow validados por Mauro)
- [ ] AC-4: Auto-priority sorting correto: agentes com `error` aparecem primeiro, depois `active`, `blocked`, `idle`, `done`
- [ ] AC-5: Estado vazio (zero work items nas últimas 24h) exibe mensagem "Todos os agentes em standby" — não tela em branco
- [ ] AC-6: Mobile 390px: cards legíveis, sem overflow horizontal, `min-h-[140px]` por card
- [ ] AC-7: Sem polling quando WebSocket conectado — verificar via Network tab que não há requests a cada Ns
- [ ] AC-8: Fallback para polling a cada 30s quando WebSocket desconecta — validar desconectando rede temporariamente

---

## Definition of Done

- [ ] Testes: renderização dos 5 estados do `AgentCard` com dados mockados (sem erro de TypeScript/prop)
- [ ] QA aprovou — SMOKE-06 (portal carrega sem erro JS no console) passou
- [ ] QA aprovou — SMOKE-11 (NOVO): `/mission-control` carrega E WebSocket conecta (`SUBSCRIBED` aparece no log do browser)
- [ ] Mauro abriu o Portal no celular (390px) e vê agentes em tempo real — cronometrado < 5s
- [ ] `work_log.md` atualizado com status FUNCIONAL
- [ ] Lei 11 (visibilidade do sistema) atualizada para ✅ no `sparkle-system-map.md`

---

## Tarefas Técnicas

- [x] T1: Verificar via `mcp__supabase__execute_sql` se `agent_work_items` está em `pg_publication_tables` para `supabase_realtime`. Confirmado: ja estava habilitado — nenhuma migration necessaria.
- [x] T2: Criar `portal/hooks/useAgentWorkItems.ts` — subscription Realtime + carga inicial + fallback polling 30s
- [x] T3: Criar `portal/components/AgentCard.tsx` — 5 estados com cores, glow e animacao pulse para `active`
- [x] T4: Criar `portal/app/mission-control/page.tsx` — PhaseTimeline, ActivePhaseSection, AgentGrid, Accordion fases completas, empty/loading/error states, StatusLegend. SVG inline (zero emoji).
- [x] T5: layout.tsx sem nav existente — link NAO adicionado conforme decisao UX spec secao 10
- [x] T6: Seed inserido via MCP Supabase: 9 rows cobrindo todos os 5 estados visuais (em_execucao, aguardando_qa, funcional, pendente, erro)
- [x] T7: Deploy via CI/CD — push para main aciona .github/workflows/deploy-portal.yml automaticamente
- [ ] T8: Teste mobile — validar por @qa em 390px via DevTools

---

## Dependências

**Pré-condição técnica:**
- `agent_work_items` existente e com dados (verificar via `mcp__supabase__execute_sql`: `SELECT COUNT(*) FROM agent_work_items`)
- Se tabela vazia: @dev insere rows de seed para QA validar todos os estados visuais
- DNS `portal.sparkleai.tech` apontando para o VPS (registro A — Mauro confirma via painel Hostinger)

**Paralela com:** P1, P2, P4 — zero dependência técnica entre elas.

**Esta story desbloqueia:** Gate V6 do @po (Mauro vê agentes no celular em < 5s).

---

## Notas para @dev

1. **Código completo** do hook, do componente e da página está em `docs/sprints/sprint-8-specs.md` seções 6.1, 6.2 e 6.3. Implementar a partir disso — sem reinventar.

2. **Tailwind é a stack CSS do portal.** Os glow effects usam `shadow-[...]` com valores arbitrários: `shadow-[0_0_20px_rgba(168,85,247,0.35)]` para active, `shadow-[0_0_24px_rgba(239,68,68,0.4)]` para error. Verificar que `tailwind.config.js` suporta valores arbitrários (geralmente sim por padrão).

3. **Realtime requer `supabase_realtime` publication ativa na tabela.** Verificar antes de começar — se não tiver, o subscription simplesmente não recebe eventos e a tela fica em modo polling sem indicar o problema. O AC-7 verifica isso.

4. **Fallback de polling (30s) é obrigatório** — AC-8 testa isso explicitamente. Implementar o `setInterval` no `useEffect` quando o status do channel for `CLOSED` ou `CHANNEL_ERROR`.

5. **Estado vazio é critério de aceite.** Não pode retornar tela em branco. Mensagem "Todos os agentes em standby" + subtítulo "Nenhum item registrado nas últimas 24h" conforme spec.

6. **Sem autenticação adicional para `/mission-control`.** Usa a sessão existente do portal — Mauro já está logado. Não criar nova rota de auth.

7. **Não criar controles de ação.** Mission Control é visualização apenas — não botões de iniciar/parar/reiniciar agentes. Isso é backlog.

8. **Se `agent_work_items` estiver vazia em produção:** inserir rows de seed para validar os estados visuais no QA:
   ```sql
   INSERT INTO agent_work_items (assigned_to, status, artifact_id, notes)
   VALUES
     ('@dev', 'em_execucao', 'S8-P6', 'Implementando Mission Control'),
     ('@qa', 'aguardando_qa', 'S8-P1', 'Aguardando review do brain isolation'),
     ('@pm', 'funcional', 'sprint-8-prds', 'PRDs entregues'),
     ('@devops', 'pendente', NULL, NULL);
   ```
