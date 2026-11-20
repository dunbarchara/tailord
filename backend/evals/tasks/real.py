"""Tasks over real postings fetched locally by evals.probes.section_labels.

These have no gold labels (the postings are real, uncommitted, and unreviewed), so they are
for probing behavior and cost, not scoring quality: run them with the runner, then summarize
with `python -m evals.probes.section_labels summarize`.
"""

import json
from dataclasses import replace

from evals.tasks.base import ClassificationTask, EvalItem
from evals.tasks.semantic_type import SEMANTIC_TYPE, render_state

REAL_SEMANTIC_TYPE = replace(SEMANTIC_TYPE, name="real_semantic_type")

REAL_SECTION_LABEL = ClassificationTask(
    name="real_section_label",
    labels={
        "section_label": (
            "A line that only names or introduces a section, a list or the posting itself: "
            "a heading ('Requirements:', 'What you'll do', 'About the team'), a lead-in "
            "('We're looking for someone who has:'), or a page title or banner. It states "
            "nothing a candidate could have or lack."
        ),
        "content": (
            "Anything that states something about the job, the company, pay, location or "
            "hiring: a sentence, a requirement, a responsibility, a benefit, a fact."
        ),
    },
    instructions=(
        "Decide whether this chunk of a job posting is only a section label or lead-in, or "
        "real content. Judge the chunk's own text."
    ),
    render_state=render_state,
)


def load_real_items() -> list[EvalItem]:
    """Non-header chunks of the locally fetched real postings (headers never reach an LLM)."""
    from evals.probes.section_labels import CHUNKS

    if not CHUNKS.exists():
        raise SystemExit(
            "no local real postings: run `uv run python -m evals.probes.section_labels fetch` "
            "and then `... chunks` first"
        )
    chunks = json.loads(CHUNKS.read_text(encoding="utf-8"))
    return [
        EvalItem(
            id=c["id"],
            input={k: c[k] for k in ("posting_id", "chunk_type", "section", "content")},
            labels={},
        )
        for c in chunks
        if c["chunk_type"] != "header"
    ]
