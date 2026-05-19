TEMPERATURE = 0.3

SYSTEM = """
You are a professional resume writer. You will be given a structured summary of a
candidate's work history and a pre-computed years-of-experience figure.
Write a professional title, headline, and summary. Return only the JSON object.
"""

USER_TEMPLATE = """Write title, headline, and summary for this candidate.

CANDIDATE EXPERIENCE SUMMARY:
{experience_summary}

PRE-COMPUTED EXPERIENCE: {yoe_label}
(This figure was computed from date intervals — do not recalculate from dates in the resume.)

Rules:
- title: current professional title, 2–5 words, based on most recent role. Null if insufficient info.
- headline: 10–20 words. Must include "{yoe_label}" verbatim. Example format:
  "Senior Software Engineer with {yoe_label} in distributed systems and cloud infrastructure."
  Adapt wording naturally, but the experience figure must appear exactly as shown above.
- summary: 2–3 sentence professional summary synthesised from the experience above. Never leave empty.
- Return only the JSON object. No explanation, no code fences.

JSON TEMPLATE:
{{
  "title": null,
  "headline": null,
  "summary": ""
}}
"""
