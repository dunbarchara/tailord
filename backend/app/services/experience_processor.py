import re
import uuid
from datetime import datetime, timezone

import structlog

from app.clients.storage_client import get_storage_client
from app.models.database import ExperienceSource
from app.services.profile_extractor import extract_profile

logger = structlog.get_logger(__name__)


def _friendly_processing_error(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if "timeout" in name or "timeout" in msg:
        return "Profile extraction timed out — please try again."
    if any(k in name or k in msg for k in ("pdf", "pypdf", "docx", "document", "unsupported")):
        return "Couldn't read this file — try a plain PDF or DOCX."
    if "decode" in msg or "unicode" in msg or "encoding" in msg:
        return "Couldn't read this file — try a plain PDF or DOCX."
    return "Something went wrong while processing your file. Please try uploading again."


_BULLET_MARKER = re.compile(r"^[•\-\*]\s*$")
_BULLET_START = re.compile(r"^[•\-\*]\s+\S")
_SECTION_HEADER = re.compile(r"^[A-Z][A-Za-z\s]{0,30}$")
_TERMINAL_PUNCT = re.compile(r"[.!?:]\s*$")


def _normalize_resume_text(text: str) -> str:
    """
    Normalize raw text extracted from a PDF resume to improve LLM parsing quality.

    Fixes two common PDF extraction artifacts:
    1. Orphaned bullet markers — a bare '•' on its own line, with its content on
       the next non-empty line. Joins them into a single bullet line.
    2. Wrapped bullet continuations — a single bullet whose text wraps across
       multiple lines (with blank lines between), producing fragmented content.
       Continuation lines (those that don't start a new bullet or section header)
       are joined back onto the preceding bullet.

    Also collapses 3+ consecutive blank lines to 2 to reduce noise.
    """
    lines = [line.rstrip() for line in text.splitlines()]

    # Pass 1: merge orphaned bullet markers with the next non-empty line
    merged: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _BULLET_MARKER.match(line.strip()):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                merged.append("• " + lines[j].strip())
                i = j + 1
                continue
        merged.append(line)
        i += 1

    # Pass 2: join wrapped continuation lines back onto their bullet.
    # A blank-line-separated fragment is joined when EITHER:
    #   (a) it starts lowercase  — mid-sentence conjunction/preposition
    #   (b) the previous bullet ends without terminal punctuation — incomplete sentence
    # This handles extractors inserting blank lines mid-bullet (e.g. long lines with
    # parentheticals ending in ')' rather than '.').
    joined: list[str] = []
    pending_blanks: list[str] = []
    for line in merged:
        stripped = line.strip()
        if not stripped:
            pending_blanks.append("")
            continue
        prev_complete = bool(_TERMINAL_PUNCT.search(joined[-1])) if joined else True
        is_continuation = (
            joined
            and _BULLET_START.match(joined[-1].lstrip())
            and not _BULLET_START.match(stripped)
            and not _SECTION_HEADER.match(stripped)
            and (stripped[0].islower() or not prev_complete)
        )
        if is_continuation:
            joined[-1] = joined[-1].rstrip() + " " + stripped
            pending_blanks = []
        else:
            joined.extend(pending_blanks)
            pending_blanks = []
            joined.append(line)
    joined.extend(pending_blanks)

    # Pass 3: collapse 3+ blank lines → 2, collapse runs of spaces within lines
    normalized = re.sub(r"\n{3,}", "\n\n", "\n".join(joined))
    normalized = re.sub(r"[ \t]{2,}", " ", normalized)
    return normalized.strip()


def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"

    if ext == "pdf":
        import fitz  # pymupdf

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page_texts = []
        for page in doc:
            blocks = page.get_text("blocks")
            # Filter to text blocks only (type 0), sort top-to-bottom then left-to-right
            text_blocks = sorted(
                (b for b in blocks if b[6] == 0),
                key=lambda b: (b[1], b[0]),
            )
            page_texts.append("\n".join(b[4].strip() for b in text_blocks if b[4].strip()))
        return "\n\n".join(page_texts)

    elif ext in ("doc", "docx"):
        from io import BytesIO

        from docx import Document

        doc = Document(BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs)

    else:
        return file_bytes.decode("utf-8", errors="replace")


def process_experience(source_id: uuid.UUID, storage_key: str, filename: str) -> None:
    """
    Background task: download file from storage, extract text, run LLM extraction,
    persist structured profile to ExperienceSource. Creates its own DB session since
    the request session is closed by the time background tasks run.
    """
    import time as _time

    from app.metrics import EXPERIENCE_PROCESSING_DURATION_MS, EXPERIENCE_PROCESSING_TOTAL

    _start = _time.perf_counter()

    logger.info(
        "process_experience start: source_id=%s storage_key=%s filename=%s",
        source_id,
        storage_key,
        filename,
    )
    from app.clients.database import SessionLocal

    db = SessionLocal()
    try:
        resume_source = db.get(ExperienceSource, source_id)
        if not resume_source:
            logger.error("ExperienceSource %s not found — aborting background task", source_id)
            return

        try:
            resume_source.sync_status = "syncing"
            db.commit()
            logger.debug("sync_status set to syncing for source %s", source_id)

            logger.debug("Downloading file from blob storage: %s", storage_key)
            file_bytes = get_storage_client().download_bytes(storage_key)
            logger.debug("Downloaded %d bytes, extracting text from %s", len(file_bytes), filename)

            text = extract_text(file_bytes, filename)
            normalized = _normalize_resume_text(text)
            logger.debug(
                "Extracted %d chars from %s, normalized to %d chars, running LLM profile extraction\n--- NORMALIZED TEXT ---\n%s\n--- END ---",
                len(text),
                filename,
                len(normalized),
                normalized[:4000],
            )

            profile = extract_profile(normalized)

            # Refresh to pick up any concurrent writes before merging
            db.refresh(resume_source)
            existing_data = resume_source.source_data or {}
            resume_source.source_data = {
                **existing_data,
                "extracted": profile,
                "raw_text": normalized,
            }
            resume_source.sync_status = "idle"
            resume_source.connection_status = "connected"
            resume_source.last_synced_at = datetime.now(timezone.utc)
            resume_source.error_message = None
            db.commit()
            logger.info("process_experience complete: source_id=%s", source_id)
            EXPERIENCE_PROCESSING_TOTAL.labels(status="success").inc()
            EXPERIENCE_PROCESSING_DURATION_MS.observe(int((_time.perf_counter() - _start) * 1000))

        except Exception as e:
            logger.exception("process_experience failed for source_id=%s: %s", source_id, e)
            resume_source.sync_status = "error"
            resume_source.connection_status = "error"
            resume_source.error_message = _friendly_processing_error(e)
            db.commit()
            EXPERIENCE_PROCESSING_TOTAL.labels(status="error").inc()
            EXPERIENCE_PROCESSING_DURATION_MS.observe(int((_time.perf_counter() - _start) * 1000))

    finally:
        db.close()
        logger.debug("DB session closed for source_id=%s", source_id)
