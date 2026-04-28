#!/usr/bin/env python3
"""
Eval runner — measures LLM chunk-matching accuracy against known fixtures.

Runs both matching modes and produces a side-by-side comparison:
  - llm:    full formatted profile passed to LLM scorer (baseline)
  - vector: cosine pre-selection → focused grouped context → LLM scores

Usage (from backend/):
    uv run python tests/eval/eval_runner.py

Results are printed to stdout and written to tests/eval/RESULTS.md.

Requires: LLM + embedding model configured in .env (EMBEDDING_API_KEY for
real embeddings; EMBEDDING_BASE_URL if using Foundry).

Exit codes:
    0 — runner completed (regardless of agreement rate)
    1 — runner could not start (bad config, no fixtures, import error)
"""

import json
import math
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

# Allow running directly from backend/ or from the repo root.
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

from app.clients.embedding_client import embed_text  # noqa: E402
from app.clients.llm_client import get_llm_client  # noqa: E402
from app.config import settings  # noqa: E402
from app.core.llm_utils import llm_parse_with_retry  # noqa: E402
from app.prompts import chunk_matching as prompt  # noqa: E402
from app.schemas.matching import ChunkMatchBatch  # noqa: E402
from app.services.chunk_matcher import _build_candidate_header, _build_grouped_context  # noqa: E402
from app.services.tailoring_generator import _format_sourced_profile  # noqa: E402
from tests.eval.profile_schema import EvalCandidateProfile  # noqa: E402

_EVAL_DIR = Path(__file__).parent
_PROFILES_DIR = _EVAL_DIR / "profiles"
_FIXTURES_DIR = _EVAL_DIR / "fixtures"
_RESULTS_FILE = _EVAL_DIR / "RESULTS.md"

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
# LLM mode (baseline)
# ---------------------------------------------------------------------------


def _run_fixture_llm(fixture: dict, profiles: dict[str, EvalCandidateProfile]) -> list[int]:
    profile = profiles[fixture["profile"]]
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
# Vector mode
# ---------------------------------------------------------------------------


def _build_exp_chunks_from_profile(profile_dict: dict) -> list[SimpleNamespace]:
    """
    Convert a profile dict into ExperienceChunk-like SimpleNamespace objects
    for in-memory embedding and retrieval during eval.

    Mirrors the shape expected by _build_grouped_context:
    group_key, date_range, source_type, technologies, content.
    """
    chunks = []
    pos = 0

    resume = profile_dict.get("resume", {})

    for job in resume.get("work_experience", []):
        group_key = f"{job.get('company', '')} | {job.get('title', '')}"
        date_range = job.get("duration")
        for bullet in job.get("bullets", []):
            chunks.append(
                SimpleNamespace(
                    content=bullet,
                    group_key=group_key,
                    date_range=date_range,
                    source_type="resume",
                    source_ref=None,
                    technologies=None,
                    position=pos,
                )
            )
            pos += 1

    for skill in resume.get("skills", {}).get("technical", []):
        chunks.append(
            SimpleNamespace(
                content=skill,
                group_key=None,
                date_range=None,
                source_type="resume",
                source_ref=None,
                technologies=None,
                position=pos,
            )
        )
        pos += 1

    for edu in resume.get("education", []):
        group_key = f"{edu.get('degree', '')} | {edu.get('institution', '')}"
        content = (
            f"{edu.get('degree', '')} from {edu.get('institution', '')} ({edu.get('year', '')})"
        ).strip()
        chunks.append(
            SimpleNamespace(
                content=content,
                group_key=group_key,
                date_range=edu.get("year"),
                source_type="resume",
                source_ref=None,
                technologies=None,
                position=pos,
            )
        )
        pos += 1

    for repo in profile_dict.get("github", {}).get("repos", []):
        if summary := repo.get("readme_summary"):
            chunks.append(
                SimpleNamespace(
                    content=summary,
                    group_key=repo["name"],
                    date_range=None,
                    source_type="github",
                    source_ref=repo["name"],
                    technologies=repo.get("detected_stack", []),
                    position=pos,
                )
            )
            pos += 1

    if user_input_text := profile_dict.get("user_input", {}).get("text"):
        chunks.append(
            SimpleNamespace(
                content=user_input_text,
                group_key=None,
                date_range=None,
                source_type="user_input",
                source_ref=None,
                technologies=None,
                position=pos,
            )
        )

    return chunks


