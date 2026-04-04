// POST /api/auth/login
// Autentica com email+senha via Supabase Auth, cria client_session e seta cookie.
// Retorna JSON com sucesso ou erro — consumido pelo formulário de login.

export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { randomUUID } from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL!
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export async function POST(req: NextRequest) {
  try {
    const { email, password } = await req.json()

    if (!email || !password) {
      return NextResponse.json(
        { error: 'Email e senha obrigatórios.' },
        { status: 400 }
      )
    }

    // Autenticar via Supabase Auth (anon key)
    const supabaseAuth = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

    const { data: authData, error: authError } =
      await supabaseAuth.auth.signInWithPassword({ email, password })

    if (authError || !authData.session) {
      return NextResponse.json(
        { error: 'Email ou senha incorretos.' },
        { status: 401 }
      )
    }

    // Client autenticado com token do usuário (respeita RLS)
    const supabaseUser = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      global: { headers: { Authorization: `Bearer ${authData.session.access_token}` } },
    })

    // Buscar client vinculado ao email autenticado
    const { data: client, error: clientError } = await supabaseUser
      .from('clients')
      .select('id')
      .eq('email', email.toLowerCase().trim())
      .single()

    if (clientError || !client) {
      return NextResponse.json(
        { error: 'Conta autenticada, mas nenhum cliente vinculado a este email.' },
        { status: 403 }
      )
    }

    // Criar session token (mesmo padrão do fluxo WhatsApp)
    const token = randomUUID()
    const expiresAt = new Date(Date.now() + 30 * 60 * 1000).toISOString() // 30 min

    const { error: insertError } = await supabaseUser
      .from('client_sessions')
      .insert({
        client_id: client.id,
        token,
        expires_at: expiresAt,
        used: false,
        source: 'login_form',
      })

    if (insertError) {
      console.error('Erro ao criar sessão:', insertError)
      return NextResponse.json(
        { error: 'Erro ao criar sessão. Tente novamente.' },
        { status: 500 }
      )
    }

    // Setar cookie HTTP-only (mesmo padrão do /api/auth/validate)
    const response = NextResponse.json({ success: true })
    response.cookies.set('sparkle_session', token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 1800, // 30 minutos
      path: '/',
    })

    return response
  } catch (err) {
    console.error('Login error:', err)
    return NextResponse.json(
      { error: 'Erro interno. Tente novamente.' },
      { status: 500 }
    )
  }
}
