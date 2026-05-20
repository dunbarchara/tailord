"""
profile_formatter.py — shared profile formatting utilities.

Moved from tailoring_generator.py. These helpers are used by multiple
services (chunk_matcher, requirement_matcher, gap_analyzer, tailorings API)
and were awkwardly private (_format_sourced_profile) despite being shared.
Public names are used throughout.
"""

import json
import re
from datetime import date

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


def parse_duration_date(token: str) -> date | None:
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


def parse_duration_years(duration: str) -> float:
    """Return fractional years for a duration string like '01/2020 - 04/2023'."""
    # Split on ' - ', ' – ', ' — ', ' to '
    parts = re.split(r"\s*[-–—]\s*|\s+to\s+", duration.strip(), maxsplit=1)
    if len(parts) != 2:
        return 0.0
    start = parse_duration_date(parts[0])
    end = parse_duration_date(parts[1])
    if not start or not end or end < start:
        return 0.0
    delta = (end - start).days / 365.25
    return round(delta, 2)


def merge_intervals(intervals: list[tuple[date, date]]) -> list[tuple[date, date]]:
    """Merge overlapping date intervals into non-overlapping spans."""
    if not intervals:
        return []
    sorted_ivs = sorted(intervals, key=lambda iv: iv[0])
    merged: list[tuple[date, date]] = [sorted_ivs[0]]
    for start, end in sorted_ivs[1:]:
        cur_start, cur_end = merged[-1]
        if start <= cur_end:
            merged[-1] = (cur_start, max(cur_end, end))
        else:
            merged.append((start, end))
    return merged


def compute_profile_signals(sourced_profile: dict) -> str:
    """
    Pre-compute factual signals that LLMs routinely miscalculate:
      - Total years of professional experience (overlap-aware merge of all roles)
      - Chronological role list

    Returns a compact string block prepended to the formatted profile so that
    scoring and matching prompts can reference pre-computed facts rather than
    doing date arithmetic themselves.
    """
    resume = sourced_profile.get("resume") or {}
    roles = resume.get("work_experience") or []

    intervals: list[tuple[date, date]] = []
    role_lines = []
    for role in roles:
        title = role.get("title", "")
        company = role.get("company", "")
        duration = role.get("duration", "")
        years = parse_duration_years(duration) if duration else 0.0
        label = f"{title} @ {company}" if company else title
        role_lines.append(f"  - {label} ({duration})" + (f" [{years:.1f} yrs]" if years else ""))
        if duration:
            parts = re.split(r"\s*[-–—]\s*|\s+to\s+", duration.strip(), maxsplit=1)
            if len(parts) == 2:
                start = parse_duration_date(parts[0])
                end = parse_duration_date(parts[1])
                if start and end and end >= start:
                    intervals.append((start, end))

    merged = merge_intervals(intervals)
    total_years = round(sum((end - start).days / 365.25 for start, end in merged), 2)

    corrections = sourced_profile.get("corrections") or {}
    if (override := corrections.get("yoe_override")) is not None:
        total_years = override

    lines = [f"Total professional experience: {total_years:.1f} years"]
    if role_lines:
        lines.append("Roles (chronological):")
        lines.extend(role_lines)

    github = sourced_profile.get("github") or {}
    repos = github.get("repos") or []
    if repos:
        lines.append(f"GitHub repos: {len(repos)} imported")

    return "\n".join(lines)


def fmt_resume_prose(data: dict) -> str:
    """Render an ExtractedProfile dict as compact prose — significantly fewer tokens than JSON."""
    lines: list[str] = []

    # Identity line
    identity_parts = [p for p in [data.get("title"), data.get("location")] if p]
    contact_parts = [p for p in [data.get("email"), data.get("linkedin")] if p]
    if identity_parts:
        lines.append(" | ".join(identity_parts))
    if contact_parts:
        lines.append("Contact: " + " | ".join(contact_parts))

    if summary := (data.get("summary") or "").strip():
        lines += ["", f"Summary: {summary}"]

    skills = data.get("skills") or {}
    if tech := skills.get("technical"):
        lines.append("Technical skills: " + ", ".join(tech))
    if soft := skills.get("soft"):
        lines.append("Soft skills: " + ", ".join(soft))

    if work := data.get("work_experience"):
        lines.append("")
        lines.append("Work Experience:")
        for role in work:
            header_parts = [role.get("title", "")]
            if company := role.get("company"):
                header_parts[0] = f"{header_parts[0]} @ {company}"
            if loc := role.get("location"):
                header_parts.append(loc)
            if dur := role.get("duration"):
                header_parts.append(f"({dur})")
            lines.append("  " + " | ".join(p for p in header_parts if p))
            for bullet in role.get("bullets") or []:
                lines.append(f"  - {bullet}")

    if edu := data.get("education"):
        lines.append("")
        lines.append("Education:")
        for e in edu:
            parts = [e.get("degree", ""), e.get("institution", "")]
            if yr := e.get("year"):
                parts.append(yr)
            entry = ", ".join(p for p in parts if p)
            if dist := e.get("distinction"):
                entry += f" | {dist}"
            lines.append(f"  {entry}")

    if projects := data.get("projects"):
        lines.append("")
        lines.append("Projects:")
        for p in projects:
            tech_str = f" [{', '.join(p.get('technologies', []))}]" if p.get("technologies") else ""
            lines.append(f"  {p.get('name', '')} — {p.get('description', '')}{tech_str}")

    if certs := data.get("certifications"):
        lines.append("Certifications: " + ", ".join(certs))

    return "\n".join(lines)


