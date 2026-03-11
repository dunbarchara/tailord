import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { fetchTailorings } from '@/lib/tailorings';
import { EmptyState } from '@/components/dashboard/EmptyState';
import { RecentTailorings } from '@/components/dashboard/RecentTailorings';

export default async function DashboardPage() {
  const session = await getServerSession(authOptions);
  const tailorings = session?.user?.id
    ? await fetchTailorings(session.user.id, session.user.email ?? '', session.user.name)
    : [];

  return (
    <div className="h-full">
      {tailorings.length === 0 ? (
        <EmptyState />
      ) : (
        <RecentTailorings tailorings={tailorings} />
      )}
    </div>
  );
}
