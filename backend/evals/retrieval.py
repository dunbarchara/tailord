"""Frozen retrieval artifact for the match_score benchmark.

Retrieval runs once; every model then sees byte-identical prompts. It mirrors production
(`chunk_matcher._score_chunk_vector`): embed each job chunk, take the top-k non-skill claims
plus the top-K_SKILLS skill claims by cosine distance, render the grouped context with the
production `_build_grouped_context`, and fill the production user template. Claims come from
the production claim derivation (`experience_chunker._resume_chunks`), so the candidate side
matches what a real user's profile would produce.

Embeddings are cached by (model, text hash) under data/cache/ (gitignored), so rebuilding
after the chunk set changes only embeds new text.

    uv run python -m evals.retrieval                      # dry run: estimate only
    uv run python -m evals.retrieval --max-spend 0.01     # embed + write the artifact
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

from app.config import settings
from app.core.llm_pricing import get_pricing
from app.prompts import chunk_matching as prompt
from app.services.chunk_display import is_display_ready
from app.services.chunk_matcher import (
    K_SKILLS,
    _build_candidate_header,
    _build_grouped_context,
)
from app.services.experience_chunker import _github_repo_chunks, _resume_chunks
from app.services.profile_formatter import compute_profile_signals
from evals.schema import Provenance, item_id
from evals.stages import ARTIFACTS_DIR, CHUNKS_PATH
from evals.store import DATA_DIR, canonical, git_sha, read_artifact, write_artifact

PROFILES_DIR = DATA_DIR / "profiles"
CACHE_PATH = DATA_DIR / "cache" / "embeddings.jsonl"
RETRIEVAL_PATH = ARTIFACTS_DIR / "retrieval.jsonl"
DEFAULT_PROFILE = "alex-chen-backend-engineer"
TOP_K = 8  # production default: settings.vector_top_k
BATCH = 128


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def load_profile(profile_id: str) -> tuple[dict, dict]:
    """Returns (profile file contents, sourced-profile dict as production passes around)."""
    raw = json.loads((PROFILES_DIR / f"{profile_id}.json").read_text(encoding="utf-8"))
    ep = raw["extracted_profile"]
    sourced = {"resume": ep["resume"]}
    if ep.get("github"):
        sourced["github"] = {"repos": ep["github"]["repos"]}
    return raw, sourced


def profile_claims(sourced: dict) -> list[SimpleNamespace]:
    """ExperienceClaim-shaped objects derived by the production chunkers."""
    claims = []
    for d in _resume_chunks(sourced["resume"]):
        claims.append(SimpleNamespace(**d, source_type="resume", source_ref=None, group_id=None))
    for repo in (sourced.get("github") or {}).get("repos", []):
        for d in _github_repo_chunks(repo):
            claims.append(
                SimpleNamespace(
                    **d, source_type="github", source_ref=repo.get("name"), group_id=None
                )
            )
    return claims


def scoreable_chunks(chunks: list[dict]) -> list[dict]:
    """Chunks production sends to vector scoring: core, non-header, display-ready."""
    return [
        c
        for c in chunks
        if c["region"] == "core"
        and is_display_ready(SimpleNamespace(chunk_type=c["chunk_type"], content=c["content"]))
    ]


# ---------------------------------------------------------------------------
# Embeddings (cached)
# ---------------------------------------------------------------------------


def load_cache() -> dict[tuple[str, str], list[float]]:
    cache: dict[tuple[str, str], list[float]] = {}
    if CACHE_PATH.exists():
        for line in CACHE_PATH.read_text().splitlines():
            r = json.loads(line)
            cache[(r["model"], r["sha"])] = r["vector"]
    return cache


def count_tokens(texts: list[str]) -> int:
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")  # text-embedding-3-* encoding
    return sum(len(enc.encode(t)) for t in texts)


def estimate_cost(texts: list[str], model: str) -> tuple[int, float | None]:
    tokens = count_tokens(texts)
    pricing = get_pricing(model)
    return tokens, (tokens / 1_000_000 * pricing["input"]) if pricing else None


def embed_missing(texts: list[str], model: str, max_spend: float) -> dict:
    """Embed texts not in the cache; stop before exceeding max_spend. Returns usage stats."""
    from app.clients.embedding_client import get_embedding_client

    cache = load_cache()
    todo = [t for t in dict.fromkeys(texts) if (model, sha(t)) not in cache]
    pricing = get_pricing(model)
    spent, tokens = 0.0, 0
    client = get_embedding_client()
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("a", encoding="utf-8") as f:
        for i in range(0, len(todo), BATCH):
            batch = todo[i : i + BATCH]
            resp = client.embeddings.create(model=model, input=batch)
            tokens += resp.usage.prompt_tokens
            spent = tokens / 1_000_000 * pricing["input"] if pricing else 0.0
            for text, d in zip(batch, resp.data):
                f.write(canonical({"model": model, "sha": sha(text), "vector": d.embedding}) + "\n")
            if spent > max_spend:
                raise RuntimeError(
                    f"spend ${spent:.6f} passed the cap ${max_spend}; progress is cached, rerun"
                )
    return {
        "embedded": len(todo),
        "cached": len(set(texts)) - len(todo),
        "tokens": tokens,
        "spend_usd": spent,
    }


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


def cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    ma, mb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return 1.0 if ma == 0 or mb == 0 else 1.0 - dot / (ma * mb)


def retrieve(job_vec, claims, claim_vecs, k: int = TOP_K) -> list[tuple[SimpleNamespace, float]]:
    """Substantive top-k plus skills top-K_SKILLS, as production's two queries do."""
    scored = [(c, cosine_distance(job_vec, v)) for c, v in zip(claims, claim_vecs)]
    subst = sorted((s for s in scored if s[0].claim_type != "skill"), key=lambda s: s[1])[:k]
    skills = sorted((s for s in scored if s[0].claim_type == "skill"), key=lambda s: s[1])[
        :K_SKILLS
    ]
    return subst + skills


