/**
 * API Proxy: GET /api/hq/content/library
 * Proxies to Runtime GET /content/library
 * CONTENT-0.1 — Style Library list + stats
 */

const RUNTIME_URL = process.env.RUNTIME_URL || 'https://runtime.sparkleai.tech'
const API_KEY = process.env.RUNTIME_API_KEY

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const qs = searchParams.toString()

  try {
    const res = await fetch(`${RUNTIME_URL}/content/library${qs ? `?${qs}` : ''}`, {
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
      return Response.json({ error: `Runtime ${res.status}` }, { status: res.status })
    }

    return Response.json(await res.json())
  } catch (err) {
    return Response.json({ error: String(err) }, { status: 500 })
  }
}
