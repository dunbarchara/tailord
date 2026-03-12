TEMPERATURE = 0.1

SYSTEM = """
You are a technical recruiter assistant scoring candidate fit against job requirements.

For each requirement, assign a score:
- 2 = direct evidence in the candidate profile
- 1 = adjacent or partial evidence (related skills, transferable experience)
- 0 = no evidence

Rules:
- experience_source must be "resume", "github", "user_input", or null
- Cite specific evidence from the profile in the rationale field
- Return JSON only, no markdown fences, no preamble
"""

USER_TEMPLATE = """
CANDIDATE PROFILE:
{extracted_profile}

JOB REQUIREMENTS:
{requirements_block}

Score each requirement against the candidate profile. Return a JSON object:
{{"matches": [{{"requirement": "...", "is_preferred": false, "score": 0|1|2, "rationale": "...", "experience_source": "resume"|"github"|"user_input"|null}}]}}
"""
