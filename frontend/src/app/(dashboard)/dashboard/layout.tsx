import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { env } from '@/lib/env'
import { Sidebar } from '@/components/dashboard/Sidebar'
import type { TailoringListItem } from '@/types'

async function fetchTailorings(userId: string, userEmail: string, userName?: string | null): Promise<TailoringListItem[]> {
  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-API-Key': env.apiKey,
      'X-User-Id': userId,
      'X-User-Email': userEmail,
    }
    if (userName) headers['X-User-Name'] = userName

    const res = await fetch(`${env.apiBaseUrl}/tailorings`, {
      method: 'GET',
      headers,
      cache: 'no-store',
    })
    if (!res.ok) return []
    return await res.json()
  } catch {
    return []
  }
}

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getServerSession(authOptions)
  const tailorings: TailoringListItem[] = session?.user?.id
    ? await fetchTailorings(session.user.id, session.user.email ?? '', session.user.name)
    : []

  return (
    <div className="flex h-screen bg-surface-base overflow-hidden">
      <Sidebar tailorings={tailorings} />
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
