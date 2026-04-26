import { getServerSession } from 'next-auth'
import { NextResponse } from 'next/server'
import { authOptions } from '@/lib/auth'
import { proxyToBackendWithUser } from '@/lib/proxy'

async function getUserContext() {
  const session = await getServerSession(authOptions)
  if (!session?.user?.id) return null
  return {
    userId: session.user.id,
    userEmail: session.user.email ?? '',
    userName: session.user.name,
  }
}

export async function PATCH(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const user = await getUserContext()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { id } = await params
  const body = await req.text()
  return proxyToBackendWithUser(`experience/chunks/${id}`, user, { method: 'PATCH', body })
}
