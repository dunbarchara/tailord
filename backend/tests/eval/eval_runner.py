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

import hashlib
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
_CACHE_DIR = _EVAL_DIR / "cache"
_CACHE_FILE = _CACHE_DIR / "scores.json"

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
# Cache (offline / record modes)
# ---------------------------------------------------------------------------


def _compute_pipeline_hash() -> str:
    """
    Fingerprint of everything that affects what the LLM sees during eval:
    prompt templates, retrieval config, fixture inputs, and candidate profiles.

    Excludes expected_scores (calibration labels) and description fields —
    those can change without invalidating the cached LLM outputs.

    A hash mismatch in --offline mode means the cache is stale and --record
    must be run before the gate result is meaningful.
    """
    h = hashlib.sha256()

    # Prompt file — the most common source of pipeline changes
    prompt_path = _BACKEND_DIR / "app" / "prompts" / "chunk_matching.py"
    h.update(prompt_path.read_bytes())

    # Retrieval config
    h.update(f"k={settings.vector_top_k}".encode())

    # Fixture inputs: id, section, profile reference, and chunk content/type.
    # expected_scores and description are intentionally excluded.
    for fixture_path in sorted(_FIXTURES_DIR.glob("*.json")):
        fixture = json.loads(fixture_path.read_text())
        h.update(fixture["id"].encode())
        h.update(fixture.get("section", "").encode())
        h.update(fixture.get("profile", "").encode())
        for chunk in fixture.get("chunks", []):
            h.update(chunk.get("chunk_type", "").encode())
            h.update(chunk.get("content", "").encode())

    # Candidate profiles
    for profile_path in sorted(_PROFILES_DIR.glob("*.json")):
        h.update(profile_path.read_bytes())

    return h.hexdigest()[:16]


def _load_score_cache() -> dict | None:
    if not _CACHE_FILE.exists():
        return None
    with open(_CACHE_FILE) as f:
        return json.load(f)


def _save_score_cache(
    run_date: date,
    llm_model: str,
    embedding_model: str,
    k: int,
    llm_results: "dict[str, list[int] | Exception]",
    vec_results: "dict[str, list[int] | Exception]",
) -> None:
    _CACHE_DIR.mkdir(exist_ok=True)
    existing = _load_score_cache()

    scores: dict[str, dict] = {}
    for fid, lr in llm_results.items():
        if isinstance(lr, list):
            scores.setdefault(fid, {})["llm"] = lr
    for fid, vr in vec_results.items():
        if isinstance(vr, list):
            scores.setdefault(fid, {})["vector"] = vr

    # Warn about any fixture whose scores changed relative to the previous cache.
    # Oscillating scores on a fixture signal it's on the model's decision boundary —
    # worth re-running before committing.
    if existing:
        changed: list[str] = []
        for fid, new_modes in scores.items():
            old_modes = existing.get("scores", {}).get(fid, {})
            for m, new_vals in new_modes.items():
                old_vals = old_modes.get(m)
                if old_vals is not None and old_vals != new_vals:
                    changed.append(
                        f"  ! {fid} [{m}]  was {_fmt_scores(old_vals)}  →  now {_fmt_scores(new_vals)}"
                    )
        if changed:
            print(
                "\nWarning: the following fixture scores changed from the previous cache.\n"
                "This may be LLM variability on a borderline case — consider re-running\n"
                "before committing to confirm the new result is stable:\n" + "\n".join(changed)
            )

    data = {
        "version": 1,
        "recorded_at": str(run_date),
        "llm_model": llm_model,
        "embedding_model": embedding_model,
        "k": k,
        "pipeline_hash": _compute_pipeline_hash(),
        "scores": scores,
    }
    with open(_CACHE_FILE, "w") as f:
        f.write(json.dumps(data, indent=2) + "\n")
    print(f"\nCache written to {_CACHE_FILE.relative_to(_BACKEND_DIR)}")


