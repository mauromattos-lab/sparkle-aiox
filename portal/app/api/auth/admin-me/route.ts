// GET /api/auth/admin-me
// Valida o cookie sparkle_admin_session via Supabase Auth (getUser).
// Retorna dados do admin ou 401 se sessão inválida/expirada.

export const dynamic = 'force-dynamic'

import { NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = process.env.SUPABASE_URL!
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export async function GET() {
  const cookieStore = cookies()
  const token = cookieStore.get('sparkle_admin_session')?.value

  if (!token) {
    return NextResponse.json({ error: 'Não autenticado' }, { status: 401 })
  }

  try {
    // Validar token via Supabase Auth (getUser verifica JWT localmente + revogação)
    const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      global: { headers: { Authorization: `Bearer ${token}` } },
    })

    const { data, error } = await supabase.auth.getUser()

    if (error || !data.user) {
      return NextResponse.json({ error: 'Sessão inválida ou expirada' }, { status: 401 })
    }

    // Verificar role admin
    const role = data.user.user_metadata?.role
    if (role !== 'admin') {
      return NextResponse.json({ error: 'Acesso não autorizado' }, { status: 403 })
    }

    return NextResponse.json({
      user: {
        id: data.user.id,
        email: data.user.email,
        role,
      },
    })
  } catch (err) {
    console.error('[admin-me] error:', err)
    return NextResponse.json({ error: 'Erro interno' }, { status: 500 })
  }
}
