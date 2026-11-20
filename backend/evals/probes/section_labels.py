"""Probe: how often do section labels slip through chunking as ordinary paragraphs, and can
Jev catch them?

Real postings are fetched through Tailord's own production paths (Greenhouse and Lever public
APIs via app.core.ats_client), chunked with the production chunker, and kept ONLY in
evals/data/local/ (gitignored). Nothing here is committed except this code; summaries written
into planning docs must stay aggregate (no company names, no long quotes).

    uv run python -m evals.probes.section_labels fetch --n 24 --seed 1
    uv run python -m evals.probes.section_labels chunks
"""

import argparse
import json
import random
import re
import time
from pathlib import Path

import requests

from app.core.ats_client import try_ats_fetch
from app.services.chunk_extractor import extract_chunks
from evals.store import DATA_DIR

LOCAL_DIR = DATA_DIR / "local" / "real_postings"
INDEX = LOCAL_DIR / "index.json"
CHUNKS = LOCAL_DIR / "chunks.json"

GREENHOUSE_BOARDS = [
    "anthropic",
    "stripe",
    "airbnb",
    "databricks",
    "cloudflare",
    "datadog",
    "gitlab",
    "coinbase",
    "discord",
    "figma",
    "instacart",
    "robinhood",
    "reddit",
    "pinterest",
]
LEVER_BOARDS = [
    "palantir",
    "spotify",
    "plaid",
    "mistral",
    "kraken",
    "weride",
    "zoox",
    "gohighlevel",
]
UA = {"User-Agent": "Mozilla/5.0 (research probe; small sample)"}


def _jobs_greenhouse(board: str) -> list[str]:
    r = requests.get(
        f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", headers=UA, timeout=20
    )
    return [j["absolute_url"] for j in r.json().get("jobs", [])] if r.ok else []


def _jobs_lever(board: str) -> list[str]:
    r = requests.get(f"https://api.lever.co/v0/postings/{board}?mode=json", headers=UA, timeout=20)
    return [j["hostedUrl"] for j in r.json()] if r.ok and isinstance(r.json(), list) else []


def fetch(n: int, seed: int) -> None:
    rng = random.Random(seed)
    pools: list[tuple[str, str]] = []  # (source, url)
    for board in GREENHOUSE_BOARDS:
        urls = _jobs_greenhouse(board)
        pools += [("greenhouse", u) for u in rng.sample(urls, min(3, len(urls)))]
        time.sleep(0.3)
    for board in LEVER_BOARDS:
        urls = _jobs_lever(board)
        pools += [("lever", u) for u in rng.sample(urls, min(3, len(urls)))]
        time.sleep(0.3)
    rng.shuffle(pools)
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    index, per_source = {}, {"greenhouse": 0, "lever": 0}
    for source, url in pools:
        if len(index) >= n or per_source[source] >= n // 2:
            continue
        markdown = try_ats_fetch(url)  # the production path; None on any failure
        if not markdown or len(markdown) < 800:
            continue
        pid = f"real-{len(index) + 1:02d}"
        (LOCAL_DIR / f"{pid}.md").write_text(markdown, encoding="utf-8")
        index[pid] = {"source": source, "url": url, "chars": len(markdown)}
        per_source[source] += 1
        time.sleep(0.3)
    INDEX.write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"fetched {len(index)} postings {per_source} into {LOCAL_DIR} (gitignored)")


def unescape_greenhouse() -> None:
    """Re-render the Greenhouse postings as they WOULD be if Tailord unescaped the API's
    HTML-entity-escaped `content` (it does not today). The as-fetched markdown is kept as
    <id>.asis.md; <id>.md becomes the fixed version, so `chunks` and later runs use it."""
    import html

    from app.core.ats_client import _greenhouse_to_markdown, _parse_greenhouse_url

    index = json.loads(INDEX.read_text(encoding="utf-8"))
    n = 0
    for pid, meta in index.items():
        if meta["source"] != "greenhouse":
            continue
        board, job_id = _parse_greenhouse_url(meta["url"])
        api = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}?questions=false"
        data = requests.get(api, headers=UA, timeout=20).json()
        data["content"] = html.unescape(data.get("content", ""))
        path = LOCAL_DIR / f"{pid}.md"
        asis = LOCAL_DIR / f"{pid}.asis.md"
        if not asis.exists():
            asis.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.write_text(_greenhouse_to_markdown(data), encoding="utf-8")
        n += 1
        time.sleep(0.3)
    print(f"re-rendered {n} Greenhouse postings with the API content unescaped")


def summarize(root: Path | None = None, thresholds=(0.5, 0.7, 0.9, 0.99)) -> dict:
    """Aggregate-only summary of the section-label probe (no posting text is printed, so the
    numbers are safe to quote in planning docs): how many chunks Jev flags as section labels
    at each probability, and in how many postings."""
    from evals.runner import RESULTS_DIR, ResultStore, input_hash
    from evals.tasks import TASKS
    from evals.tasks.real import load_real_items

    root = root or RESULTS_DIR
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    items = {i.id: i for i in load_real_items()}
    task = TASKS["real_section_label"]
    results = {
        k[0]: r
        for k, r in ResultStore(task.name, "jev-1.14.0", root).load().items()
        if k[0] in items and r["input_hash"] == input_hash(task, items[k[0]]) and not r["error"]
    }
    out = {"postings": len(index), "chunks_to_an_llm": len(items), "answered": len(results)}
    for t in thresholds:
        flagged = [i for i, r in results.items() if r["probabilities"]["section_label"] >= t]
        posts = {items[i].input["posting_id"] for i in flagged}
        out[f"p>={t}"] = {"chunks": len(flagged), "postings": len(posts)}
    for key, value in out.items():
        print(f"{key}: {value}")
    return out


def chunk() -> None:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    out = []
    for pid in index:
        markdown = (LOCAL_DIR / f"{pid}.md").read_text(encoding="utf-8")
        for c in extract_chunks(markdown):
            out.append(
                {
                    "id": f"{pid}:{c.position}",
                    "posting_id": pid,
                    "position": c.position,
                    "chunk_type": c.chunk_type,
                    "section": c.section,
                    "content": c.content,
                }
            )
    CHUNKS.write_text(json.dumps(out), encoding="utf-8")
    kinds = {}
    for c in out:
        kinds[c["chunk_type"]] = kinds.get(c["chunk_type"], 0) + 1
    print(f"{len(out)} chunks from {len(index)} postings: {kinds}")


_LABEL_RE = re.compile(r"^[\W_]*([A-Z][\w'&/, -]{2,60}):?[\W_]*$")


def looks_like_label(text: str) -> bool:
    """Cheap heuristic for counting only (Jev is the detector under test): a short line with
    no sentence punctuation, or one ending in a colon."""
    t = text.strip()
    if len(t.split()) > 8 or t.endswith((".", "!", "?")):
        return False
    return t.endswith(":") or bool(_LABEL_RE.match(t))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--n", type=int, default=24)
    f.add_argument("--seed", type=int, default=1)
    sub.add_parser("chunks")
    sub.add_parser("unescape-greenhouse")
    sub.add_parser("summarize")
    args = ap.parse_args()
    if args.cmd == "fetch":
        fetch(args.n, args.seed)
    elif args.cmd == "chunks":
        chunk()
    elif args.cmd == "summarize":
        summarize()
    else:
        unescape_greenhouse()
