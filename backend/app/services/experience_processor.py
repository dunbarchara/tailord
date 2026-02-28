import json
import logging
import uuid
from datetime import datetime, timezone

from app.clients.llm_client import get_llm_client
from app.clients.s3_client import download_file_bytes
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
"""


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
    return json.loads(content)


def process_experience(experience_id: uuid.UUID, s3_key: str, filename: str) -> None:
    """
    Background task: download file from S3, extract text, run LLM extraction,
    persist structured profile to DB. Creates its own DB session (request session
    is closed by the time background tasks run).
    """
    from app.clients.database import SessionLocal

    db = SessionLocal()
    try:
        experience = db.get(Experience, experience_id)
        if not experience:
            logger.error(f"Experience {experience_id} not found for processing")
            return

        try:
            experience.status = "processing"
            db.commit()

            file_bytes = download_file_bytes(s3_key)
            text = extract_text(file_bytes, filename)
            profile = extract_profile(text)

            experience.extracted_profile = {"resume": profile}
            experience.status = "ready"
            experience.processed_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(f"Experience {experience_id} processed successfully")

        except Exception as e:
            logger.exception(f"Failed to process experience {experience_id}: {e}")
            experience.status = "error"
            experience.error_message = str(e)
            db.commit()

    finally:
        db.close()
