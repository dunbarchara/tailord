"""Label sets and their definitions, written once and used by label-request generation,
scoring, and every adapter (an LLM prompt, or Jev `choice`/`score` criteria).

Definitions copy the production prompt (app/prompts/chunk_matching.py)."""

SEMANTIC_TYPES: dict[str, str] = {
    "job_requirement": "a skill, qualification, or experience requirement the candidate must "
    "demonstrate",
    "role_description": "responsibilities, duties, what the person will do day-to-day",
    "company_description": "information about the company (products, scale, mission, culture, "
    "team)",
    "compensation": "salary range, equity, bonuses, 401K, benefits, PTO",
    "location": "office location, remote/hybrid policy, relocation",
    "application_info": "how to apply, EEO statements, deadlines, contact details",
    "legal": "legal boilerplate, criminal history disclosures, compliance text",
    "other": "anything that doesn't fit the above",
}

# Match score semantics (production scale): -1 not scorable, 0 gap, 1 partial, 2 strong.
MATCH_SCORES: dict[int, str] = {
    -1: "Not a candidate requirement (perk, boilerplate, description); not scored.",
    0: "Gap: the profile contains no explicit evidence for the requirement.",
    1: "Partial: adjacent or limited evidence; does not fully satisfy the requirement.",
    2: "Strong: the profile clearly and explicitly satisfies the requirement.",
}
