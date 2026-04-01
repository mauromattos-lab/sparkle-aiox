// GET /api/auth/validate?token=<token>
// Valida o token de acesso, seta cookie HTTP-only e redireciona para /dashboard.
// Chamado quando o cliente clica no link enviado via WhatsApp.

export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { supabaseServer } from '@/lib/supabase-server'

export async function GET(req: NextRequest) {
  const token = req.nextUrl.searchParams.get('token')

  if (!token) {
    return NextResponse.redirect(new URL('/?msg=token-invalido', req.url))
  }

  // Buscar sessão válida: não expirada e não invalidada
  const { data: session, error } = await supabaseServer
    .from('client_sessions')
    .select('id, client_id, expires_at')
    .eq('token', token)
    .eq('used', false)
    .gt('expires_at', new Date().toISOString())
    .single()

  if (error || !session) {
    return NextResponse.redirect(new URL('/?msg=link-expirado', req.url))
  }

  // Setar cookie HTTP-only — não acessível via JavaScript no browser
  // Usar x-forwarded-host do Traefik para evitar redirect para 0.0.0.0:3000
  const proto = req.headers.get('x-forwarded-proto') || 'https'
  const host = req.headers.get('x-forwarded-host') || req.headers.get('host') || 'portal.sparkleai.tech'
  const baseUrl = `${proto}://${host}`
  const response = NextResponse.redirect(new URL('/dashboard', baseUrl))
  response.cookies.set('sparkle_session', token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 1800, // 30 minutos em segundos
    path: '/',
  })

  return response
}
