import os
from app.clients.llm_client import get_llm_client
from app.config import settings
import logging
logger = logging.getLogger(__name__)


llm_temperature = 0.2

def extract_profile(resume_text, repos):
    prompt = f"""
Extract a concise software engineer profile.

Resume:
{resume_text}

GitHub Repos:
{repos}

Return JSON with:
- summary
- key_skills
- notable_projects
"""
    
    client = get_llm_client()
    
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=llm_temperature
    )
    
    content_profile = resp.choices[0].message.content
    logger.debug(f"\n\n===== LLM RESPONSE - PROFILE ({settings.llm_model}) ({llm_temperature}) =====\n" + str(content_profile))

    return content_profile




SEMANTIC_SYSTEM_PROMPT = """
You are an AI expert in extracting structured job posting data. Return only a JSON object matching the canonical schema.

Rules:
- Return valid JSON only; no markdown or explanations.
- Use null for missing scalar fields, [] for missing lists.
- Normalize skills and responsibilities for clarity.
- Separate required vs preferred qualifications, technical vs soft skills.
- If unsure about a field, leave it null/empty.

Requirements classification:
- Preferred phrases: "nice to have", "preferred", "bonus", "pluses", "helpful but not required", "optional", "not required"
- Required phrases: "required", "must have", "minimum qualifications", "basic qualifications", "you must", "we require", "requirements"
- If a qualification appears under a preferred-labeled section, place it in requirements.preferred.

Technical skills:
- Include all explicit technologies, tools, languages, frameworks, cloud providers, and platforms.
- Treat proper nouns and branded tools as technical skills (AWS, Cloudflare, Terraform, TypeScript, React, Kubernetes).
- Do not generalize; extract exact names even outside Skills sections.
- Deduplicate while preserving capitalization.

"""

SEMANTIC_USER_PROMPT = """
Extract job data from the following job posting in JSON matching this schema:

{
  "title": string|null,
  "responsibilities": string[],
  "requirements": {"required":string[],"preferred":string[]},
  "skills": {"technical":string[],"soft":string[]},
}

JOB POSTING MARKDOWN:

```
___JOB_MARKDOWN___
```

Instructions:
- Return JSON matching the schema; null or [] for missing fields.
- Do not add extra fields or explanations.
- Normalize skills and responsibilities for clarity.
- Treat markdown headings as section titles and bullets as items.
- Include all technologies/tools mentioned in the correct skill sections.
"""


def extract_job(job_posting_markdown):
    client = get_llm_client()
    prompt = SEMANTIC_USER_PROMPT.replace("___JOB_MARKDOWN___", job_posting_markdown)
    
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": SEMANTIC_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=llm_temperature
    )
    
    content_job = resp.choices[0].message.content
    logger.debug(f"\n\n===== LLM RESPONSE - JOB ({settings.llm_model}) ({llm_temperature}) =====\n" + str(content_job))

    return content_job


def generate_match(profile, job):
    prompt = f"""
You are a technical recruiter assistant.

USER PROFILE:
{profile}

JOB:
{job}

Write a concise paragraph explaining why the user is a strong fit.
Only use information from the profile.
"""
    client = get_llm_client()

    logger.debug("\n\n===== SEMANTIC_USER_PROMPT =====\n" + prompt)
    
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=llm_temperature
    )
    
    content_match = resp.choices[0].message.content
    logger.debug(f"\n\n===== LLM RESPONSE - JOB ({settings.llm_model}) ({llm_temperature}) =====\n" + str(content_match))

    return content_match
