import logging
import re
import uuid
from datetime import datetime, timezone

from app.clients.storage_client import get_storage_client
from app.models.database import Experience
from app.services.profile_extractor import extract_profile

logger = logging.getLogger(__name__)


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


def _normalize_resume_text(text: str) -> str:
    """
    Normalize raw text extracted from a PDF resume to improve LLM parsing quality.

    Fixes two common pypdf artifacts:
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

    # Pass 2: join wrapped continuation lines back onto their bullet
    joined: list[str] = []
    for line in merged:
        stripped = line.strip()
        if not stripped:
            joined.append("")
            continue
        if (
            joined
            and joined[-1].strip()
            and _BULLET_START.match(joined[-1].lstrip())
            and not _BULLET_START.match(stripped)
            and not _SECTION_HEADER.match(stripped)
        ):
            joined[-1] = joined[-1].rstrip() + " " + stripped
        else:
            joined.append(line)

    # Pass 3: collapse 3+ blank lines → 2, collapse runs of spaces within lines
    normalized = re.sub(r"\n{3,}", "\n\n", "\n".join(joined))
    normalized = re.sub(r"[ \t]{2,}", " ", normalized)
    return normalized.strip()


def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"

    if ext == "pdf":
        from io import BytesIO

        from pdfminer.high_level import extract_text as pdfminer_extract

        return pdfminer_extract(BytesIO(file_bytes))

    elif ext in ("doc", "docx"):
        from io import BytesIO

        from docx import Document

        doc = Document(BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs)

    else:
        return file_bytes.decode("utf-8", errors="replace")


def process_experience(experience_id: uuid.UUID, storage_key: str, filename: str) -> None:
    """
    Background task: download file from storage, extract text, run LLM extraction,
    persist structured profile to DB. Creates its own DB session since the request
    session is closed by the time background tasks run.
    """
    logger.info(
        "process_experience start: experience_id=%s storage_key=%s filename=%s",
        experience_id,
        storage_key,
        filename,
    )
    from app.clients.database import SessionLocal

    db = SessionLocal()
    try:
        experience = db.get(Experience, experience_id)
        if not experience:
            logger.error("Experience %s not found — aborting background task", experience_id)
            return

        try:
            experience.status = "processing"
            db.commit()
            logger.debug("Status set to processing for experience %s", experience_id)

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

            # Refresh to pick up any concurrent writes (e.g. GitHub enrichment
            # data written while the LLM was running) before merging.
            db.refresh(experience)
            experience.raw_resume_text = normalized
            experience.extracted_profile = {
                **(experience.extracted_profile or {}),
                "resume": profile,
            }
            experience.status = "ready"
            experience.processed_at = datetime.now(timezone.utc)
            db.commit()
            logger.info("process_experience complete: experience_id=%s", experience_id)

        except Exception as e:
            logger.exception("process_experience failed for experience_id=%s: %s", experience_id, e)
            experience.status = "error"
            experience.error_message = _friendly_processing_error(e)
            db.commit()

    finally:
        db.close()
        logger.debug("DB session closed for experience_id=%s", experience_id)
