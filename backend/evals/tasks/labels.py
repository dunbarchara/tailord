"""Label sets and their definitions, written once and used by label-request generation,
scoring, and every adapter (an LLM prompt, or Jev `choice`/`score` criteria).

Definitions mirror the production prompt (app/prompts/chunk_matching.py)."""

SEMANTIC_TYPES: dict[str, str] = {
    "job_requirement": "A qualification, skill, experience level, or responsibility the "
    "candidate is expected to have or perform.",
    "role_description": "What the role does day to day, team context, or the mission of the "
    "position, without stating a candidate requirement.",
    "company_description": "About the company: mission, product, history, culture, values.",
    "compensation": "Salary, equity, bonus, benefits, perks, or other compensation information.",
    "location": "Office location, remote or hybrid policy, travel, or work authorization by place.",
    "application_info": "How to apply, hiring process, deadlines, recruiter contact, or other "
    "page chrome unrelated to the job itself.",
    "legal": "Equal opportunity statements, privacy notices, and other legal boilerplate.",
    "other": "Anything that fits none of the above.",
}

# Match score semantics (production scale): -1 not scorable, 0 gap, 1 partial, 2 strong.
MATCH_SCORES: dict[int, str] = {
    -1: "Not a candidate requirement (perk, boilerplate, description); not scored.",
    0: "Gap: the profile contains no explicit evidence for the requirement.",
    1: "Partial: adjacent or limited evidence; does not fully satisfy the requirement.",
    2: "Strong: the profile clearly and explicitly satisfies the requirement.",
}
