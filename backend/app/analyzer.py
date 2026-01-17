# backend/app/analyzer.py
import json
from app.llm_client import get_llm_client
from app.config import settings

def analyze_job(text: str) -> dict:
    client = get_llm_client()

    prompt = f"""
STRICT INSTRUCTIONS:
- Output MUST be valid JSON
- No markdown
- No ```json
- No text before or after JSON
- Use double quotes only
- Arrays must contain strings only

If a field cannot be determined, return an empty array or empty string.

JSON Schema:
{{
  "job_title": "",
  "seniority_level": "",
  "required_skills": [],
  "preferred_skills": [],
  "soft_skills": [],
  "responsibilities": [],
  "qualifications": []
}}

JOB DESCRIPTION:
{text}
"""

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return json.loads(response.choices[0].message.content)
