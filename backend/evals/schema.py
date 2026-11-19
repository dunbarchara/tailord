"""Artifact, provenance and label records shared by every eval task.

An artifact is a frozen set of items (JSONL) plus a header recording where it came from.
Provenance chains artifacts together: each one names the artifact it was derived from by
content hash, so a benchmark result can always be traced back to its exact inputs.
"""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1

# What produced an artifact: deterministic app code (git sha recorded), an LLM task run, or
# agreed labels standing in for a model's output until a standard model is chosen.
ProducerKind = Literal["code", "model", "labels"]


class Provenance(BaseModel):
    producer_kind: ProducerKind
    # Pipeline stage that produced it, e.g. "html_to_markdown", "job_bounds", "chunking".
    producer_task: str
    # Model name for producer_kind="model"; git sha for "code"; label sources for "labels".
    producer: str
    upstream_hash: str | None = None  # content hash of the artifact this was derived from
    params: dict[str, Any] = Field(default_factory=dict)
    # True until `promote` replaces a labels-derived artifact with a chosen model's output.
    provisional: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))


class ArtifactHeader(BaseModel):
    schema_version: int = SCHEMA_VERSION
    name: str  # e.g. "chunks", "retrieval"
    provenance: Provenance
    item_count: int
    content_hash: str  # sha256 of the canonical item serialization


class LabelRecord(BaseModel):
    """One label for one item from one source. Items are never labeled twice per source."""

    task: str
    item_id: str
    label: Any  # task-specific: str for choices, int for scores, {"start","end"} for bounds
    # Free-form: "silver:sonnet-5-5", "silver:<model>", "gold:human".
    label_source: str
    labeled_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    note: str | None = None


def item_id(*parts: str | int) -> str:
    """Stable item id from its natural key, e.g. item_id("greenhouse-01", 14) or
    item_id(chunk_id, profile_id) for profile-dependent tasks."""
    return ":".join(str(p) for p in parts)
