// Middleware de proteção de rotas — executa na Edge antes de cada request
//
// /dashboard/* → verifica cookie sparkle_session (sessão de cliente via Supabase REST)
// /hq/*        → verifica cookie sparkle_admin_session (JWT Supabase Auth do admin)
//
// Edge-compatible: sem Node.js APIs, sem @supabase/supabase-js no edge runtime

import { NextRequest, NextResponse } from 'next/server'

// ─── helpers ────────────────────────────────────────────────────────────────

function redirectLogin(req: NextRequest, msg: string) {
  const url = new URL('/login', req.url)
  url.searchParams.set('msg', msg)
  return NextResponse.redirect(url)
}

// ─── /hq/* guard — validates sparkle_admin_session JWT via Supabase Auth ───

async function handleHQAuth(req: NextRequest): Promise<NextResponse> {
  const adminToken = req.cookies.get('sparkle_admin_session')?.value

  if (!adminToken) {
    return redirectLogin(req, 'acesso-negado')
  }

  const supabaseUrl = process.env.SUPABASE_URL!
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

  try {
    // Validate JWT by calling Supabase Auth /user endpoint (edge-compatible fetch)
    const res = await fetch(`${supabaseUrl}/auth/v1/user`, {
      headers: {
        apikey: anonKey,
        Authorization: `Bearer ${adminToken}`,
      },
    })

    if (!res.ok) {
      const redirect = redirectLogin(req, 'sessao-expirada')
      redirect.cookies.delete('sparkle_admin_session')
      return redirect
    }

    const user = await res.json()

    // Enforce admin role
    if (user?.user_metadata?.role !== 'admin') {
      const redirect = redirectLogin(req, 'acesso-negado')
      redirect.cookies.delete('sparkle_admin_session')
      return redirect
    }

    // Inject user info for optional use in server components
    const requestHeaders = new Headers(req.headers)
    requestHeaders.set('x-admin-id', user.id ?? '')
    requestHeaders.set('x-admin-email', user.email ?? '')

    return NextResponse.next({ request: { headers: requestHeaders } })
  } catch {
    const redirect = redirectLogin(req, 'erro-autenticacao')
    redirect.cookies.delete('sparkle_admin_session')
    return redirect
  }
}

// ─── /dashboard/* guard — existing client session logic ─────────────────────

async function handleDashboardAuth(req: NextRequest): Promise<NextResponse> {
  const sessionToken = req.cookies.get('sparkle_session')?.value

  if (!sessionToken) {
    return NextResponse.redirect(new URL('/?msg=acesso-negado', req.url))
  }

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

    const requestHeaders = new Headers(req.headers)
    requestHeaders.set('x-client-id', sessions[0].client_id)

    return NextResponse.next({ request: { headers: requestHeaders } })
  } catch {
    const redirect = NextResponse.redirect(new URL('/?msg=erro-autenticacao', req.url))
    redirect.cookies.delete('sparkle_session')
    return redirect
  }
}

// ─── Main middleware ─────────────────────────────────────────────────────────

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl

  if (pathname.startsWith('/hq')) {
    return handleHQAuth(req)
  }

  if (pathname.startsWith('/dashboard')) {
    return handleDashboardAuth(req)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/hq/:path*', '/dashboard/:path*'],
}
