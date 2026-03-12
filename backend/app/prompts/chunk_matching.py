TEMPERATURE = 0.1

SYSTEM = """
You are evaluating job posting chunks against a candidate profile.

For each chunk, assign a score:
- 2  = strong match — candidate has direct, demonstrable evidence for this item
- 1  = partial match — candidate has adjacent, transferable, or related experience
- 0  = gap — this is a real requirement but the candidate lacks evidence for it
- -1 = non-evaluable — boilerplate, EEO statement, benefits, company description, or any chunk that is not a requirement or qualification

Rules:
- Every chunk must have a rationale. For 0 (gap), explain what is missing. For -1, briefly note why it is non-evaluable.
- experience_source must be "resume", "github", "user_input", or null. Set to null for score -1 or 0.
- Return JSON only, no markdown fences, no preamble.
- The number of results must exactly match the number of input chunks.
"""

USER_TEMPLATE = """
CANDIDATE PROFILE:
{extracted_profile}

SECTION: {section}

CHUNKS:
{chunks_block}

Score each chunk. Return a JSON object with exactly as many results as chunks:
{{"results": [{{"score": 2|1|0|-1, "rationale": "...", "experience_source": "resume"|"github"|"user_input"|null}}]}}
"""
