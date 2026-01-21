import json
from app.clients.llm_client import get_llm_client
from app.config import settings
import logging
logger = logging.getLogger(__name__)

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
  "summary": string|null,
  "employment": {"type":"full_time"|"part_time"|"contract"|null,"level":"junior"|"mid"|"senior"|null,"contract_length_months":int|null},
  "location": {"workplace_type":string|null,"primary_location":string|null,"eligible_regions":string[]},
  "compensation": {"currency":string|null,"min":int|null,"max":int|null,"frequency":string|null,"equity":bool|null},
  "title": string|null,
  "company": {"name":string|null,"department":string|null},
  "responsibilities": string[],
  "requirements": {"required":string[],"preferred":string[]},
  "skills": {"technical":string[],"soft":string[]},
  "qualifications": {"education":string|null,"certifications":string[]},
  "application": {"apply_url":string|null,"deadline":string|null},
  "benefits": string[]
}

JOB POSTING MARKDOWN:

```
___JOB_MARKDOWN___
```

Instructions:
- Return JSON matching the schema; null or [] for missing fields.
- Do not add extra fields or explanations.
- For "summary":
    - Use the first paragraph under "About Us", "Company", or job description if present.
    - If none exists, use the first descriptive paragraph of the posting.
    - Only use null if there is no descriptive text.
- Normalize skills and responsibilities for clarity.
- Treat markdown headings as section titles and bullets as items.
- Include all technologies/tools mentioned in the correct skill sections.
"""


def extract_semantic(job_posting_markdown: str) -> dict:

    client = get_llm_client()
    prompt = SEMANTIC_USER_PROMPT.replace("___JOB_MARKDOWN___", job_posting_markdown)
    
    logger.debug("\n\n===== SEMANTIC_SYSTEM_PROMPT =====\n" + SEMANTIC_SYSTEM_PROMPT)
    logger.debug("\n\n===== SEMANTIC_USER_PROMPT =====\n" + prompt)
    
    llm_temperature = 0.2

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": SEMANTIC_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=llm_temperature,
    )
    
    parsedJson = json.loads(response.choices[0].message.content)
    logger.debug(f"\n\n===== LLM RESPONSE ({settings.llm_model}) ({llm_temperature}) =====\n" + str(parsedJson))

    return parsedJson
