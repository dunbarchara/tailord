import re
import time

import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

# Telemetry must be configured before any module that creates OTel metric
# instruments at import time (metrics.py, and api modules that import it).
from app.telemetry import setup_telemetry

setup_telemetry()

from app.api import admin, experience, integrations, notion, resume, tailorings, users  # noqa: E402
from app.clients.llm_client import validate_llm_config  # noqa: E402
from app.logging import setup_logging  # noqa: E402
from app.metrics import HTTP_REQUEST_DURATION_MS, HTTP_REQUESTS_TOTAL  # noqa: E402
from app.middleware.correlation import CorrelationIdMiddleware  # noqa: E402

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)


def _normalize_path(path: str) -> str:
    return _UUID_RE.sub("{id}", path)


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

        if scope.get("path") == "/metrics":
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
            norm_path = _normalize_path(path)
            HTTP_REQUESTS_TOTAL.labels(
                method=method, endpoint=norm_path, status_code=str(status_code[0])
            ).inc()
            HTTP_REQUEST_DURATION_MS.labels(method=method, endpoint=norm_path).observe(duration_ms)


def create_app() -> FastAPI:
    setup_logging()

    validate_llm_config()

    app = FastAPI(
        title="Tailord API",
        version="1.0.0",
    )

    app.mount("/metrics", make_asgi_app())

    # Middleware runs in reverse registration order (last registered = outermost).
    # We want: CorrelationId (outermost) → RequestLogging → app handlers.
    app.add_middleware(_RequestLoggingMiddleware)
    app.add_middleware(CorrelationIdMiddleware)

    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    FastAPIInstrumentor().instrument_app(app)
    SQLAlchemyInstrumentor().instrument()

    @app.get("/health", include_in_schema=False)
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    app.include_router(users.router)
    app.include_router(admin.router)
    app.include_router(experience.router)
    app.include_router(tailorings.router)
    app.include_router(resume.router)
    app.include_router(notion.router)
    app.include_router(integrations.router)
    return app


app = create_app()
