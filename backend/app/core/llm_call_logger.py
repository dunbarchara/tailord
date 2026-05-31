"""
llm_call_logger.py — non-fatal per-call row writer for llm_call_logs.

Called from llm_parse, llm_generate, and embed_text after every successful call.
Creates its own DB session per write. user_id is read from structlog context vars
(bound by deps_user.py on every authenticated request and in background task setup).
Non-fatal: logs a warning and returns on any error.
"""

import uuid

import structlog
import structlog.contextvars

logger = structlog.get_logger(__name__)


def log_llm_call(
    *,
    call_type: str,
    model: str,
    prompt_name: str,
    input_tokens: int,
    cached_tokens: int = 0,
    output_tokens: int | None = None,
    latency_ms: int,
) -> None:
    try:
        ctx = structlog.contextvars.get_contextvars()
        user_id_str = ctx.get("user_id")
        tailoring_id_str = ctx.get("tailoring_id")
        user_id = uuid.UUID(user_id_str) if user_id_str else None
        tailoring_id = uuid.UUID(tailoring_id_str) if tailoring_id_str else None

        from app.clients.database import SessionLocal
        from app.models.database import LlmCallLog

        db = SessionLocal()
        try:
            db.add(
                LlmCallLog(
                    user_id=user_id,
                    tailoring_id=tailoring_id,
                    call_type=call_type,
                    model=model,
                    prompt_name=prompt_name,
                    input_tokens=input_tokens,
                    cached_tokens=cached_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.warning("llm_call_log_write_failed", model=model, prompt_name=prompt_name)


def cleanup_old_llm_call_logs() -> None:
    """Delete llm_call_logs rows older than 90 days. Non-fatal. Called from _finalize_tailoring."""
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    try:
        from app.clients.database import SessionLocal
        from app.models.database import LlmCallLog

        with SessionLocal() as db:
            db.query(LlmCallLog).filter(LlmCallLog.created_at < cutoff).delete()
            db.commit()
    except Exception:
        logger.warning("cleanup_llm_call_logs_failed")
