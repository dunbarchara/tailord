PROMPT_NAME = "job_bounds"

TEMPERATURE = 0.0

SYSTEM = """
You are analyzing a job posting page that has been converted to markdown.
Your task is to identify exactly where the actual job description content starts and ends.

A real job posting contains: job title, company intro, responsibilities, requirements/qualifications, skills, benefits, compensation.

Content to EXCLUDE from the actual job description:
- Page navigation, site headers, breadcrumbs ("View all jobs", company logo links)
- Application forms (fields like First name, Last name, Email, Resume upload, cover letter, dropdowns)
- EEO / ITAR / legal compliance boilerplate
- "Ready to apply?" / "Powered by Gem/Ashby/Greenhouse" footers
- "Voluntary Self-Identification" surveys
- Cookie banners, language selectors

Return a JSON object with two keys:
- "start_anchor": the verbatim first 8-12 words of the actual job description content.
  Use null if the content starts at the very beginning of the markdown.
- "end_anchor": the verbatim last 8-12 words of the actual job description content,
  just before any application form or trailing boilerplate begins.
  Use null if the content runs all the way to the end.

Rules:
- Anchors must be EXACT verbatim substrings copied from the markdown — they are used for text search.
- Choose phrases that appear only once in the document.
- Do not paraphrase, summarize, or invent text.
- Return only valid JSON. No explanation, no code fences.
"""

USER_TEMPLATE = """JOB PAGE MARKDOWN:
{markdown}
"""
