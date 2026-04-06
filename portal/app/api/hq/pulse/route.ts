/**
 * API Proxy: GET /api/hq/pulse
 * Proxies to Runtime GET /system/pulse — injects API key server-side.
 * AC3: consolidated system status (agents, brain, workflows, clients).
 */

const RUNTIME_URL = process.env.RUNTIME_URL || 'https://runtime.sparkleai.tech'
const API_KEY = process.env.RUNTIME_API_KEY

export async function GET() {
  try {
    const res = await fetch(`${RUNTIME_URL}/system/pulse`, {
      headers: {
        'X-API-Key': API_KEY ?? '',
        'Content-Type': 'application/json',
      },
      next: { revalidate: 30 },
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
    console.error('[/api/hq/pulse] fetch error:', err)
    return Response.json({ error: 'Runtime unreachable' }, { status: 503 })
  }
}
