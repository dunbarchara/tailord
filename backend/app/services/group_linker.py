"""
group_linker.py — heuristic matching of GitHub repo groups to resume role groups.

No LLM involved. Uses normalised string comparison (exact match or substring)
to suggest a parent role group for each repository group.

Called at ingest time (chunk_resume / chunk_github_repo) so suggestions are
available immediately after a sync completes.
"""

import re

import structlog

from app.models.database import ExperienceGroup

logger = structlog.get_logger(__name__)

# Suffixes and noise words to strip before comparing
_STRIP_SUFFIXES = re.compile(
    r"\b(inc|ltd|llc|co|corp|plc|gmbh|bv|sa|ag|pty|pvt|limited|company)\b",
    re.IGNORECASE,
)
_STRIP_NOISE = re.compile(r"[^a-z0-9\s]")


def _normalise(name: str) -> str:
    """Lowercase, strip punctuation and common company suffixes."""
    name = name.lower()
    name = _STRIP_SUFFIXES.sub("", name)
    name = _STRIP_NOISE.sub(" ", name)
    return " ".join(name.split())  # collapse whitespace


def suggest_repo_parent(
    repo_group: ExperienceGroup,
    role_groups: list[ExperienceGroup],
) -> tuple[ExperienceGroup, str] | None:
    """Return (role_group, confidence) for the best matching role, or None.

    Strategy:
    1. Exact normalised match on name → 'high' confidence
    2. One name is a contiguous substring of the other → 'medium' confidence
    3. No match → None

    Only role groups (group_type='role') should be passed as role_groups.
    Does NOT write to DB — the caller is responsible for updating type_meta.
    """
    repo_norm = _normalise(repo_group.name)
    if not repo_norm:
        return None

    exact_match: ExperienceGroup | None = None
    substring_match: ExperienceGroup | None = None

    for role in role_groups:
        # Role group names are typically "Company | Title" — check both the
        # full name and just the company portion (before the " | ").
        role_name = role.name or ""
        candidates = [role_name]
        if " | " in role_name:
            candidates.append(role_name.split(" | ")[0])

        for candidate in candidates:
            candidate_norm = _normalise(candidate)
            if not candidate_norm:
                continue

            if repo_norm == candidate_norm:
                exact_match = role
                break
            if repo_norm in candidate_norm or candidate_norm in repo_norm:
                if substring_match is None:
                    substring_match = role

        if exact_match:
            break

    if exact_match:
        logger.debug(
            "group_linker_exact_match",
            repo=repo_group.name,
            role=exact_match.name,
        )
        return exact_match, "high"

    if substring_match:
        logger.debug(
            "group_linker_substring_match",
            repo=repo_group.name,
            role=substring_match.name,
        )
        return substring_match, "medium"

    return None
