import json
from app.clients.llm_client import get_llm_client
from app.config import settings
import logging
logger = logging.getLogger(__name__)


llm_temperature = 0.2


def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences that small LLMs emit despite instructions."""
    text = text.strip()
    if text.startswith("```"):
        text = text[text.index("\n") + 1:]  # drop opening fence line
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    return text.strip()


SEMANTIC_SYSTEM_PROMPT_JOB = """
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


!! YOUR RESPONSE MUST BE VALID JSON ONLY !!
!! DO NOT RETURN CODE FENCES !!
!! DO NOT INCLUDE '```json' IN YOUR RESPONSE !!
"""

SEMANTIC_USER_PROMPT_JOB = """
Fill in this JSON template using information from the job posting below.
Rules:
- Keep all keys exactly as shown.
- Replace empty strings and arrays with extracted values.
- Use null for string fields with no data, [] for list fields with no data.
- skills.technical: specific technologies, tools, languages, frameworks, platforms.
- skills.soft: interpersonal and workplace skills.
- requirements.required vs requirements.preferred: classify based on section headings and phrasing ("must have", "nice to have", etc.).
- Return only the JSON object. No explanation, no code fences.

JSON TEMPLATE:
{{
  "company": null,
  "title": null,
  "responsibilities": [],
  "requirements": {{"required": [], "preferred": []}},
  "skills": {{"technical": [], "soft": []}}
}}

JOB POSTING:
___JOB_MARKDOWN___
"""


def extract_job(job_posting_markdown) -> dict:
    client = get_llm_client()
    prompt = SEMANTIC_USER_PROMPT_JOB.replace("___JOB_MARKDOWN___", job_posting_markdown)
    
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": SEMANTIC_SYSTEM_PROMPT_JOB},
            {"role": "user", "content": prompt}
        ],
        temperature=llm_temperature,
        response_format={"type": "json_object"},
    )
    
    content_job = resp.choices[0].message.content
    logger.debug(f"\n\n===== LLM RESPONSE - JOB ({settings.llm_model}) ({llm_temperature}) =====\n" + str(content_job))

    return json.loads(_strip_json_fences(content_job))


def _format_sourced_profile(sourced_profile: dict) -> str:
    """Format a source-keyed profile dict into labeled blocks for LLM context."""
    source_labels = {
        "resume": "Resume",
        "github": "GitHub",
        "user_input": "Direct Input",
    }
    sections = []
    for key, label in source_labels.items():
        if data := sourced_profile.get(key):
            sections.append(f"[Source: {label}]\n{json.dumps(data, indent=2)}")
    # Include any unknown keys without a label, so future sources aren't silently dropped
    for key, data in sourced_profile.items():
        if key not in source_labels:
            sections.append(f"[Source: {key}]\n{json.dumps(data, indent=2)}")
    return "\n\n".join(sections) if sections else json.dumps(sourced_profile, indent=2)


TAILORING_SYSTEM_PROMPT = """
You are Tailord, an AI that writes sourced advocacy documents on behalf of job candidates.

Rules:
- Write in third person throughout — you are advocating FOR the candidate, never impersonating them.
- Every claim must be traceable to specific evidence in the candidate's profile. If you cannot source a claim, omit it.
- Address the document to the hiring company — make it specific to this role and organization.
- This is NOT a cover letter. Do not use cover letter format or salutations.
- Return valid Markdown only. No preamble, no meta-commentary.
- Include 3–5 fit claims. Each claim gets its own ## section with an evidence citation.
- In each citation, identify both the source type (Resume / GitHub / Direct Input) and the specific detail.
"""

TAILORING_USER_PROMPT = """
Write a sourced candidate advocacy document for {candidate_name} applying to {job_title} at {company}.

CANDIDATE PROFILE (grouped by input source):
{extracted_profile}

JOB REQUIREMENTS:
{extracted_job}

Output format (Markdown):

# {candidate_name} — Application for {job_title} at {company}

## Why {company} should talk to {candidate_name}

[Opening paragraph: compelling third-person case for this candidate in this role. No generic filler.]

## [Specific Fit Claim 1 — e.g., "Production-scale React leadership"]

[2–3 sentences making the sourced case.]

*Source: [Resume / GitHub / Direct Input] — [specific role, project, or repo]*

## [Specific Fit Claim 2]

...

*(3–5 claims total. Only include a claim if it can be sourced from the profile.)*
"""


def generate_tailoring(extracted_profile: dict, extracted_job: dict, candidate_name: str) -> str:
    company = extracted_job.get("company") or "the company"
    job_title = extracted_job.get("title") or "this role"

    prompt = TAILORING_USER_PROMPT.format(
        candidate_name=candidate_name,
        job_title=job_title,
        company=company,
        extracted_profile=_format_sourced_profile(extracted_profile),
        extracted_job=json.dumps(extracted_job, indent=2),
    )

    client = get_llm_client()

    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": TAILORING_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )

    content = resp.choices[0].message.content
    logger.debug(f"\n\n===== LLM RESPONSE - TAILORING ({settings.llm_model}) =====\n" + str(content))
    return content


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

    logger.debug("\n\n===== SEMANTIC_USER_PROMPT_JOB =====\n" + prompt)
    
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=llm_temperature
    )
    
    content_match = resp.choices[0].message.content
    logger.debug(f"\n\n===== LLM RESPONSE - JOB ({settings.llm_model}) ({llm_temperature}) =====\n" + str(content_match))

    return content_match
