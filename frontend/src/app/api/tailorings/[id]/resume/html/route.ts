import { randomUUID } from 'crypto'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { buildUserHeaders } from '@/lib/proxy'
import { env } from '@/lib/env'

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await getServerSession(authOptions)
  if (!session?.user?.id) return new Response('Unauthorized', { status: 401 })

  const { id } = await params
  const user = {
    userId: session.user.id,
    userEmail: session.user.email ?? '',
    userName: session.user.name,
  }

  const res = await fetch(`${env.apiBaseUrl}/tailorings/${id}/resume/html`, {
    headers: buildUserHeaders(user, randomUUID()),
  })

  if (!res.ok) return new Response('Not found', { status: res.status })

  const html = await res.text()
  return new Response(html, {
    headers: { 'Content-Type': 'text/html; charset=utf-8' },
  })
}
