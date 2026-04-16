import { getServerSession } from 'next-auth'
import { NextResponse } from 'next/server'
import { authOptions } from '@/lib/auth'
import { proxyToBackendWithUser } from '@/lib/proxy'

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ username: string }> }
) {
  const session = await getServerSession(authOptions)
  if (!session?.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const { username } = await params

  return proxyToBackendWithUser(`experience/github/${encodeURIComponent(username)}/repos`, {
    userId: session.user.id,
    userEmail: session.user.email ?? '',
    userName: session.user.name,
  }, { method: 'GET' })
}
