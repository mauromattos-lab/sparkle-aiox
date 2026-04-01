// Middleware de proteção de rotas — executa na Edge antes de cada request
// Protege /dashboard/* verificando cookie sparkle_session via Supabase REST diretamente
// (edge-compatible: sem Node.js APIs, sem @supabase/supabase-js no edge runtime)

import { NextRequest, NextResponse } from 'next/server'

const PROTECTED_PATHS = ['/dashboard']

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl

  // Verificar se a rota é protegida
  const isProtected = PROTECTED_PATHS.some((p) => pathname.startsWith(p))
  if (!isProtected) return NextResponse.next()

  // Checar presença do cookie de sessão
  const sessionToken = req.cookies.get('sparkle_session')?.value
  if (!sessionToken) {
    return NextResponse.redirect(new URL('/?msg=acesso-negado', req.url))
  }

  // Validar token no Supabase via fetch direto (edge-compatible)
  const supabaseUrl = process.env.SUPABASE_URL!
  const serviceKey = process.env.SUPABASE_SERVICE_KEY!
  const now = new Date().toISOString()

  try {
    const res = await fetch(
      `${supabaseUrl}/rest/v1/client_sessions?token=eq.${encodeURIComponent(sessionToken)}&used=eq.false&expires_at=gt.${encodeURIComponent(now)}&select=client_id&limit=1`,
      {
        headers: {
          apikey: serviceKey,
          Authorization: `Bearer ${serviceKey}`,
          'Content-Type': 'application/json',
        },
      }
    )

    if (!res.ok) {
      const redirect = NextResponse.redirect(new URL('/?msg=sessao-expirada', req.url))
      redirect.cookies.delete('sparkle_session')
      return redirect
    }

    const sessions: { client_id: string }[] = await res.json()

    if (!sessions || sessions.length === 0) {
      const redirect = NextResponse.redirect(new URL('/?msg=sessao-expirada', req.url))
      redirect.cookies.delete('sparkle_session')
      return redirect
    }

    // Injetar client_id no header para uso opcional nas server components
    const requestHeaders = new Headers(req.headers)
    requestHeaders.set('x-client-id', sessions[0].client_id)

    return NextResponse.next({ request: { headers: requestHeaders } })
  } catch {
    // Falha de rede — redireciona com segurança
    const redirect = NextResponse.redirect(new URL('/?msg=erro-autenticacao', req.url))
    redirect.cookies.delete('sparkle_session')
    return redirect
  }
}

export const config = {
  matcher: ['/dashboard/:path*'],
}
