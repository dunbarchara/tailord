"""Deterministic (code) stages of the job-side chain, each written as a frozen artifact.

    HTML posting -> markdown -> [job_bounds: LLM task] -> chunks -> [semantic_type: LLM task]

Both stages here reuse production code, so benchmarks see exactly what Tailord feeds its LLM
tasks. Their provenance is the git sha. Line numbers for bounds are **1-indexed, inclusive**
over `markdown.splitlines()`.

    uv run python -m evals.stages
"""

import json
from pathlib import Path

from app.core.extract import extract_markdown_content
from app.services.chunk_extractor import extract_chunks
from evals.schema import Provenance, item_id
from evals.store import DATA_DIR, git_sha, read_artifact, write_artifact

POSTINGS_DIR = DATA_DIR / "postings"
ARTIFACTS_DIR = DATA_DIR / "artifacts"
MARKDOWN_PATH = ARTIFACTS_DIR / "markdown.jsonl"
CHUNKS_PATH = ARTIFACTS_DIR / "chunks.jsonl"

# Production caps scraped markdown at 12k tokens before any LLM sees it; every posting here is
# far below that (checked in tests), so no truncation stage is modeled.
Bounds = tuple[int, int]  # (start_line, end_line), 1-indexed inclusive


def html_to_markdown(html: str) -> str:
    return extract_markdown_content(html)


def apply_line_bounds(markdown: str, bounds: Bounds | None) -> tuple[str, str, str]:
    """Split markdown into (pre, core, post) by line range, like production's `apply_bounds`
    does with anchors. `None` is the production fallback (both anchors null): all core."""
    if bounds is None:
        return "", markdown, ""
    start, end = bounds
    lines = markdown.splitlines()
    if not (1 <= start <= end <= len(lines)):
        raise ValueError(f"bounds {bounds} outside 1..{len(lines)}")
    return (
        "\n".join(lines[: start - 1]),
        "\n".join(lines[start - 1 : end]),
        "\n".join(lines[end:]),
    )


def numbered(markdown: str) -> str:
    """Line-numbered view for labelers and the bounds prompt."""
    return "\n".join(f"{i:>4}| {line}" for i, line in enumerate(markdown.splitlines(), 1))


def manifest() -> list[dict]:
    return [json.loads(line) for line in (POSTINGS_DIR / "manifest.jsonl").read_text().splitlines()]


def build_markdown_artifact(path: Path = MARKDOWN_PATH) -> str:
    items = []
    for row in manifest():
        html = (POSTINGS_DIR / "html" / f"{row['id']}.html").read_text(encoding="utf-8")
        markdown = html_to_markdown(html)
        items.append(
            {
                "id": row["id"],
                "board": row["board"],
                "markdown": markdown,
                "line_count": len(markdown.splitlines()),
            }
        )
    header = write_artifact(
        path,
        "markdown",
        items,
        Provenance(
            producer_kind="code",
            producer_task="html_to_markdown",
            producer=git_sha(),
            params={"extractor": "app.core.extract.extract_markdown_content"},
        ),
    )
    return header.content_hash


def build_chunks_artifact(
    markdown_path: Path = MARKDOWN_PATH,
    out_path: Path = CHUNKS_PATH,
    bounds_by_posting: dict[str, Bounds] | None = None,
    bounds_source: str = "none",
    provisional: bool = True,
) -> str:
    """Chunk every posting with production's `extract_chunks`.

    Positions run pre -> core -> post like production; `region` says which. Only core chunks
    are benchmark items (production excludes pre/post from scoring). With no bounds the whole
    markdown is core, which is production's fallback when bounds detection fails.
    """
    md_header, postings = read_artifact(markdown_path)
    items = []
    for p in postings:
        bounds = (bounds_by_posting or {}).get(p["id"])
        regions = zip(("pre", "core", "post"), apply_line_bounds(p["markdown"], bounds))
        position = 0
        for region, segment in regions:
            if not segment.strip():
                continue
            for c in extract_chunks(segment):
                items.append(
                    {
                        "id": item_id(p["id"], position),
                        "posting_id": p["id"],
                        "position": position,
                        "region": region,
                        "chunk_type": c.chunk_type,
                        "section": c.section,
                        "content": c.content,
                    }
                )
                position += 1
    header = write_artifact(
        out_path,
        "chunks",
        items,
        Provenance(
            producer_kind="code",
            producer_task="chunking",
            producer=git_sha(),
            upstream_hash=md_header.content_hash,
            params={"bounds_source": bounds_source, "chunker": "extract_chunks"},
            provisional=provisional,
        ),
    )
    return header.content_hash


def core_chunks(items: list[dict]) -> list[dict]:
    """The chunks a semantic_type / match_score benchmark runs on."""
    return [c for c in items if c["region"] == "core"]


if __name__ == "__main__":
    md_hash = build_markdown_artifact()
    chunks_hash = build_chunks_artifact()
    _, chunks = read_artifact(CHUNKS_PATH)
    print(
        f"markdown {md_hash[:12]}  chunks {chunks_hash[:12]}  core chunks {len(core_chunks(chunks))}"
    )
