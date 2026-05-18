import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog

from app.config import settings


def _uppercase_level(logger: object, method: str, event_dict: dict) -> dict:
    """Normalize log level to uppercase to match Log Analytics KQL conventions."""
    if "level" in event_dict:
        event_dict["level"] = event_dict["level"].upper()
    return event_dict


# Processors shared between structlog native loggers and stdlib foreign loggers.
# Order matters: merge context vars first, then add metadata, then format.
_shared_processors: list = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    _uppercase_level,
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.processors.TimeStamper(fmt="iso"),
]


def setup_logging() -> None:
    """
    Configure structlog as the application-wide logging backend.

    structlog native loggers (structlog.get_logger()) produce JSON directly.
    stdlib loggers (logging.getLogger()) are routed through ProcessorFormatter
    so they also emit JSON — this covers third-party libraries and unmodified
    app code that hasn't been migrated to structlog yet.

    Every log line includes correlation_id automatically via merge_contextvars,
    which reads whatever was bound by CorrelationIdMiddleware (or the background
    task re-bind) for the current async context.
    """
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    structlog.configure(
        processors=_shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Local dev: human-readable colored output.
    # All other environments: JSON for Log Analytics ingestion.
    renderer = (
        structlog.dev.ConsoleRenderer()
        if settings.environment == "local"
        else structlog.processors.JSONRenderer()
    )

    # ProcessorFormatter bridges stdlib → structlog pipeline.
    # foreign_pre_chain applies to records from stdlib logging.getLogger() calls.
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=_shared_processors,
    )

    handlers: list[logging.Handler] = []

    if settings.environment == "local":
        log_dir = Path(settings.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        json_formatter = structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
            foreign_pre_chain=_shared_processors,
        )
        json_file_handler = RotatingFileHandler(
            log_dir / "app.jsonl",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        json_file_handler.setFormatter(json_formatter)
        handlers.append(json_file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)

    logging.basicConfig(level=log_level, handlers=handlers)

    # Silence noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
