// POST /api/auth/admin-login
// Autentica Mauro (admin) com email + senha via Supabase Auth.
// Verifica role admin no user_metadata, seta cookie sparkle_admin_session (7 dias).

export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = process.env.SUPABASE_URL!
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const { email, password } = body ?? {}

    if (!email || !password) {
      return NextResponse.json(
        { error: 'Email e senha são obrigatórios.' },
        { status: 400 }
      )
    }

    // Autenticar via Supabase Auth
    const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
    const { data: authData, error: authError } = await supabase.auth.signInWithPassword({
      email: email.trim().toLowerCase(),
      password,
    })

    if (authError || !authData.session || !authData.user) {
      return NextResponse.json(
        { error: 'Email ou senha incorretos.' },
        { status: 401 }
      )
    }

    // Verificar role admin no user_metadata
    const role = authData.user.user_metadata?.role
    if (role !== 'admin') {
      return NextResponse.json(
        { error: 'Acesso não autorizado. Conta sem permissão de administrador.' },
        { status: 403 }
      )
    }

    // Usar access_token da sessão Supabase como valor do cookie admin
    const sessionToken = authData.session.access_token

    // Retornar sucesso e setar cookie HTTP-only (7 dias)
    const response = NextResponse.json({
      success: true,
      user: {
        id: authData.user.id,
        email: authData.user.email,
        role,
      },
    })

    response.cookies.set('sparkle_admin_session', sessionToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 604800, // 7 dias em segundos
      path: '/',
    })

    return response
  } catch (err) {
    console.error('[admin-login] error:', err)
    return NextResponse.json(
      { error: 'Erro interno. Tente novamente.' },
      { status: 500 }
    )
  }
}
