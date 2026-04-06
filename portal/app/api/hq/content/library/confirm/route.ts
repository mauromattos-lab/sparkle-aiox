/**
 * API Proxy: POST /api/hq/content/library/confirm
 * Proxies to Runtime POST /content/library/confirm
 * CONTENT-0.1 — Confirm Style Library (apply tiers)
 */

const RUNTIME_URL = process.env.RUNTIME_URL || 'https://runtime.sparkleai.tech'
const API_KEY = process.env.RUNTIME_API_KEY

export async function POST(request: Request) {
  const { searchParams } = new URL(request.url)
  const creatorId = searchParams.get('creator_id') || 'zenya'

  try {
    const res = await fetch(
      `${RUNTIME_URL}/content/library/confirm?creator_id=${creatorId}`,
      {
        method: 'POST',
        headers: {
          'X-API-Key': API_KEY ?? '',
          'Content-Type': 'application/json',
        },
      }
    )

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `Runtime ${res.status}` }))
      return Response.json(err, { status: res.status })
    }

    return Response.json(await res.json())
  } catch (err) {
    return Response.json({ error: String(err) }, { status: 500 })
  }
}
