import { randomUUID } from 'crypto'
import { env } from './env'
import { logger } from './logger'
import { NextResponse } from 'next/server'

export async function proxyToBackend(
  endpoint: string,
  body: string
): Promise<NextResponse> {
  const correlationId = randomUUID()

  try {
    const res = await fetch(`${env.apiBaseUrl}/${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': env.apiKey,
        'X-Correlation-Id': correlationId,
      },
      body,
    })

    if (!res.ok) {
      const text = await res.text()
      let detail: string = text
      try {
        const parsed = JSON.parse(text)
        if (typeof parsed?.detail === 'string') detail = parsed.detail
      } catch {}
      logger.error('Backend error', { method: 'POST', endpoint, status: res.status, detail, correlation_id: correlationId })
      return NextResponse.json(
        { error: `Backend error: ${res.status}`, detail },
        { status: res.status, headers: { 'X-Correlation-Id': correlationId } }
      )
    }

    logger.info('Backend request', { method: 'POST', endpoint, status: res.status, correlation_id: correlationId })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status, headers: { 'X-Correlation-Id': correlationId } })
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error'
    logger.error('Backend unreachable', { method: 'POST', endpoint, error: message, correlation_id: correlationId })
    return NextResponse.json(
      { error: 'Backend unreachable', detail: message },
      { status: 502, headers: { 'X-Correlation-Id': correlationId } }
    )
  }
}

interface UserContext {
  userId: string
  userEmail: string
  userName?: string | null
  userImage?: string | null
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
  const correlationId = randomUUID()

  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-API-Key': env.apiKey,
      'X-User-Id': user.userId,
      'X-User-Email': user.userEmail,
      'X-Correlation-Id': correlationId,
    }
    if (user.userName) {
      headers['X-User-Name'] = user.userName
    }
    if (user.userImage) {
      headers['X-User-Image'] = user.userImage
    }

    logger.debug('Backend request', { method, endpoint, userId: user.userId, correlation_id: correlationId })

    const res = await fetch(`${env.apiBaseUrl}/${endpoint}`, {
      method,
      headers,
      ...(body !== undefined ? { body } : {}),
    })

    if (!res.ok) {
      const text = await res.text()
      let detail: string = text
      try {
        const parsed = JSON.parse(text)
        if (typeof parsed?.detail === 'string') detail = parsed.detail
      } catch {}
      logger.error('Backend error', { method, endpoint, status: res.status, detail, userId: user.userId, correlation_id: correlationId })
      return NextResponse.json(
        { error: `Backend error: ${res.status}`, detail },
        { status: res.status, headers: { 'X-Correlation-Id': correlationId } }
      )
    }

    logger.info('Backend response', { method, endpoint, status: res.status, userId: user.userId, correlation_id: correlationId })

    if (res.status === 204) {
      return new NextResponse(null, { status: 204, headers: { 'X-Correlation-Id': correlationId } })
    }

    const data = await res.json()
    return NextResponse.json(data, { status: res.status, headers: { 'X-Correlation-Id': correlationId } })
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error'
    logger.error('Backend unreachable', { method, endpoint, error: message, userId: user.userId, correlation_id: correlationId })
    return NextResponse.json(
      { error: 'Backend unreachable', detail: message },
      { status: 502, headers: { 'X-Correlation-Id': correlationId } }
    )
  }
}

/**
 * Proxy an SSE (text/event-stream) request to the backend, passing the stream
 * body through without buffering. Used for long-running LLM endpoints.
 */
export async function proxyStreamToBackendWithUser(
  endpoint: string,
  user: UserContext,
  body?: string,
): Promise<Response> {
  const correlationId = randomUUID()

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-API-Key': env.apiKey,
    'X-User-Id': user.userId,
    'X-User-Email': user.userEmail,
    'X-Correlation-Id': correlationId,
  }
  if (user.userName) {
    headers['X-User-Name'] = user.userName
  }
  if (user.userImage) {
    headers['X-User-Image'] = user.userImage
  }

  logger.debug('Backend stream request', { endpoint, userId: user.userId, correlation_id: correlationId })

  try {
    const res = await fetch(`${env.apiBaseUrl}/${endpoint}`, {
      method: 'POST',
      headers,
      ...(body !== undefined ? { body } : {}),
    })

    if (!res.ok) {
      const text = await res.text()
      let detail: string = text
      try {
        const parsed = JSON.parse(text)
        if (typeof parsed?.detail === 'string') detail = parsed.detail
      } catch {}
      logger.error('Backend stream error', { endpoint, status: res.status, detail, userId: user.userId, correlation_id: correlationId })
      return new Response(
        JSON.stringify({ error: `Backend error: ${res.status}`, detail }),
        { status: res.status, headers: { 'Content-Type': 'application/json', 'X-Correlation-Id': correlationId } }
      )
    }

    // Pass the stream body through — do not buffer
    return new Response(res.body, {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'X-Correlation-Id': correlationId,
      },
    })
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error'
    logger.error('Backend stream unreachable', { endpoint, error: message, userId: user.userId, correlation_id: correlationId })
    return new Response(
      JSON.stringify({ error: 'Backend unreachable', detail: message }),
      { status: 502, headers: { 'Content-Type': 'application/json', 'X-Correlation-Id': correlationId } }
    )
  }
}
