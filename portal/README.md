# Portal do Cliente — Sparkle AI

Aplicacao web Next.js 14 para clientes Sparkle acompanharem seus servicos.

## Stack
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- Supabase JS Client

## Como rodar

```bash
# 1. Instalar dependencias
npm install

# 2. Subir em dev
npm run dev
```

Acesse: http://localhost:3000

## Variaveis de ambiente

Ja configuradas em `.env.local`:
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

> **ATENCAO ANTES DO DEPLOY:** A key atual em `.env.local` tem prefixo `sb_secret_`, o que indica que pode ser a `service_role` key do Supabase. Essa key da acesso total ao banco e bypassa o Row Level Security (RLS). Antes de ir para producao, verifique no Supabase Dashboard (Settings > API) e substitua pela **anon key**. Ative RLS na tabela `clients` para garantir que cada cliente so acesse seus proprios dados.

## Supabase — tabela `clients`

Campos esperados:
| Campo | Tipo | Descricao |
|-------|------|-----------|
| id | uuid | PK |
| name | text | Nome completo do cliente |
| company | text | Nome da empresa |
| email | text | Email para login |
| plan | text | Nome do plano |
| mrr | numeric | Valor mensal (R$) |
| due_day | int | Dia do vencimento |
| has_zenya | boolean | Tem Zenya ativa? |
| has_trafego | boolean | Tem trafego pago? |
| status | text | active / configurando |

## Funcionalidades v1
- Login por email (sem senha)
- Dashboard diferenciado: Zenya e/ou Trafego Pago
- Design dark com glassmorphism
- Responsivo (mobile-first)

## Build para producao

```bash
npm run build
npm start
```
