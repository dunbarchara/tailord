import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { fetchTailorings } from '@/lib/tailorings'
import { Sidebar } from '@/components/dashboard/Sidebar'
import type { TailoringListItem } from '@/types'

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
    <div className="flex h-screen bg-surface-base overflow-hidden" style={{ fontFamily: "ui-sans-serif, system-ui, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji'", WebkitFontSmoothing: 'antialiased' }}>
      <Sidebar tailorings={tailorings} />
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