def _cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 1.0
    return 1.0 - dot / (mag_a * mag_b)


def _embed_exp_chunks(
    chunks: list[SimpleNamespace],
) -> list[tuple[SimpleNamespace, list[float]]]:
    """Embed experience chunks; silently skips failures."""
    result = []
    for c in chunks:
        try:
            result.append((c, embed_text(c.content)))
        except Exception as e:
            print(f"  Warning: failed to embed experience chunk: {e}", file=sys.stderr)
    return result


def _run_fixture_vector(
    fixture: dict, profiles: dict[str, EvalCandidateProfile], k: int
) -> list[int]:
    profile = profiles[fixture["profile"]]
    profile_dict = profile.to_profile_dict()

    exp_chunks = _build_exp_chunks_from_profile(profile_dict)
    embedded_exp = _embed_exp_chunks(exp_chunks)
    if not embedded_exp:
        raise RuntimeError("No experience chunks could be embedded")

    candidate_header = _build_candidate_header(profile.candidate_name, profile.pronouns)
    scores = []

    for c in fixture["chunks"]:
        job_emb = embed_text(c["content"])

        # Rank by cosine distance (ascending = most similar first)
        ranked = sorted(embedded_exp, key=lambda ce: _cosine_distance(job_emb, ce[1]))
        top_k_chunks = [chunk for chunk, _ in ranked[:k]]

        grouped_context = _build_grouped_context(top_k_chunks)

        result = llm_parse_with_retry(
            get_llm_client(),
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": prompt.SYSTEM},
                {
                    "role": "user",
                    "content": prompt.USER_TEMPLATE_VECTOR.format(
                        candidate_header=candidate_header,
                        job_requirement=f"[{c['chunk_type'].upper()}] {c['content']}",
                        grouped_context=grouped_context,
                        k=len(top_k_chunks),
                    ),
                },
            ],
            response_model=ChunkMatchBatch,
            temperature=prompt.TEMPERATURE,
        )
        scores.append(result.results[0].score if result.results else -1)

    return scores


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _fmt_scores(scores: list[int]) -> str:
    return "[" + ", ".join(_SCORE_LABELS.get(s, str(s)) for s in scores) + "]"


def _match_mark(expected: list[int], actual: list[int]) -> str:
    if len(actual) != len(expected):
        return "✗"
    return "✓" if all(e == a for e, a in zip(expected, actual)) else "✗"


def _write_results_md(
    run_date: date,
    llm_model: str,
    embedding_model: str,
    fixtures: list[dict],
    llm_results: dict[str, list[int] | Exception],
    vec_results: dict[str, list[int] | Exception],
    k: int,
) -> None:
    lines = [
        "# Eval Results",
        "",
        f"**Date:** {run_date}  ",
        f"**LLM model:** `{llm_model}`  ",
        f"**Embedding model:** `{embedding_model}`  ",
        f"**Vector top-K:** {k}",
        "",
        "## Per-fixture scores",
        "",
        "| Fixture | Expected | LLM | Vector | LLM✓ | Vec✓ |",
        "|---------|----------|-----|--------|------|------|",
    ]

    total_chunks = 0
    llm_matched = 0
    vec_matched = 0

    for fx in fixtures:
        fid = fx["id"]
        expected = fx["expected_scores"]
        n = len(expected)

        llm_r = llm_results.get(fid)
        vec_r = vec_results.get(fid)

        llm_str = _fmt_scores(llm_r) if isinstance(llm_r, list) else f"ERROR: {llm_r}"
        vec_str = _fmt_scores(vec_r) if isinstance(vec_r, list) else f"ERROR: {vec_r}"

        llm_mark = _match_mark(expected, llm_r) if isinstance(llm_r, list) else "✗"
        vec_mark = _match_mark(expected, vec_r) if isinstance(vec_r, list) else "✗"

        lines.append(
            f"| {fid} | {_fmt_scores(expected)} | {llm_str} | {vec_str} | {llm_mark} | {vec_mark} |"
        )

        total_chunks += n
        if isinstance(llm_r, list):
            llm_matched += sum(1 for i in range(n) if i < len(llm_r) and expected[i] == llm_r[i])
        if isinstance(vec_r, list):
            vec_matched += sum(1 for i in range(n) if i < len(vec_r) and expected[i] == vec_r[i])

    if total_chunks:
        llm_rate = llm_matched / total_chunks
        vec_rate = vec_matched / total_chunks
        lines += [
            "",
            "## Agreement rates",
            "",
            "| Mode | Matched | Total | Rate |",
            "|------|---------|-------|------|",
            f"| LLM (full profile) | {llm_matched} | {total_chunks} | {llm_rate:.0%} |",
            f"| Vector (top-{k}) | {vec_matched} | {total_chunks} | {vec_rate:.0%} |",
        ]

    lines += [
        "",
        "## Methodology",
        "",
        "**LLM mode:** full `_format_sourced_profile` string passed to scorer in a batched call.  ",
        f"**Vector mode:** experience chunks extracted from profile in-memory, embedded with "
        f"`{embedding_model}`, ranked by cosine similarity, top-{k} passed as grouped context "
        "to a single-chunk LLM call.  ",
        "",
        "_Note: scoring is non-deterministic (temperature=0.1). Run multiple times to confirm "
        "stable agreement rates before promoting vector as default._",
    ]

    _RESULTS_FILE.write_text("\n".join(lines) + "\n")
    print(f"\nResults written to {_RESULTS_FILE.relative_to(_BACKEND_DIR)}")


