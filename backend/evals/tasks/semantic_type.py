"""semantic_type: which of 8 categories a job posting chunk belongs to.

Label definitions are the production prompt's (evals/tasks/labels.py). Production asks for
this inside the combined scoring call; here it is a standalone classification so models can
be compared on it alone, on the frozen chunk inputs from label round 2.
"""

from typing import Any

from evals.store import read_labels
from evals.tasks.base import ClassificationTask, EvalItem
from evals.tasks.labels import SEMANTIC_TYPES


def render_state(item_input: dict[str, Any]) -> str:
    section = item_input.get("section") or "(none)"
    return f"Section: {section}\nChunk type: {item_input['chunk_type']}\nChunk: {item_input['content']}"


SEMANTIC_TYPE = ClassificationTask(
    name="semantic_type",
    labels=SEMANTIC_TYPES,
    instructions=(
        "Classify this chunk of a job posting into the category that best describes what it "
        "says. Judge the chunk's own content; the section heading is context only."
    ),
    render_state=render_state,
)

LABEL_SOURCES = ("silver:sonnet-5-5", "silver:opus-5-5", "agreed")


def load_items() -> list[EvalItem]:
    """Every scoreable chunk with its labels from each available source."""
    # Imported here: evals.labeling imports evals.tasks.labels, which loads this package.
    from evals.labeling import items_for, labels_path

    by_source: dict[str, dict[str, Any]] = {}
    for source in LABEL_SOURCES:
        path = labels_path("semantic_type", source)
        if path.exists():
            by_source[source] = {r.item_id: r.label for r in read_labels(path)}
    return [
        EvalItem(
            id=chunk["id"],
            input={
                "posting_id": chunk["posting_id"],
                "chunk_type": chunk["chunk_type"],
                "section": chunk["section"],
                "content": chunk["content"],
            },
            labels={s: labels[chunk["id"]] for s, labels in by_source.items()},
        )
        for chunk in items_for("semantic_type")
    ]
