// POST /api/auth/admin-logout
// Limpa o cookie sparkle_admin_session e redireciona para /login.

export const dynamic = 'force-dynamic'

import { NextResponse } from 'next/server'

export async function POST() {
  const response = NextResponse.json({ success: true })
  response.cookies.set('sparkle_admin_session', '', {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: 0,
  })
  return response
}
