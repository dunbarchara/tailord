import json
import re
from datetime import date

from app.clients.llm_client import get_llm_client
from app.config import settings
from app.core.llm_utils import llm_parse
from app.prompts import tailoring as prompt
from app.schemas.llm_outputs import TailoringContent

_MONTH_ABBR = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _parse_duration_date(token: str) -> date | None:
    """Parse a single date token from a duration string into a date object."""
    t = token.strip().lower()
    if t in ("present", "current", "now", "today"):
        return date.today()
    # MM/YYYY or MM-YYYY
    m = re.match(r"^(\d{1,2})[/-](\d{4})$", t)
    if m:
        return date(int(m.group(2)), int(m.group(1)), 1)
    # Mon YYYY (e.g. "Jan 2020")
    m = re.match(r"^([a-z]{3})\s+(\d{4})$", t)
    if m and m.group(1) in _MONTH_ABBR:
        return date(int(m.group(2)), _MONTH_ABBR[m.group(1)], 1)
    # YYYY only
    m = re.match(r"^(\d{4})$", t)
    if m:
        return date(int(m.group(1)), 1, 1)
    return None


def _parse_duration_years(duration: str) -> float:
    """Return fractional years for a duration string like '01/2020 - 04/2023'."""
    # Split on ' - ', ' – ', ' — ', ' to '
    parts = re.split(r"\s*[-–—]\s*|\s+to\s+", duration.strip(), maxsplit=1)
    if len(parts) != 2:
        return 0.0
    start = _parse_duration_date(parts[0])
    end = _parse_duration_date(parts[1])
    if not start or not end or end < start:
        return 0.0
    delta = (end - start).days / 365.25
    return round(delta, 2)


def _compute_profile_signals(sourced_profile: dict) -> str:
    """
    Pre-compute factual signals that LLMs routinely miscalculate:
      - Total years of professional experience (summed across all roles)
      - Chronological role list

    Returns a compact string block prepended to the formatted profile so that
    scoring and matching prompts can reference pre-computed facts rather than
    doing date arithmetic themselves.
    """
    resume = sourced_profile.get("resume") or {}
    roles = resume.get("work_experience") or []

    total_years = 0.0
    role_lines = []
    for role in roles:
        title = role.get("title", "")
        company = role.get("company", "")
        duration = role.get("duration", "")
        years = _parse_duration_years(duration) if duration else 0.0
        total_years += years
        label = f"{title} @ {company}" if company else title
        role_lines.append(f"  - {label} ({duration})" + (f" [{years:.1f} yrs]" if years else ""))

    lines = [f"Total professional experience: {total_years:.1f} years"]
    if role_lines:
        lines.append("Roles (chronological):")
        lines.extend(role_lines)

    github = sourced_profile.get("github") or {}
    repos = github.get("repos") or []
    if repos:
        lines.append(f"GitHub repos: {len(repos)} imported")

    return "\n".join(lines)


def _format_sourced_profile(
    sourced_profile: dict,
    candidate_name: str | None = None,
    pronouns: str | None = None,
) -> str:
    """Format a source-keyed profile dict into labeled blocks for LLM context.

    Prepends a CANDIDATE block (name + pronouns) and a COMPUTED SIGNALS block
    so all LLM calls have consistent candidate context without requiring each
    service to manage it independently.
    """
    source_labels = {
        "resume": "Resume",
        "github": "GitHub",
        "user_input": "Direct Input",
    }

    sections = []

    if candidate_name or pronouns:
        candidate_lines = []
        if candidate_name:
            candidate_lines.append(f"Name: {candidate_name}")
        if pronouns:
            candidate_lines.append(
                f"Pronouns: {pronouns} — use these when referring to the candidate in third person."
            )
        sections.append("[CANDIDATE]\n" + "\n".join(candidate_lines))

    signals = _compute_profile_signals(sourced_profile)
    sections.append(f"[COMPUTED SIGNALS — treat as ground truth]\n{signals}")

    for key, label in source_labels.items():
        if data := sourced_profile.get(key):
            sections.append(f"[Source: {label}]\n{json.dumps(data, indent=2)}")
    for key, data in sourced_profile.items():
        if key not in source_labels:
            sections.append(f"[Source: {key}]\n{json.dumps(data, indent=2)}")
    return "\n\n".join(sections) if sections else json.dumps(sourced_profile, indent=2)


