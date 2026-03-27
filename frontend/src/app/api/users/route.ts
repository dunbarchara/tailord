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
    userImage: session.user.image,
  };
}

export async function GET() {
  const user = await getUser();
  if (!user) return new Response('Unauthorized', { status: 401 });
  return proxyToBackendWithUser('users/me', user, { method: 'GET' });
}

export async function PATCH(req: Request) {
  const user = await getUser();
  if (!user) return new Response('Unauthorized', { status: 401 });
  const body = await req.text();
  return proxyToBackendWithUser('users/me', user, { method: 'PATCH', body });
}

export async function DELETE() {
  const user = await getUser();
  if (!user) return new Response('Unauthorized', { status: 401 });
  return proxyToBackendWithUser('users/me', user, { method: 'DELETE' });
}
