/**
 * API Proxy: GET /api/hq/content/pieces
 * Proxies to Runtime GET /content/pieces
 * CONTENT-1.9 — List all content pieces (for calendar view)
 */

const RUNTIME_URL = process.env.RUNTIME_URL || 'https://runtime.sparkleai.tech'
const API_KEY = process.env.RUNTIME_API_KEY

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const qs = searchParams.toString()

  try {
    const res = await fetch(`${RUNTIME_URL}/content/pieces${qs ? `?${qs}` : ''}`, {
      headers: {
        'X-API-Key': API_KEY ?? '',
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    })

    if (!res.ok) {
      return Response.json({ error: `Runtime ${res.status}` }, { status: res.status })
    }

    return Response.json(await res.json())
  } catch (err) {
    return Response.json({ error: String(err) }, { status: 500 })
  }
}
