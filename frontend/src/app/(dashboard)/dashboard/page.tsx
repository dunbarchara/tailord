import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { fetchTailorings } from '@/lib/tailorings';
import { DashboardHome } from '@/components/dashboard/DashboardHome';

export default async function DashboardPage() {
  const session = await getServerSession(authOptions);
  const tailorings = session?.user?.id
    ? await fetchTailorings(session.user.id, session.user.email ?? '', session.user.name)
    : [];

  return (
    <div className="h-full">
      <DashboardHome
        name={session?.user?.name ?? null}
        tailorings={tailorings}
      />
    </div>
  );
}
