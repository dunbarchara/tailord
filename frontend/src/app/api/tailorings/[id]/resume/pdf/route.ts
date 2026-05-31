import { randomUUID } from 'crypto'
import { getServerSession } from 'next-auth'
import { NextResponse } from 'next/server'
import { authOptions } from '@/lib/auth'
import { buildUserHeaders } from '@/lib/proxy'
import { env } from '@/lib/env'

async function getUserContext() {
  const session = await getServerSession(authOptions)
  if (!session?.user?.id) return null
  return {
    userId: session.user.id,
    userEmail: session.user.email ?? '',
    userName: session.user.name,
  }
}

export async function POST(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const user = await getUserContext()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { id } = await params
  const correlationId = randomUUID()
  const headers = buildUserHeaders(user, correlationId)

  const res = await fetch(`${env.apiBaseUrl}/tailorings/${id}/resume/pdf`, {
    method: 'POST',
    headers,
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    return NextResponse.json(
      { error: 'PDF generation failed', detail: text },
      { status: res.status }
    )
  }

  const blob = await res.blob()
  const disposition = res.headers.get('Content-Disposition') ?? 'attachment; filename="resume.pdf"'
  return new Response(blob, {
    headers: {
      'Content-Type': 'application/pdf',
      'Content-Disposition': disposition,
    },
  })
}