def fmt_github_prose(data: dict) -> str:
    """Render GitHub profile data as a compact repo list.

    Renders enriched fields (readme_summary, detected_stack, project_domain)
    when present; falls back to basic metadata otherwise.
    """
    repos = data.get("repos") or []
    if not repos:
        return "(No repos)"
    lines = [f"Repos ({len(repos)}):"]
    for r in repos:
        name = r.get("name", "(unnamed)")
        url = r.get("url", "")
        ref = f"{name} ({url})" if url else name

        # Enriched path
        if r.get("readme_summary"):
            stack = ", ".join(r.get("detected_stack") or [])
            domain = r.get("project_domain") or ""
            confidence = r.get("confidence") or ""
            header = ref
            if domain:
                header += f" [{domain}]"
            lines.append(f"  {header}")
            lines.append(f"    Summary: {r['readme_summary']}")
            if stack:
                lines.append(f"    Stack: {stack}")
            for claim in r.get("experience_claims") or []:
                lines.append(f"    - {claim}")
            if confidence:
                lines.append(f"    Confidence: {confidence}")
        else:
            # Basic fallback
            lang = f" [{r['language']}]" if r.get("language") else ""
            desc = f" — {r['description']}" if r.get("description") else ""
            lines.append(f"  {ref}{lang}{desc}")

    return "\n".join(lines)


def strip_city(institution: str) -> str:
    """Remove trailing city/state from institution names.

    Handles common delimiters: comma, em dash, en dash, hyphen with spaces.
    e.g. 'University of Arizona, Tucson, AZ'
         'University of Arizona — Tucson, AZ'
         'University of Arizona - Tucson'
    """
    return re.split(r"\s*[,—–·•]\s*|\s+-\s+", institution, maxsplit=1)[0].strip()


def format_sourced_profile(
    sourced_profile: dict,
    candidate_name: str | None = None,
    pronouns: str | None = None,
) -> str:
    """Format a source-keyed profile dict into labeled blocks for LLM context.

    Prepends a CANDIDATE block (name + pronouns) and a COMPUTED SIGNALS block
    so all LLM calls have consistent candidate context without requiring each
    service to manage it independently.

    Resume and GitHub data are rendered as compact prose (not raw JSON) to
    keep token counts manageable.
    """
    sections = []

    corrections = sourced_profile.get("corrections") or {}

    if candidate_name or pronouns:
        candidate_lines = []
        if candidate_name:
            candidate_lines.append(f"Name: {candidate_name}")
        resume_data = sourced_profile.get("resume") or {}
        effective_headline = corrections.get("headline") or resume_data.get("headline")
        if effective_headline:
            candidate_lines.append(f"Headline: {effective_headline}")
        if pronouns:
            candidate_lines.append(
                f"Pronouns: {pronouns} — use these when referring to the candidate in third person."
            )
        sections.append("[CANDIDATE]\n" + "\n".join(candidate_lines))

    signals = compute_profile_signals(sourced_profile)
    sections.append(f"[COMPUTED SIGNALS — treat as ground truth]\n{signals}")

    known_keys = {"resume", "github", "user_input", "corrections"}

    if resume := sourced_profile.get("resume"):
        if corrections:
            correctable = ("title", "summary", "location", "headline")
            merged_resume = {
                **resume,
                **{k: v for k, v in corrections.items() if k in correctable and v is not None},
            }
            sections.append(f"[Source: Resume]\n{fmt_resume_prose(merged_resume)}")
        else:
            sections.append(f"[Source: Resume]\n{fmt_resume_prose(resume)}")

    if github := sourced_profile.get("github"):
        sections.append(f"[Source: GitHub]\n{fmt_github_prose(github)}")

    if user_input := sourced_profile.get("user_input"):
        body = user_input if isinstance(user_input, str) else json.dumps(user_input)
        sections.append(f"[Source: Direct Input]\n{body}")

    for key, data in sourced_profile.items():
        if key not in known_keys:
            sections.append(f"[Source: {key}]\n{json.dumps(data)}")

    return "\n\n".join(sections) if sections else json.dumps(sourced_profile)


def build_ranked_matches_from_chunks(job_id, db) -> list[dict]:
    """Build ranked matches from scored JobChunk rows for a given job.

    Reads JobChunk rows where match_score >= 1 and should_render is True, ordered
    by score descending so the strongest matches appear first in the tailoring prompt.
    """
    from app.models.database import JobChunk

    chunks = (
        db.query(JobChunk)
        .filter(
            JobChunk.job_id == job_id,
            JobChunk.match_score >= 1,
            JobChunk.should_render.is_(True),
        )
        .order_by(JobChunk.match_score.desc(), JobChunk.position)
        .all()
    )
    return [
        {
            "requirement": chunk.content,
            "score": chunk.match_score,
            "rationale": chunk.match_rationale or "",
            "advocacy_blurb": chunk.advocacy_blurb or "",
            "experience_sources": chunk.experience_sources or [],
            "is_preferred": False,
        }
        for chunk in chunks
    ]
