/**
 * API Proxy: GET /api/hq/activity
 * Proxies to Runtime GET /cockpit/activity — injects API key server-side.
 * AC2: returns last 50 runtime events.
 */

const RUNTIME_URL = process.env.RUNTIME_URL || 'https://runtime.sparkleai.tech'
const API_KEY = process.env.RUNTIME_API_KEY

export async function GET() {
  try {
    const res = await fetch(`${RUNTIME_URL}/cockpit/activity`, {
      headers: {
        'X-API-Key': API_KEY ?? '',
        'Content-Type': 'application/json',
      },
      // Activity feed does not use Next.js cache — SWR handles client-side polling
      cache: 'no-store',
    })

    if (!res.ok) {
      return Response.json(
        { error: `Runtime responded with ${res.status}` },
        { status: res.status }
      )
    }

    const data = await res.json()
    return Response.json(data)
  } catch (err) {
    console.error('[/api/hq/activity] fetch error:', err)
    return Response.json({ error: 'Runtime unreachable' }, { status: 503 })
  }
}
