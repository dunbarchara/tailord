import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { proxyToBackendWithUser } from '@/lib/proxy';

async function getUser() {
  const session = await getServerSession(authOptions);
  if (!session?.user) return null;
  return {
    userId: session.user.id,
    userEmail: session.user.email ?? '',
    userName: session.user.name,
  };
}

// DELETE /api/notion — disconnect Notion integration
export async function DELETE() {
  const user = await getUser();
  if (!user) return new Response('Unauthorized', { status: 401 });
  return proxyToBackendWithUser('notion/disconnect', user, { method: 'DELETE' });
}