def main() -> None:
    profiles = _load_profiles()
    fixtures = _load_fixtures()

    if not fixtures:
        print(f"No fixtures found in {_FIXTURES_DIR}", file=sys.stderr)
        sys.exit(1)

    k = settings.vector_top_k
    run_date = date.today()

    col_id = 28
    col_exp = 26
    col_llm = 26
    col_vec = 26
    width = col_id + col_exp + col_llm + col_vec + 12

    print(
        f"\nEval run — {run_date}"
        f"  |  model: {settings.llm_model}"
        f"  |  embedding: {settings.embedding_model}"
        f"  |  K={k}"
    )
    print("=" * width)
    print(
        f"{'Fixture':<{col_id}}  {'Expected':<{col_exp}}  "
        f"{'LLM':<{col_llm}}  {'Vector':<{col_vec}}  Match"
    )
    print("-" * width)

    llm_results: dict[str, list[int] | Exception] = {}
    vec_results: dict[str, list[int] | Exception] = {}

    total_chunks = 0
    llm_matched = 0
    vec_matched = 0

    for fixture in fixtures:
        fid = fixture["id"]
        expected = fixture["expected_scores"]
        n = len(expected)

        # LLM mode
        try:
            llm_scores = _run_fixture_llm(fixture, profiles)
            llm_results[fid] = llm_scores
        except Exception as exc:
            llm_results[fid] = exc
            llm_scores = []

        # Vector mode
        try:
            vec_scores = _run_fixture_vector(fixture, profiles, k)
            vec_results[fid] = vec_scores
        except Exception as exc:
            vec_results[fid] = exc
            vec_scores = []

        total_chunks += n
        llm_matched += sum(
            1 for i in range(n) if i < len(llm_scores) and expected[i] == llm_scores[i]
        )
        vec_matched += sum(
            1 for i in range(n) if i < len(vec_scores) and expected[i] == vec_scores[i]
        )

        llm_str = _fmt_scores(llm_scores) if isinstance(llm_results[fid], list) else "ERROR"
        vec_str = _fmt_scores(vec_scores) if isinstance(vec_results[fid], list) else "ERROR"
        llm_mark = _match_mark(expected, llm_scores) if llm_scores else "✗"
        vec_mark = _match_mark(expected, vec_scores) if vec_scores else "✗"

        print(
            f"{fid:<{col_id}}  {_fmt_scores(expected):<{col_exp}}  "
            f"{llm_str:<{col_llm}}  {vec_str:<{col_vec}}  {llm_mark}/{vec_mark}"
        )

    print("-" * width)

    if total_chunks:
        llm_rate = llm_matched / total_chunks
        vec_rate = vec_matched / total_chunks
        print(f"\nAgreement — LLM: {llm_matched}/{total_chunks} ({llm_rate:.0%})", end="")
        print(f"  |  Vector: {vec_matched}/{total_chunks} ({vec_rate:.0%})")

    _write_results_md(
        run_date,
        settings.llm_model,
        settings.embedding_model,
        fixtures,
        llm_results,
        vec_results,
        k,
    )


if __name__ == "__main__":
    main()
