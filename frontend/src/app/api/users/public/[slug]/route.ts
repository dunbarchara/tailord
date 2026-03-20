import { NextResponse } from 'next/server'
import { env } from '@/lib/env'

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ slug: string }> }
) {
  const { slug } = await params

  try {
    const res = await fetch(`${env.apiBaseUrl}/users/public/${slug}`, {
      headers: { 'X-API-Key': env.apiKey },
    })

    if (!res.ok) {
      const text = await res.text()
      return NextResponse.json(
        { error: `Backend error: ${res.status}`, detail: text },
        { status: res.status }
      )
    }

    const data = await res.json()
    return NextResponse.json(data)
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error'
    return NextResponse.json(
      { error: 'Backend unreachable', detail: message },
      { status: 502 }
    )
  }
}
