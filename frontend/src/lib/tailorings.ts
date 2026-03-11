import { env } from '@/lib/env'
import type { TailoringListItem } from '@/types'

export async function fetchTailorings(
  userId: string,
  userEmail: string,
  userName?: string | null,
): Promise<TailoringListItem[]> {
  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-API-Key': env.apiKey,
      'X-User-Id': userId,
      'X-User-Email': userEmail,
    }
    if (userName) headers['X-User-Name'] = userName

    const res = await fetch(`${env.apiBaseUrl}/tailorings`, {
      method: 'GET',
      headers,
      cache: 'no-store',
    })
    if (!res.ok) return []
    return await res.json()
  } catch {
    return []
  }
}
