import { getServerSession } from 'next-auth'
import { NextResponse } from 'next/server'
import { authOptions } from '@/lib/auth'
import { proxyToBackendWithUser } from '@/lib/proxy'

export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await getServerSession(authOptions)
  if (!session?.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const { id } = await params
  const body = await req.text()

  return proxyToBackendWithUser(
    `tailorings/${id}/gap-answer`,
    {
      userId: session.user.id,
      userEmail: session.user.email ?? '',
      userName: session.user.name,
    },
    { method: 'POST', body }
  )
}
