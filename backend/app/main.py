import time

import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api import admin, experience, notion, tailorings, users
from app.clients.llm_client import validate_llm_config
from app.logging import setup_logging
from app.middleware.correlation import CorrelationIdMiddleware

_req_logger = structlog.get_logger("app.requests")


class _RequestLoggingMiddleware:
    """
    Pure-ASGI middleware: logs every HTTP request entry and exit.

    Logs method + path on entry so the correlation_id (already set by
    CorrelationIdMiddleware which runs first) appears in the entry record.
    Logs status_code + duration_ms on exit. Safe for SSE streaming — the
    'complete' log fires when the stream is fully consumed (useful for
    tracking stream duration).
    """

    def __init__(self, app) -> None:
        self._app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        method = scope.get("method", "")
        path = scope.get("path", "")
        start = time.perf_counter()

        _req_logger.info("request_start", method=method, path=path)

        status_code = [0]

        async def send_wrapped(message):
            if message["type"] == "http.response.start":
                status_code[0] = message.get("status", 0)
            await send(message)

        try:
            await self._app(scope, receive, send_wrapped)
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            _req_logger.info(
                "request_complete",
                method=method,
                path=path,
                status_code=status_code[0],
                duration_ms=duration_ms,
            )


def create_app() -> FastAPI:
    setup_logging()

    validate_llm_config()

    app = FastAPI(
        title="Tailord API",
        version="1.0.0",
    )

    # Middleware runs in reverse registration order (last registered = outermost).
    # We want: CorrelationId (outermost) → RequestLogging → app handlers.
    app.add_middleware(_RequestLoggingMiddleware)
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/health", include_in_schema=False)
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    app.include_router(users.router)
    app.include_router(admin.router)
    app.include_router(experience.router)
    app.include_router(tailorings.router)
    app.include_router(notion.router)
    return app


app = create_app()