def _run_offline(fixtures: list[dict], cache: dict, mode: str, threshold: float) -> None:
    """
    Offline gate: compare cached scores against fixture expected_scores.
    mode: "vector" | "llm" | "both"
    Exits 0 if all checked modes meet threshold, 1 otherwise.
    """
    cached_scores = cache.get("scores", {})
    modes_to_check = ["llm", "vector"] if mode == "both" else [mode]
    k = cache.get("k", "?")

    print(
        f"\nOffline eval gate — recorded {cache.get('recorded_at', '?')}"
        f"  |  model: {cache.get('llm_model', '?')}"
        f"  |  embedding: {cache.get('embedding_model', '?')}"
        f"  |  K={k}"
    )

    # Pipeline hash check — detects stale cache without requiring developer memory.
    # If prompts, fixture inputs, retrieval config, or profiles have changed since
    # --record was last run, the cached scores no longer reflect current behaviour.
    current_hash = _compute_pipeline_hash()
    cached_hash = cache.get("pipeline_hash")
    if cached_hash is None:
        print(
            "\n  Warning: cache has no pipeline_hash (recorded before this feature).\n"
            "  Run: make eval-record  to add staleness detection to this cache."
        )
    elif current_hash != cached_hash:
        print(
            f"\n✗ Pipeline inputs have changed since cache was recorded.\n"
            f"  Cached hash : {cached_hash}\n"
            f"  Current hash: {current_hash}\n"
            f"\n  The cached scores may no longer reflect current pipeline behaviour.\n"
            f"  Run: make eval-record  to update the cache, then re-run this gate.",
            file=sys.stderr,
        )
        sys.exit(1)

    any_failed = False

    for m in modes_to_check:
        print(f"\n[{m} mode]")
        total = 0
        matched = 0
        cache_miss = False

        for fx in fixtures:
            fid = fx["id"]
            expected = fx["expected_scores"]
            cached = cached_scores.get(fid, {}).get(m)

            if cached is None:
                print(f"  ✗ {fid:<34}  CACHE MISS — run: make eval-record")
                cache_miss = True
                continue

            n = len(expected)
            hits = sum(1 for e, c in zip(expected, cached) if e == c)
            total += n
            matched += hits
            mark = "✓" if hits == n else "✗"
            print(
                f"  {mark} {fid:<34}  got {_fmt_scores(cached):<28}  "
                f"expected {_fmt_scores(expected)}"
            )

        if cache_miss:
            any_failed = True
        elif total:
            rate = matched / total
            status = "PASS" if rate >= threshold else "FAIL"
            print(f"\n  [{m}] {status}: {matched}/{total} ({rate:.0%}) — threshold {threshold:.0%}")
            if rate < threshold:
                any_failed = True

    sys.exit(1 if any_failed else 0)


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
    import argparse

    parser = argparse.ArgumentParser(description="Eval runner for chunk-matching quality")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--offline",
        action="store_true",
        help="Check cached scores against expected_scores (no API calls). Exit 1 if below threshold.",
    )
    group.add_argument(
        "--record",
        action="store_true",
        help="Run live eval and write scores to cache (seeds/updates the offline gate).",
    )
    parser.add_argument(
        "--mode",
        choices=["both", "vector", "llm"],
        default="both",
        help="Modes to run or check. Default: both.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.70,
        help="Minimum agreement rate for offline gate. Default: 0.70.",
    )
    args = parser.parse_args()

    fixtures = _load_fixtures()
    if not fixtures:
        print(f"No fixtures found in {_FIXTURES_DIR}", file=sys.stderr)
        sys.exit(1)

    # ── Offline gate — no API calls ──────────────────────────────────────────
    if args.offline:
        cache = _load_score_cache()
        if not cache:
            print(
                f"No cache at {_CACHE_FILE} — run: make eval-record",
                file=sys.stderr,
            )
            sys.exit(1)
        _run_offline(fixtures, cache, args.mode, args.threshold)
        return  # _run_offline calls sys.exit

    # ── Live run ─────────────────────────────────────────────────────────────
    profiles = _load_profiles()
    k = settings.vector_top_k
    run_date = date.today()
    run_llm = args.mode in ("both", "llm")
    run_vec = args.mode in ("both", "vector")

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

        if run_llm:
            try:
                llm_scores = _run_fixture_llm(fixture, profiles)
                llm_results[fid] = llm_scores
            except Exception as exc:
                llm_results[fid] = exc
                llm_scores = []
        else:
            llm_scores = []

        if run_vec:
            try:
                vec_scores = _run_fixture_vector(fixture, profiles, k)
                vec_results[fid] = vec_scores
            except Exception as exc:
                vec_results[fid] = exc
                vec_scores = []
        else:
            vec_scores = []

        total_chunks += n
        if run_llm:
            llm_matched += sum(
                1 for i in range(n) if i < len(llm_scores) and expected[i] == llm_scores[i]
            )
        if run_vec:
            vec_matched += sum(
                1 for i in range(n) if i < len(vec_scores) and expected[i] == vec_scores[i]
            )

        llm_str = (
            _fmt_scores(llm_scores)
            if isinstance(llm_results.get(fid), list)
            else ("—" if not run_llm else "ERROR")
        )
        vec_str = (
            _fmt_scores(vec_scores)
            if isinstance(vec_results.get(fid), list)
            else ("—" if not run_vec else "ERROR")
        )
        llm_mark = _match_mark(expected, llm_scores) if run_llm and llm_scores else "—"
        vec_mark = _match_mark(expected, vec_scores) if run_vec and vec_scores else "—"

        print(
            f"{fid:<{col_id}}  {_fmt_scores(expected):<{col_exp}}  "
            f"{llm_str:<{col_llm}}  {vec_str:<{col_vec}}  {llm_mark}/{vec_mark}"
        )

    print("-" * width)

    if total_chunks:
        parts = []
        if run_llm:
            parts.append(f"LLM: {llm_matched}/{total_chunks} ({llm_matched / total_chunks:.0%})")
        if run_vec:
            parts.append(f"Vector: {vec_matched}/{total_chunks} ({vec_matched / total_chunks:.0%})")
        print(f"\nAgreement — {'  |  '.join(parts)}")

    if run_llm and run_vec:
        _write_results_md(
            run_date,
            settings.llm_model,
            settings.embedding_model,
            fixtures,
            llm_results,
            vec_results,
            k,
        )

    if args.record:
        _save_score_cache(
            run_date,
            settings.llm_model,
            settings.embedding_model,
            k,
            llm_results,
            vec_results,
        )


if __name__ == "__main__":
    main()
