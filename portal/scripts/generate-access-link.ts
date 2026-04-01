// Script CLI para Mauro gerar links de acesso ao portal para qualquer cliente
//
// Uso:
//   npx ts-node --project tsconfig.json scripts/generate-access-link.ts <client_id>
//
// Exemplo:
//   npx ts-node --project tsconfig.json scripts/generate-access-link.ts 550e8400-e29b-41d4-a716-446655440000
//
// Requisitos: SUPABASE_URL e SUPABASE_SERVICE_KEY no .env.local

import { config } from 'dotenv'
import { resolve } from 'path'
import { randomBytes } from 'crypto'
import { createClient } from '@supabase/supabase-js'

// Carregar variáveis de ambiente do .env.local
config({ path: resolve(__dirname, '../.env.local') })

const clientId = process.argv[2]

if (!clientId) {
  console.error('\nErro: client_id obrigatório.')
  console.error('Uso: npx ts-node scripts/generate-access-link.ts <client_id>\n')
  process.exit(1)
}

if (!process.env.SUPABASE_URL || !process.env.SUPABASE_SERVICE_KEY) {
  console.error('\nErro: SUPABASE_URL e SUPABASE_SERVICE_KEY devem estar no portal/.env.local\n')
  process.exit(1)
}

const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_KEY!
)

const BASE_URL = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'

async function generateLink() {
  // Gerar token criptograficamente seguro (64 hex chars = 256 bits)
  const token = randomBytes(32).toString('hex')
  const expiresAt = new Date(Date.now() + 30 * 60 * 1000).toISOString()

  // Verificar se o cliente existe
  const { data: client, error: clientError } = await supabase
    .from('clients')
    .select('id, name, company')
    .eq('id', clientId)
    .single()

  if (clientError || !client) {
    console.error(`\nErro: cliente com id "${clientId}" não encontrado no Supabase.\n`)
    process.exit(1)
  }

  // Inserir sessão no banco
  const { error: insertError } = await supabase
    .from('client_sessions')
    .insert({
      client_id: clientId,
      token,
      expires_at: expiresAt,
    })

  if (insertError) {
    console.error('\nErro ao criar sessão:', insertError.message, '\n')
    process.exit(1)
  }

  const link = `${BASE_URL}/api/auth/validate?token=${token}`

  console.log('\n─────────────────────────────────────────')
  console.log(`  Link de acesso gerado com sucesso`)
  console.log('─────────────────────────────────────────')
  console.log(`  Cliente : ${client.name} (${client.company})`)
  console.log(`  Expira  : ${new Date(expiresAt).toLocaleString('pt-BR')}`)
  console.log(`  Link    : ${link}`)
  console.log('─────────────────────────────────────────\n')
}

generateLink()