def _format_ranked_matches(matches: list[dict]) -> str:
    """Format pre-scored requirement matches into a labeled block for the LLM."""
    if not matches:
        return "(No pre-scored matches available — write claims based on the candidate profile and job context.)"

    score_labels = {2: "STRONG", 1: "PARTIAL"}
    source_labels = {"resume": "Resume", "github": "GitHub", "user_input": "Direct Input"}

    lines = []
    for match in matches:
        score = match.get("score", 0)
        score_label = score_labels.get(score, "PARTIAL")
        req = match.get("requirement", "")
        is_preferred = match.get("is_preferred", False)
        req_label = "Preferred" if is_preferred else "Required"
        rationale = match.get("rationale", "")
        source_key = match.get("experience_source")
        source_label = source_labels.get(source_key, source_key) if source_key else None

        header = f'[{score_label}] {req_label}: "{req}"'
        if source_label and rationale:
            detail = f"  → {source_label} — {rationale}"
        elif rationale:
            detail = f"  → {rationale}"
        elif source_label:
            detail = f"  → {source_label}"
        else:
            detail = None

        lines.append(header)
        if detail:
            lines.append(detail)

    return "\n".join(lines)


def _strip_city(institution: str) -> str:
    """Remove trailing city/state from institution names.

    Handles common delimiters: comma, em dash, en dash, hyphen with spaces.
    e.g. 'University of Arizona, Tucson, AZ'
         'University of Arizona — Tucson, AZ'
         'University of Arizona - Tucson'
    """
    return re.split(r"\s*[,—–·•]\s*|\s+-\s+", institution, maxsplit=1)[0].strip()


def _render_tailoring(
    content: TailoringContent,
    candidate_name: str,
    candidate_email: str | None,
    candidate_linkedin: str | None,
    candidate_title: str | None,
    company: str,
    job_title: str,
    job_url: str | None = None,
) -> str:
    """Deterministically render a TailoringContent object into the final markdown document."""
    first_name = candidate_name.split()[0] if candidate_name else candidate_name
    job_title_md = f"[{job_title}]({job_url})" if job_url else job_title

    lines: list[str] = []

    # Greeting + opening sentence
    lines += [
        f"Hello **{company}**,",
        "",
        f"Given the requirements in your {job_title_md} job posting, here are some reasons **{candidate_name}** would be a strong fit for the role.",
        "",
        "---",
        "",
    ]

    # Advocacy sections
    for stmt in content.advocacy_statements:
        source_tag = " ".join(f"[{s}]" for s in stmt.sources) if stmt.sources else ""
        body = f"{stmt.body} *{source_tag}*".strip()
        lines += [f"**{stmt.header}**", "", body, ""]

    lines += ["---", ""]

    # Closing: LLM synthesis + deterministic contact line
    closing = content.closing.rstrip()
    if candidate_email:
        lines += [closing, ""]
        lines.append(
            f"If you're interested in continuing the conversation, {first_name} can be reached at [{candidate_email}](mailto:{candidate_email})."
        )
    else:
        lines.append(closing)

    lines += ["", "---", ""]

    # Candidate brief footer
    brief_parts = [candidate_name]
    if candidate_title:
        brief_parts.append(candidate_title)
    if candidate_email:
        brief_parts.append(f"[{candidate_email}](mailto:{candidate_email})")
    if candidate_linkedin:
        linkedin_url = (
            candidate_linkedin
            if candidate_linkedin.startswith("http")
            else f"https://{candidate_linkedin}"
        )
        brief_parts.append(f"[LinkedIn]({linkedin_url})")
    lines.append(f"*{' · '.join(brief_parts)}*")

    return "\n".join(lines)


def generate_tailoring(
    extracted_profile: dict,
    extracted_job: dict,
    candidate_name: str,
    ranked_matches: list[dict] | None = None,
    job_url: str | None = None,
    pronouns: str | None = None,
) -> str:
    company = extracted_job.get("company") or "the company"
    job_title = extracted_job.get("title") or "this role"
    resume = extracted_profile.get("resume") or {}
    candidate_email: str | None = resume.get("email") or None
    candidate_linkedin: str | None = resume.get("linkedin") or None

    ranked_matches_block = _format_ranked_matches(
        ranked_matches if ranked_matches is not None else []
    )

    content = llm_parse(
        get_llm_client(),
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": prompt.SYSTEM},
            {
                "role": "user",
                "content": prompt.USER_TEMPLATE.format(
                    candidate_name=candidate_name,
                    job_title=job_title,
                    company=company,
                    ranked_matches_block=ranked_matches_block,
                    extracted_profile=_format_sourced_profile(
                        extracted_profile, candidate_name=candidate_name, pronouns=pronouns
                    ),
                ),
            },
        ],
        response_model=TailoringContent,
        temperature=prompt.TEMPERATURE,
    )

    return _render_tailoring(
        content=content,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        candidate_linkedin=candidate_linkedin,
        candidate_title=resume.get("title") or None,
        company=company,
        job_title=job_title,
        job_url=job_url,
    )
