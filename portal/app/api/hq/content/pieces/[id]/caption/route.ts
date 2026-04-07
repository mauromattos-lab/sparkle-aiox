/**
 * API Proxy: PATCH /api/hq/content/pieces/{id}/caption
 * Proxies to Runtime PATCH /content/pieces/{id}/caption
 * CONTENT-1.7 — Edit caption of a content piece
 */

const RUNTIME_URL = process.env.RUNTIME_URL || 'https://runtime.sparkleai.tech'
const API_KEY = process.env.RUNTIME_API_KEY

export async function PATCH(
  request: Request,
  { params }: { params: { id: string } }
) {
  const body = await request.json().catch(() => null)

  try {
    const res = await fetch(`${RUNTIME_URL}/content/pieces/${params.id}/caption`, {
      method: 'PATCH',
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
