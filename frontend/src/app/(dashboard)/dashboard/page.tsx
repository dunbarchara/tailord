import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { fetchTailorings, fetchDisplayName } from '@/lib/tailorings';
import { DashboardHome } from '@/components/dashboard/DashboardHome';

export default async function DashboardPage() {
  const session = await getServerSession(authOptions);
  const [tailorings, displayName] = session?.user?.id
    ? await Promise.all([
        fetchTailorings(session.user.id, session.user.email ?? '', session.user.name),
        fetchDisplayName(session.user.id, session.user.email ?? '', session.user.name),
      ])
    : [[], null];

  return (
    <div className="h-full">
      <DashboardHome
        name={displayName}
        tailorings={tailorings}
      />
    </div>
  );
}
