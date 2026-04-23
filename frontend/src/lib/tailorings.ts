import { env } from '@/lib/env'
import type { TailoringListItem } from '@/types'

export async function fetchDisplayName(
  userId: string,
  userEmail: string,
  userName?: string | null,
): Promise<string | null> {
  try {
    const headers: Record<string, string> = {
      'X-API-Key': env.apiKey,
      'X-User-Id': userId,
      'X-User-Email': userEmail,
    }
    if (userName) headers['X-User-Name'] = userName

    const res = await fetch(`${env.apiBaseUrl}/users/me`, {
      method: 'GET',
      headers,
      cache: 'no-store',
    })
    if (!res.ok) return userName ?? null
    const data = await res.json()
    const preferred = [data.preferred_first_name, data.preferred_last_name].filter(Boolean).join(' ')
    return preferred || userName || null
  } catch {
    return userName ?? null
  }
}

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
    const data = await res.json()
    return data.tailorings ?? []
  } catch {
    return []
  }
}
