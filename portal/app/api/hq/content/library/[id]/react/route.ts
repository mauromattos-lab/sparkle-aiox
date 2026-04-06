/**
 * API Proxy: POST /api/hq/content/library/{id}/react
 * Proxies to Runtime POST /content/library/{id}/react
 * CONTENT-0.1 — React to image (like/discard/neutral)
 */

const RUNTIME_URL = process.env.RUNTIME_URL || 'https://runtime.sparkleai.tech'
const API_KEY = process.env.RUNTIME_API_KEY

export async function POST(
  request: Request,
  { params }: { params: { id: string } }
) {
  const body = await request.json().catch(() => null)

  try {
    const res = await fetch(`${RUNTIME_URL}/content/library/${params.id}/react`, {
      method: 'POST',
      headers: {
        'X-API-Key': API_KEY ?? '',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
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
