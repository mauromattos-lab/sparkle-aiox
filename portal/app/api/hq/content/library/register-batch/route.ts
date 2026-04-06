/**
 * API Proxy: POST /api/hq/content/library/register-batch
 * Proxies to Runtime POST /content/library/register-batch
 * CONTENT-0.1 — Register batch of uploaded images
 */

const RUNTIME_URL = process.env.RUNTIME_URL || 'https://runtime.sparkleai.tech'
const API_KEY = process.env.RUNTIME_API_KEY

export async function POST(request: Request) {
  const body = await request.json().catch(() => null)

  try {
    const res = await fetch(`${RUNTIME_URL}/content/library/register-batch`, {
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
