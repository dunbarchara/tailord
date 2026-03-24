import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { env } from '@/lib/env'

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ slug: string }> }
) {
  const session = await getServerSession(authOptions)
  if (!session?.user) return new Response('Unauthorized', { status: 401 })

  const { slug } = await params

  try {
    const res = await fetch(`${env.apiBaseUrl}/users/check-username/${slug}`, {
      headers: { 'X-API-Key': env.apiKey },
    })

    if (!res.ok) {
      return NextResponse.json({ available: false }, { status: res.status })
    }

    const data = await res.json()
    return NextResponse.json(data)
  } catch {
    return NextResponse.json({ available: false }, { status: 502 })
  }
}
