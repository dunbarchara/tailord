from typing import Literal

from pydantic import BaseModel

PROMPT_NAME = "github_pr_extraction"
TEMPERATURE = 0.1


class ClaimDraft(BaseModel):
    content: str  # ≤25 words, first person, past tense, outcome-focused
    claim_type: Literal["work_experience", "skill", "project", "other"]
    confidence: Literal["high", "medium", "low"]
    technologies: list[str]
    pillar: str | None = None  # nullable — for future competency pillar classification


class PRClaimExtractionResult(BaseModel):
    claims: list[ClaimDraft]
    skip_reason: str | None = None  # non-null if PR has no claimable content


SYSTEM = """
You are a professional experience analyst. You extract concrete, first-person experience
claims from GitHub pull request data. Each claim should describe an observable achievement
or outcome — not implementation details or internal architecture.

Rules for claims:
- First person, past tense (e.g. "Implemented", "Reduced", "Migrated")
- One claim per sentence, ≤25 words
- Describe what was accomplished, not how the code works internally
- No internal file names, function names, or architecture specifics
- No generic statements ("Fixed a bug", "Improved performance") without specific context
- technologies captures the stack; content describes the outcome

Confidence mapping:
- "high" — PR body explicitly states outcome with measurable or specific detail
- "medium" — clear description of what was done, no quantified outcome
- "low" — title only; body absent or generic

Return skip_reason (non-null string, claims=[]) for:
- Dependency bumps / version upgrades with no functional change
- Reverts (e.g. "Revert #123")
- Documentation-only changes (typo fixes, README updates, comment edits)
- No-body PRs with only generic commit messages ("Update", "Fix", "WIP")
- Bot-authored PRs or automated changes

Return only valid JSON matching the schema. No preamble, no code fences, no commentary.
"""

USER_TEMPLATE = """Extract experience claims from this merged pull request.

REPOSITORY: {repo}
PR #{pr_number}: {pr_title}

PR BODY:
{pr_body}

USER'S COMMIT MESSAGES (first line only, author-filtered):
{commit_messages}

LABELS: {labels}

Return JSON matching this schema exactly:
{{
  "claims": [
    {{
      "content": "First-person, past-tense claim ≤25 words describing outcome",
      "claim_type": "work_experience | skill | project | other",
      "confidence": "high | medium | low",
      "technologies": ["Framework", "Tool", "Language"],
      "pillar": null
    }}
  ],
  "skip_reason": null
}}

If the PR has no claimable content, return:
{{
  "claims": [],
  "skip_reason": "brief reason (e.g. dependency bump, doc-only, revert)"
}}
"""
