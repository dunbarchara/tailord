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
- For work_experience start_date: normalise the start of the date range to YYYY-MM format (e.g. "2020-01"). Leave null if not determinable.
- For work_experience end_date: normalise the end of the date range to YYYY-MM format (e.g. "2023-04"). Use null if the role is current, ongoing, or "Present".
- For education location: extract city/state of the institution if present. Leave null if not found.
- For education distinction, extract GPA, honours, or academic distinctions if present (e.g. "3.8 GPA · Magna Cum Laude"). Leave null if not found. If the resume line uses "|" or "," to separate the degree name from GPA/honours (e.g. "Bachelor of Science in Computer Science | GPA: 3.8 (Magna Cum Laude)"), put only the degree name in "degree" and put the GPA/honours in "distinction".
- For education degree: extract the credential received (e.g. "Bachelor of Science in Computer Science"). Leave "" if the person attended but no degree or credential is mentioned.
- For education year: extract the graduation or completion date as written (e.g. "Graduated Dec 2017", "May 2019", "2023"). Leave "" if not found.
- For education enrollment_date: normalise the start of studies to YYYY-MM or YYYY. Leave null if not determinable.
- For education completion_date: normalise when attendance ended to YYYY-MM or YYYY — this is neutral and applies whether the person graduated, transferred, or simply stopped attending. Leave null if still ongoing.
- For education status: infer one of "graduated" (degree received), "pursuing" (currently enrolled, no end date), "transferred" (explicit transfer language or attended without degree + has end date at non-final institution), "attended" (attended with dates but no credential mentioned). Leave null if unclear.
- For projects start_date: normalise to YYYY-MM or YYYY. Leave null if not found.
- For projects end_date: normalise to YYYY-MM or YYYY. Use null if the project is ongoing or no end date is stated.
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
    {{"title": "", "company": "", "location": null, "duration": "", "start_date": null, "end_date": null, "bullets": []}}
  ],
  "skills": {{"technical": [], "soft": []}},
  "education": [{{"degree": "", "institution": "", "location": null, "year": "", "enrollment_date": null, "completion_date": null, "status": null, "distinction": null}}],
  "projects": [{{"name": "", "description": "", "technologies": [], "start_date": null, "end_date": null}}],
  "certifications": []
}}

RESUME:
{resume_text}
"""
