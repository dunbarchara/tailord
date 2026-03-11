import logging
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


def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"

    if ext == "pdf":
        from pypdf import PdfReader
        from io import BytesIO
        reader = PdfReader(BytesIO(file_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    elif ext in ("doc", "docx"):
        from docx import Document
        from io import BytesIO
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
    logger.info("process_experience start: experience_id=%s storage_key=%s filename=%s",
                experience_id, storage_key, filename)
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
            logger.debug("Extracted %d chars of text, running LLM profile extraction", len(text))

            profile = extract_profile(text)

            experience.extracted_profile = {"resume": profile}
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
