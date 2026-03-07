import json
import logging
import uuid
from datetime import datetime, timezone

from app.clients.llm_client import get_llm_client
from app.clients.storage_client import get_storage_client
from app.config import settings
from app.models.database import Experience

logger = logging.getLogger(__name__)

EXTRACT_SYSTEM_PROMPT = """
You are an AI expert in parsing resumes. Extract structured information from the resume text and return **only valid JSON**, strictly following this schema:

{
  "summary": "prose overview of candidate",
  "work_experience": [
    {"title": "", "company": "", "duration": "", "bullets": []}
  ],
  "skills": {"technical": [], "soft": []},
  "education": [{"degree": "", "institution": "", "year": ""}],
  "projects": [{"name": "", "description": "", "technologies": []}],
  "certifications": []
}

**IMPORTANT RULES:**
1. Output **only JSON**. Do **not** include explanations, text, notes, or markdown.
2. Do **not** use ```json, ``` or any code fences.
3. Do **not** add any line breaks, headings, or extra formatting.
4. If a field is empty, return `""` for strings and `[]` for arrays.
5. Any violation will be treated as invalid output.

**Return JSON exactly as shown above. Nothing else.**
!! YOUR RESPONSE MUST BE VALID JSON ONLY !!
!! DO NOT RETURN CODE FENCES !!
!! DO NOT INCLUDE '```json' IN YOUR RESPONSE !!
"""


def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences that small LLMs emit despite instructions."""
    text = text.strip()
    if text.startswith("```"):
        text = text[text.index("\n") + 1:]
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    return text.strip()


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


def extract_profile(text: str) -> dict:
    logger.debug("Running LLM profile extraction (model=%s, text_len=%d)", settings.llm_model, len(text))
    client = get_llm_client()
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=0.1,
    )
    content = response.choices[0].message.content
    logger.debug("LLM profile extraction complete (response_len=%d)", len(content or ""))
    logger.debug(content)
    return json.loads(_strip_json_fences(content))


def process_experience(experience_id: uuid.UUID, storage_key: str, filename: str) -> None:
    """
    Background task: download file from Azure Blob Storage, extract text, run LLM
    extraction, persist structured profile to DB. Creates its own DB session since
    the request session is closed by the time background tasks run.
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
            experience.error_message = str(e)
            db.commit()

    finally:
        db.close()
        logger.debug("DB session closed for experience_id=%s", experience_id)
