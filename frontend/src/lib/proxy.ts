import { env } from './env'
import { NextResponse } from 'next/server'

export async function proxyToBackend(
  endpoint: string,
  body: string
): Promise<NextResponse> {
  try {
    const res = await fetch(`${env.apiBaseUrl}/${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': env.apiKey,
      },
      body,
    })

    if (!res.ok) {
      const text = await res.text()
      return NextResponse.json(
        { error: `Backend error: ${res.status}`, detail: text },
        { status: res.status }
      )
    }

    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error'
    return NextResponse.json(
      { error: 'Backend unreachable', detail: message },
      { status: 502 }
    )
  }
}
