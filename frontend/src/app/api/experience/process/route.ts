import { getServerSession } from 'next-auth'
import { NextResponse } from 'next/server'
import { authOptions } from '@/lib/auth'
import { proxyStreamToBackendWithUser } from '@/lib/proxy'

export async function POST(req: Request) {
  const session = await getServerSession(authOptions)
  if (!session?.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  return proxyStreamToBackendWithUser('experience/process', {
    userId: session.user.id,
    userEmail: session.user.email ?? '',
    userName: session.user.name,
  }, await req.text())
}
