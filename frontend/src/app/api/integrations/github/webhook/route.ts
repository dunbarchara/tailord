import { NextRequest, NextResponse } from 'next/server'
import { env } from '@/lib/env'

export async function POST(request: NextRequest) {
  const body = await request.arrayBuffer()
  const sig = request.headers.get('X-Hub-Signature-256') ?? ''
  const event = request.headers.get('X-GitHub-Event') ?? ''
  const delivery = request.headers.get('X-GitHub-Delivery') ?? ''

  const res = await fetch(`${env.apiBaseUrl}/integrations/github/webhook`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Hub-Signature-256': sig,
      'X-GitHub-Event': event,
      'X-GitHub-Delivery': delivery,
    },
    body,
  })

  return new NextResponse(null, { status: res.status })
}
