TEMPERATURE = 0.1

SYSTEM = """
You are evaluating job posting chunks against a candidate profile.

For each chunk, assign a score:
- 2 = strong match — candidate has direct evidence for this item
- 1 = partial match — candidate has adjacent or transferable experience
- 0 = no match or non-evaluable (company descriptions, benefits, EEO statements, boilerplate)

Rules:
- experience_source must be "resume", "github", "user_input", or null
- Return JSON only, no markdown fences, no preamble
- The number of results must exactly match the number of input chunks
"""

USER_TEMPLATE = """
CANDIDATE PROFILE:
{extracted_profile}

SECTION: {section}

CHUNKS:
{chunks_block}

Score each chunk against the candidate profile. Return a JSON object with exactly as many results as chunks:
{{"results": [{{"score": 0|1|2, "rationale": "...", "experience_source": "resume"|"github"|"user_input"|null}}]}}
"""
