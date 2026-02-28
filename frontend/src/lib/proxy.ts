import { env } from './env'
import { NextResponse } from 'next/server'

export async function proxyToBackend(
  endpoint: string,
  body: string
): Promise<NextResponse> {
  try {
    const res = await fetch(`${env.apiBaseUrl}/${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': env.apiKey,
      },
      body,
    })

    if (!res.ok) {
      const text = await res.text()
      return NextResponse.json(
        { error: `Backend error: ${res.status}`, detail: text },
        { status: res.status }
      )
    }

    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error'
    return NextResponse.json(
      { error: 'Backend unreachable', detail: message },
      { status: 502 }
    )
  }
}

interface UserContext {
  userId: string
  userEmail: string
  userName?: string | null
}

export async function proxyToBackendWithUser(
  endpoint: string,
  user: UserContext,
  options: {
    method?: string
    body?: string
  } = {}
): Promise<NextResponse> {
  const { method = 'POST', body } = options

  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-API-Key': env.apiKey,
      'X-User-Id': user.userId,
      'X-User-Email': user.userEmail,
    }
    if (user.userName) {
      headers['X-User-Name'] = user.userName
    }

    const res = await fetch(`${env.apiBaseUrl}/${endpoint}`, {
      method,
      headers,
      ...(body !== undefined ? { body } : {}),
    })

    if (!res.ok) {
      const text = await res.text()
      return NextResponse.json(
        { error: `Backend error: ${res.status}`, detail: text },
        { status: res.status }
      )
    }

    if (res.status === 204) {
      return new NextResponse(null, { status: 204 })
    }

    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error'
    return NextResponse.json(
      { error: 'Backend unreachable', detail: message },
      { status: 502 }
    )
  }
}
