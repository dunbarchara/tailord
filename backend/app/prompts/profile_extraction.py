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
- Add one object per role to work_experience, one per project, one per degree.
- For skills.technical, list specific technologies, tools, and languages.
- For skills.soft, list interpersonal and workplace skills.
- certifications is a list of strings.
- If a field has no data, leave it as "" or [].
- Return only the JSON object. No explanation, no code fences.

JSON TEMPLATE:
{{
  "summary": "",
  "work_experience": [
    {{"title": "", "company": "", "duration": "", "bullets": []}}
  ],
  "skills": {{"technical": [], "soft": []}},
  "education": [{{"degree": "", "institution": "", "year": ""}}],
  "projects": [{{"name": "", "description": "", "technologies": []}}],
  "certifications": []
}}

RESUME:
{resume_text}
"""