def build_items(chunks: list[dict], profile_id: str, model: str) -> list[dict]:
    raw, sourced = load_profile(profile_id)
    claims = profile_claims(sourced)
    cache = load_cache()
    claim_vecs = [cache[(model, sha(c.content))] for c in claims]
    # Production passes compute_profile_signals output (it depends on today's date for
    # ongoing roles), so the rendered header is frozen into the artifact here.
    header = _build_candidate_header(
        raw["candidate_name"], raw.get("pronouns"), signals=compute_profile_signals(sourced)
    )
    items = []
    for c in scoreable_chunks(chunks):
        top = retrieve(cache[(model, sha(c["content"]))], claims, claim_vecs)
        context = _build_grouped_context([t[0] for t in top])
        requirement = f"[{c['chunk_type'].upper()}] {c['content']}"
        items.append(
            {
                "id": item_id(c["id"], profile_id),
                "chunk_id": c["id"],
                "profile_id": profile_id,
                "chunk_type": c["chunk_type"],
                "section": c["section"],
                "content": c["content"],
                "candidate_header": header,
                "job_requirement": requirement,
                "grouped_context": context,
                "retrieved": [
                    {
                        "content": t[0].content,
                        "claim_type": t[0].claim_type,
                        "distance": round(t[1], 6),
                    }
                    for t in top
                ],
                "user_prompt": prompt.format_user_template_vector(
                    candidate_header=header,
                    job_requirement=requirement,
                    grouped_context=context,
                    k=len(top),
                ),
            }
        )
    return items


def build_artifact(
    chunks_path: Path = CHUNKS_PATH,
    out_path: Path = RETRIEVAL_PATH,
    profile_id: str = DEFAULT_PROFILE,
    model: str | None = None,
) -> str:
    model = model or settings.embedding_model
    chunks_header, chunks = read_artifact(chunks_path)
    raw_profile_hash = sha((PROFILES_DIR / f"{profile_id}.json").read_text(encoding="utf-8"))
    items = build_items(chunks, profile_id, model)
    header = write_artifact(
        out_path,
        "retrieval",
        items,
        Provenance(
            producer_kind="code",
            producer_task="retrieval",
            producer=git_sha(),
            upstream_hash=chunks_header.content_hash,
            params={
                "embedding_model": model,
                "k": TOP_K,
                "k_skills": K_SKILLS,
                "profile_id": profile_id,
                "profile_hash": raw_profile_hash,
                "system_prompt_hash": sha(prompt.SYSTEM),
            },
            provisional=chunks_header.provenance.provisional,
        ),
    )
    return header.content_hash


def required_texts(chunks: list[dict], profile_id: str) -> list[str]:
    _, sourced = load_profile(profile_id)
    return [c.content for c in profile_claims(sourced)] + [
        c["content"] for c in scoreable_chunks(chunks)
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-spend", type=float, default=None, help="USD cap; omit for a dry run")
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    args = ap.parse_args()

    model = settings.embedding_model
    _, chunks = read_artifact(CHUNKS_PATH)
    texts = list(dict.fromkeys(required_texts(chunks, args.profile)))
    cached = load_cache()
    todo = [t for t in texts if (model, sha(t)) not in cached]
    tokens, cost = estimate_cost(todo, model)
    print(f"embedding model: {model}  endpoint: {settings.embedding_base_url or 'default'}")
    print(f"texts: {len(texts)} unique, {len(todo)} not cached; est. tokens {tokens:,}")
    print("est. cost: " + (f"${cost:.6f}" if cost is not None else "unknown (model unpriced)"))
    if args.max_spend is None:
        cap = max((cost or 0) * 1.5, 0.0001)
        print(
            f"\ndry run. To embed and write the artifact:\n"
            f"  uv run python -m evals.retrieval --max-spend {cap:.4f}"
        )
        return
    stats = embed_missing(texts, model, args.max_spend)
    print(
        f"embedded {stats['embedded']} (cached {stats['cached']}), "
        f"{stats['tokens']:,} tokens, ${stats['spend_usd']:.6f}"
    )
    print("artifact hash", build_artifact(model=model)[:12])


if __name__ == "__main__":
    main()
