import uuid

import structlog


class CorrelationIdMiddleware:
    """
    Pure-ASGI middleware: reads X-Correlation-Id from the incoming request (or generates
    a new UUID4), binds it to the structlog context so every log record in this request's
    async scope carries it automatically, and echoes it back in the response headers.

    Uses structlog.contextvars rather than a raw ContextVar — this is the idiomatic
    structlog pattern and means correlation_id appears in all log records without any
    per-callsite plumbing.

    Implemented as a raw ASGI middleware (not BaseHTTPMiddleware) so it is safe for
    long-running SSE streaming responses.
    """

    def __init__(self, app) -> None:
        self._app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        if scope.get("path") == "/metrics":
            await self._app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        raw = headers.get(b"x-correlation-id", b"")
        correlation_id = raw.decode("utf-8") if raw else str(uuid.uuid4())

        # Clear any context from a previous request that might have leaked into
        # this async task, then bind the correlation ID for this request.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        async def send_with_header(message):
            if message["type"] == "http.response.start":
                headers_list = list(message.get("headers", []))
                headers_list.append((b"x-correlation-id", correlation_id.encode("utf-8")))
                message = {**message, "headers": headers_list}
            await send(message)

        await self._app(scope, receive, send_with_header)
