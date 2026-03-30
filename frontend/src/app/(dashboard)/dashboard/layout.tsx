import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { fetchTailorings } from '@/lib/tailorings'
import { SidebarMintlify } from '@/components/dashboard/SidebarMintlify'
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
    <div className="flex h-screen bg-[#FAFAF9] overflow-hidden" style={{ fontFamily: "ui-sans-serif, system-ui, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji'", WebkitFontSmoothing: 'auto' }}>
      <SidebarMintlify tailorings={tailorings} />
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
