import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { fetchTailorings, fetchDisplayName, fetchExperience } from '@/lib/tailorings';
import { DashboardHome } from '@/components/dashboard/DashboardHome';

export default async function DashboardPage() {
  const session = await getServerSession(authOptions);
  const [tailorings, displayName, experience] = session?.user?.id
    ? await Promise.all([
        fetchTailorings(session.user.id, session.user.email ?? '', session.user.name),
        fetchDisplayName(session.user.id, session.user.email ?? '', session.user.name),
        fetchExperience(session.user.id, session.user.email ?? '', session.user.name),
      ])
    : [[], null, null];

  const hasExperience = !!(
    experience?.extracted_profile?.resume ||
    experience?.extracted_profile?.github ||
    experience?.github_username
  );

  return (
    <div className="h-full">
      <DashboardHome
        name={displayName}
        tailorings={tailorings}
        hasExperience={hasExperience}
      />
    </div>
  );
}
