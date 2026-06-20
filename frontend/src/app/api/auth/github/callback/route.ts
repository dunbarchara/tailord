import { getServerSession } from 'next-auth'
import { NextRequest, NextResponse } from 'next/server'
import { authOptions } from '@/lib/auth'
import { proxyToBackendWithUser } from '@/lib/proxy'

export async function GET(request: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session?.user?.id) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  const { searchParams } = new URL(request.url)
  const code = searchParams.get('code')
  const installationId = searchParams.get('installation_id')

  if (!code || !installationId) {
    return NextResponse.redirect(
      new URL('/dashboard/experience?github_error=missing_params', request.url)
    )
  }

  const user = {
    userId: session.user.id,
    userEmail: session.user.email ?? '',
    userName: session.user.name,
  }

  const res = await proxyToBackendWithUser(
    `integrations/github/callback?code=${encodeURIComponent(code)}&installation_id=${encodeURIComponent(installationId)}`,
    user,
    { method: 'GET' }
  )

  if (!res.ok) {
    return NextResponse.redirect(
      new URL('/dashboard/experience?github_error=callback_failed', request.url)
    )
  }

  return NextResponse.redirect(
    new URL('/dashboard/experience?github_connected=true', request.url)
  )
}
