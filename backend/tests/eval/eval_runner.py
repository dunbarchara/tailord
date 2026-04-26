#!/usr/bin/env python3
"""
Eval runner — measures LLM chunk-matching accuracy against known fixtures.

Usage (from backend/):
    uv run python tests/eval/eval_runner.py

Requires: local LLM running at LLM_BASE_URL (configured in .env).
NOT in CI — run manually before making prompt or model changes to record
a baseline, and after to confirm you haven't regressed.

Local models (e.g. LM Studio) are expected to underperform on some fixtures.
That's intentional — this runner exists to surface those weaknesses, not gate
on them. A future sprint will add a CI gate when targeting hosted models.

Exit codes:
    0 — runner completed (regardless of agreement rate)
    1 — runner could not start (bad config, no fixtures, import error)
"""

import json
import sys
from datetime import date
from pathlib import Path

# Allow running directly from backend/ or from the repo root.
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

from app.clients.llm_client import get_llm_client  # noqa: E402
from app.config import settings  # noqa: E402
from app.core.llm_utils import llm_parse_with_retry  # noqa: E402
from app.prompts import chunk_matching as prompt  # noqa: E402
from app.schemas.matching import ChunkMatchBatch  # noqa: E402
from app.services.tailoring_generator import _format_sourced_profile  # noqa: E402
from tests.eval.profile_schema import EvalCandidateProfile  # noqa: E402

_EVAL_DIR = Path(__file__).parent
_PROFILES_DIR = _EVAL_DIR / "profiles"
_FIXTURES_DIR = _EVAL_DIR / "fixtures"

_SCORE_LABELS = {2: "STRONG", 1: "PARTIAL", 0: "GAP", -1: "N/A"}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _load_profiles() -> dict[str, EvalCandidateProfile]:
    profiles = {}
    for path in _PROFILES_DIR.glob("*.json"):
        with open(path) as f:
            data = json.load(f)
        profiles[path.stem] = EvalCandidateProfile(**data)
    return profiles


def _load_fixtures() -> list[dict]:
    fixtures = []
    for path in sorted(_FIXTURES_DIR.glob("*.json")):
        with open(path) as f:
            fixtures.append(json.load(f))
    return fixtures


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _run_fixture(fixture: dict, profiles: dict[str, EvalCandidateProfile]) -> list[int]:
    profile_key = fixture["profile"]
    profile = profiles[profile_key]

    formatted_profile = _format_sourced_profile(
        profile.to_profile_dict(),
        candidate_name=profile.candidate_name,
        pronouns=profile.pronouns,
    )

    chunks = fixture["chunks"]
    section = fixture.get("section", "Requirements")
    chunks_block = "\n".join(
        f"{i}. [{c['chunk_type'].upper()}] {c['content']}" for i, c in enumerate(chunks, start=1)
    )

    result = llm_parse_with_retry(
        get_llm_client(),
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": prompt.SYSTEM},
            {
                "role": "user",
                "content": prompt.USER_TEMPLATE.format(
                    extracted_profile=formatted_profile,
                    section=section,
                    chunks_block=chunks_block,
                ),
            },
        ],
        response_model=ChunkMatchBatch,
        temperature=prompt.TEMPERATURE,
    )
    return [r.score for r in result.results]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _fmt_scores(scores: list[int]) -> str:
    return "[" + ", ".join(_SCORE_LABELS.get(s, str(s)) for s in scores) + "]"


def main() -> None:
    profiles = _load_profiles()
    fixtures = _load_fixtures()

    if not fixtures:
        print(f"No fixtures found in {_FIXTURES_DIR}", file=sys.stderr)
        sys.exit(1)

    col_id = 32
    col_exp = 28
    col_act = 28
    width = col_id + col_exp + col_act + 6

    print(f"\nEval run — {date.today()}  |  model: {settings.llm_model}")
    print("=" * width)
    print(f"{'Fixture':<{col_id}}  {'Expected':<{col_exp}}  {'Actual':<{col_act}}  Match")
    print("-" * width)

    total_chunks = 0
    matched_chunks = 0
    errors = 0

    for fixture in fixtures:
        fid = fixture["id"]
        expected = fixture["expected_scores"]

        try:
            actual = _run_fixture(fixture, profiles)
        except Exception as exc:
            print(f"{fid:<{col_id}}  ERROR: {exc}")
            errors += 1
            continue

        n = len(expected)
        chunk_matches = [i < len(actual) and expected[i] == actual[i] for i in range(n)]
        matched = sum(chunk_matches)
        total_chunks += n
        matched_chunks += matched

        exp_str = _fmt_scores(expected)
        act_str = _fmt_scores(actual) if len(actual) == n else _fmt_scores(actual) + " (!)"
        mark = "✓" if matched == n and len(actual) == n else "✗"

        print(f"{fid:<{col_id}}  {exp_str:<{col_exp}}  {act_str:<{col_act}}  {mark}")

    print("-" * width)

    if total_chunks:
        rate = matched_chunks / total_chunks
        print(f"\nAgreement: {matched_chunks}/{total_chunks} chunks ({rate:.0%})")
    if errors:
        print(f"Errors: {errors} fixture(s) failed to run")

    print(
        "\nNote: local models are expected to score below hosted models on these fixtures.\n"
        "This baseline is a reference point — not a pass/fail gate.\n"
    )


if __name__ == "__main__":
    main()
