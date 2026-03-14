import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { proxyToBackendWithUser } from '@/lib/proxy';
import { logger } from '@/lib/logger';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';

// GET /api/auth/notion/callback — Notion redirects here after OAuth
export async function GET(req: Request) {
  const session = await getServerSession(authOptions);
  if (!session?.user) {
    logger.warn('Notion callback reached without session');
    return new Response('Unauthorized', { status: 401 });
  }

  const { searchParams } = new URL(req.url);
  const code = searchParams.get('code');
  const state = searchParams.get('state');
  const error = searchParams.get('error');

  if (error) {
    logger.warn('Notion OAuth returned error', { userId: session.user.id, error });
    redirect('/dashboard/settings?notion=error');
  }

  const cookieStore = await cookies();
  const storedState = cookieStore.get('notion_oauth_state')?.value;
  cookieStore.delete('notion_oauth_state');

  if (!code || !state || state !== storedState) {
    logger.warn('Notion callback state mismatch or missing code', { userId: session.user.id });
    redirect('/dashboard/settings?notion=error');
  }

  const user = {
    userId: session.user.id,
    userEmail: session.user.email ?? '',
    userName: session.user.name,
  };

  const res = await proxyToBackendWithUser('notion/callback', user, {
    method: 'POST',
    body: JSON.stringify({ code }),
  });

  if (!res.ok) {
    logger.error('Notion token exchange failed', { userId: user.userId });
    redirect('/dashboard/settings?notion=error');
  }

  logger.info('Notion workspace connected', { userId: user.userId });
  redirect('/dashboard/settings?notion=connected');
}
