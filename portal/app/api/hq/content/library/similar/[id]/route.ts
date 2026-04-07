/**
 * API Proxy: GET /api/hq/content/library/similar/{id}
 * Proxies to Runtime GET /content/library/similar/{id}
 * CONTENT-1.8 — Get visually similar images by CLIP embedding
 */

const RUNTIME_URL = process.env.RUNTIME_URL || 'https://runtime.sparkleai.tech'
const API_KEY = process.env.RUNTIME_API_KEY

export async function GET(
  _request: Request,
  { params }: { params: { id: string } }
) {
  try {
    const res = await fetch(`${RUNTIME_URL}/content/library/similar/${params.id}`, {
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
