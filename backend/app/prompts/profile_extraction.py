PROMPT_NAME = "resume_structure_extraction"

TEMPERATURE = 0.1

SYSTEM = """
You are a resume parser. You will be given a resume and a JSON template.
Fill in the template with information extracted from the resume.
Return only the completed JSON object. Do not add any text outside the JSON.
"""

USER_TEMPLATE = """Fill in this JSON template using information from the resume below.
Rules:
- Keep all keys exactly as shown.
- Replace empty strings and arrays with extracted values.
- Add one object per role to work_experience, one per degree.
- For work_experience, extract every bullet point verbatim — do not summarise, skip, or truncate any bullet. Each bullet must be plain text with no leading bullet character (•, -, *, –, etc.).
- For work_experience title: use the explicit job title if given. If no title is stated (e.g. a sub-team or division is listed), infer the most appropriate title from context (e.g. "Software Engineer").
- For work_experience company: include the employer and team/division if relevant (e.g. "Microsoft – Azure IoT Solutions").
- For work_experience location: extract city/state or remote if present (e.g. "New York, NY"). Leave null if not found.
- For work_experience duration: extract the date range exactly as written (e.g. "Jan 2020 – Apr 2023"). Do not normalise or reformat.
- For education location: extract city/state of the institution if present. Leave null if not found.
- For education distinction, extract GPA, honours, or academic distinctions if present (e.g. "3.8 GPA · Magna Cum Laude"). Leave null if not found.
- For skills.technical, list specific technologies, tools, and languages.
- For skills.soft, list interpersonal and workplace skills.
- certifications is a list of strings.
- For email, extract the candidate's contact email address if present. Leave null if not found.
- For phone, extract the candidate's phone number if present. Leave null if not found.
- For linkedin, extract the LinkedIn profile URL or handle if present (e.g. "linkedin.com/in/username"). Leave null if not found.
- For location, extract the candidate's city and state or country (e.g. "New York, NY"). Leave null if not found.
- For projects: only populate from an explicitly labeled "Projects", "Side Projects", or "Personal Projects" section. Do NOT infer or extract projects from work experience bullets, even if a bullet describes a named system or product. If no such section exists, return [].
- If a field has no data, leave it as "", null, or [].
- Return only the JSON object. No explanation, no code fences.

JSON TEMPLATE:
{{
  "email": null,
  "phone": null,
  "linkedin": null,
  "location": null,
  "work_experience": [
    {{"title": "", "company": "", "location": null, "duration": "", "bullets": []}}
  ],
  "skills": {{"technical": [], "soft": []}},
  "education": [{{"degree": "", "institution": "", "location": null, "year": "", "distinction": null}}],
  "projects": [],
  "certifications": []
}}

RESUME:
{resume_text}
"""
