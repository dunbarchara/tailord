import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { proxyToBackendWithUser } from '@/lib/proxy';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';

// GET /api/auth/notion — fetch the Notion auth URL from backend and redirect
export async function GET() {
  const session = await getServerSession(authOptions);
  if (!session?.user) return new Response('Unauthorized', { status: 401 });

  const user = {
    userId: session.user.id,
    userEmail: session.user.email ?? '',
    userName: session.user.name,
  };

  const res = await proxyToBackendWithUser('notion/auth-url', user, { method: 'GET' });
  if (!res.ok) return new Response('Failed to get Notion auth URL', { status: 502 });

  const data = await res.json() as { url: string };

  // Set a short-lived state cookie to prevent CSRF on the callback
  const state = crypto.randomUUID();
  const cookieStore = await cookies();
  cookieStore.set('notion_oauth_state', state, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 300,
    path: '/',
  });

  // Append state to the Notion auth URL
  const authUrl = new URL(data.url);
  authUrl.searchParams.set('state', state);

  redirect(authUrl.toString());
}
