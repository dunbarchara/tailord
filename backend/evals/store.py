"""Reading and writing artifacts and label files (JSONL, deterministic serialization)."""

import hashlib
import json
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from evals.schema import ArtifactHeader, LabelRecord, Provenance

DATA_DIR = Path(__file__).parent / "data"


def canonical(obj: Any) -> str:
    """Deterministic JSON: sorted keys, no whitespace, unicode preserved."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(items: Iterable[dict]) -> str:
    h = hashlib.sha256()
    for item in items:
        h.update(canonical(item).encode())
        h.update(b"\n")
    return h.hexdigest()


def git_sha() -> str:
    """Current commit, marked dirty if the tree has uncommitted changes (code provenance)."""
    root = Path(__file__).parent
    sha = subprocess.run(
        ["git", "rev-parse", "--short=12", "HEAD"], cwd=root, capture_output=True, text=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", "."], cwd=root, capture_output=True, text=True
    ).stdout.strip()
    return f"{sha or 'unknown'}{'+dirty' if dirty else ''}"


def write_artifact(
    path: Path, name: str, items: list[dict], provenance: Provenance
) -> ArtifactHeader:
    """Write `<path>` as JSONL: line 1 is the header, the rest are items."""
    header = ArtifactHeader(
        name=name,
        provenance=provenance,
        item_count=len(items),
        content_hash=content_hash(items),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(canonical(header.model_dump()) + "\n")
        for item in items:
            f.write(canonical(item) + "\n")
    return header


def read_artifact(path: Path) -> tuple[ArtifactHeader, list[dict]]:
    """Read an artifact and verify its content hash (a hand-edited artifact is an error)."""
    with path.open(encoding="utf-8") as f:
        header = ArtifactHeader.model_validate(json.loads(f.readline()))
        items = [json.loads(line) for line in f if line.strip()]
    if len(items) != header.item_count or content_hash(items) != header.content_hash:
        raise ValueError(f"{path}: content does not match its header hash (edited by hand?)")
    return header, items


def write_labels(path: Path, records: Iterable[LabelRecord]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(canonical(r.model_dump()) + "\n")
            n += 1
    return n


def read_labels(path: Path) -> list[LabelRecord]:
    with path.open(encoding="utf-8") as f:
        return [LabelRecord.model_validate_json(line) for line in f if line.strip()]
