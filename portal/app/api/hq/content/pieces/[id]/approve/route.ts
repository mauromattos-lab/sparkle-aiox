/**
 * API Proxy: POST /api/hq/content/pieces/{id}/approve
 * Proxies to Runtime POST /content/pieces/{id}/approve
 * CONTENT-1.7 — Approve a content piece
 */

const RUNTIME_URL = process.env.RUNTIME_URL || 'https://runtime.sparkleai.tech'
const API_KEY = process.env.RUNTIME_API_KEY

export async function POST(
  _request: Request,
  { params }: { params: { id: string } }
) {
  try {
    const res = await fetch(`${RUNTIME_URL}/content/pieces/${params.id}/approve`, {
      method: 'POST',
      headers: {
        'X-API-Key': API_KEY ?? '',
        'Content-Type': 'application/json',
      },
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `Runtime ${res.status}` }))
      return Response.json(err, { status: res.status })
    }

    return Response.json(await res.json())
  } catch (err) {
    return Response.json({ error: String(err) }, { status: 500 })
  }
}
