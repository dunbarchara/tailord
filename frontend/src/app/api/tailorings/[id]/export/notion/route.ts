import { getServerSession } from 'next-auth'
import { NextResponse } from 'next/server'
import { authOptions } from '@/lib/auth'
import { proxyToBackendWithUser } from '@/lib/proxy'

export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await getServerSession(authOptions)
  if (!session?.user?.id) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { id } = await params
  const { searchParams } = new URL(req.url)
  const view = searchParams.get('view') ?? 'letter'

  return proxyToBackendWithUser(`notion/export/${id}?view=${view}`, {
    userId: session.user.id,
    userEmail: session.user.email ?? '',
    userName: session.user.name,
  }, { method: 'POST' })
}
