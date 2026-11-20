"""Label requests, imports, agreement reports and agreed labels for the three rounds.

Rounds run in order, each rebuilding the next stage's inputs:
  1. job_bounds    (per posting)  -> rebuild chunks with the agreed bounds
  2. semantic_type (per core chunk)
  3. match_score   (per retrieval item; rebuild retrieval first if chunks changed)

Request files are self-contained (task definition + items, no predictions) so a model with no
repo context can fill them in. Responses are JSONL, one `{"id": ..., "label": ...}` per line.

    uv run python -m evals.labeling request job_bounds
    uv run python -m evals.labeling import job_bounds FILE --source silver:sonnet-5-5
    uv run python -m evals.labeling report job_bounds silver:sonnet-5-5 silver:<other>
    uv run python -m evals.labeling agree job_bounds --primary silver:<other> --secondary silver:sonnet-5-5
    uv run python -m evals.labeling rebuild-chunks            # apply agreed bounds
    uv run python -m evals.labeling adjudicate                # corrections on top of the agreed set
"""

import argparse
import json
import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from app.prompts import chunk_matching, job_bounds
from evals.schema import LabelRecord
from evals.stages import CHUNKS_PATH, MARKDOWN_PATH, build_chunks_artifact, numbered
from evals.store import DATA_DIR, read_artifact, read_labels, write_labels
from evals.tasks.labels import MATCH_SCORES, SEMANTIC_TYPES

LABELS_DIR = DATA_DIR / "labels"
REQUESTS_DIR = DATA_DIR / "requests"
TASKS = ("job_bounds", "semantic_type", "match_score")


# ---------------------------------------------------------------------------
# Items and validation
# ---------------------------------------------------------------------------


def _retrieval_path() -> Path:
    from evals.retrieval import RETRIEVAL_PATH

    return RETRIEVAL_PATH


def items_for(task: str) -> list[dict]:
    """The items a task labels, in a stable order."""
    if task == "job_bounds":
        return read_artifact(MARKDOWN_PATH)[1]
    if task == "semantic_type":
        # Same chunks production sends to the LLM: core, non-header, display-ready.
        from evals.retrieval import scoreable_chunks

        return scoreable_chunks(read_artifact(CHUNKS_PATH)[1])
    if task == "match_score":
        return read_artifact(_retrieval_path())[1]
    raise ValueError(f"unknown task {task!r}")


def validate_label(task: str, label, item: dict) -> str | None:
    """Return an error message, or None if the label is valid for this item."""
    if task == "job_bounds":
        if not isinstance(label, dict) or set(label) - {"start", "end"}:
            return 'label must be {"start": int, "end": int}'
        s, e = label.get("start"), label.get("end")
        if not (isinstance(s, int) and isinstance(e, int)) or isinstance(s, bool):
            return "start and end must be integers"
        if not 1 <= s <= e <= item["line_count"]:
            return f"need 1 <= start <= end <= {item['line_count']}, got {s}..{e}"
        return None
    if task == "semantic_type":
        return None if label in SEMANTIC_TYPES else f"unknown semantic_type {label!r}"
    if task == "match_score":
        ok = isinstance(label, int) and not isinstance(label, bool) and label in MATCH_SCORES
        return None if ok else f"score must be one of {sorted(MATCH_SCORES)}"
    raise ValueError(f"unknown task {task!r}")


def parse_response(text: str) -> list[dict]:
    """Tolerant JSONL parse: skips blank lines and code fences; errors name the line."""
    rows = []
    for n, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("```"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {n}: not valid JSON ({exc.msg})") from exc
        if not isinstance(row, dict) or "id" not in row or "label" not in row:
            raise ValueError(f'line {n}: expected {{"id": ..., "label": ...}}')
        rows.append(row)
    return rows


def import_labels(task: str, response_text: str, source: str) -> list[LabelRecord]:
    """Validate a response against the task's items (every item exactly once) and return records."""
    items = {i["id"]: i for i in items_for(task)}
    seen: dict[str, dict] = {}
    errors: list[str] = []
    for row in parse_response(response_text):
        iid = row["id"]
        if iid not in items:
            errors.append(f"unknown id {iid!r}")
        elif iid in seen:
            errors.append(f"duplicate id {iid!r}")
        elif err := validate_label(task, row["label"], items[iid]):
            errors.append(f"{iid}: {err}")
        else:
            seen[iid] = row
    missing = [i for i in items if i not in seen]
    if missing:
        errors.append(f"{len(missing)} items unlabeled, e.g. {missing[:3]}")
    if errors:
        raise ValueError("import rejected:\n  " + "\n  ".join(errors[:20]))
    return [
        LabelRecord(
            task=task,
            item_id=iid,
            label=seen[iid]["label"],
            label_source=source,
            note=seen[iid].get("note"),
        )
        for iid in items
    ]


def labels_path(task: str, source: str) -> Path:
    return LABELS_DIR / f"{task}.{re.sub(r'[^A-Za-z0-9._-]+', '_', source)}.jsonl"


# ---------------------------------------------------------------------------
# Agreement
# ---------------------------------------------------------------------------


def cohen_kappa(a: list, b: list) -> float:
    """Cohen's kappa for two raters over the same items (1.0 if chance agreement is 1)."""
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def _range_iou(x: dict, y: dict) -> float:
    inter = max(0, min(x["end"], y["end"]) - max(x["start"], y["start"]) + 1)
    union = (x["end"] - x["start"] + 1) + (y["end"] - y["start"] + 1) - inter
    return inter / union


def agreement(task: str, a: list[LabelRecord], b: list[LabelRecord]) -> dict:
    """Agreement stats and the disagreement list between two label sets."""
    la, lb = {r.item_id: r.label for r in a}, {r.item_id: r.label for r in b}
    ids = [i for i in la if i in lb]
    out: dict = {"task": task, "n": len(ids)}
    if task == "job_bounds":
        items = {i["id"]: i for i in items_for(task)}
        ious = [_range_iou(la[i], lb[i]) for i in ids]
        keep_a, keep_b = [], []
        for i in ids:
            for line in range(1, items[i]["line_count"] + 1):
                keep_a.append(la[i]["start"] <= line <= la[i]["end"])
                keep_b.append(lb[i]["start"] <= line <= lb[i]["end"])
        out |= {
            "exact_match": sum(la[i] == lb[i] for i in ids) / len(ids),
            "mean_iou": sum(ious) / len(ious),
            "line_kappa": cohen_kappa(keep_a, keep_b),
        }
    else:
        out |= {
            "exact_match": sum(la[i] == lb[i] for i in ids) / len(ids),
            "kappa": cohen_kappa([la[i] for i in ids], [lb[i] for i in ids]),
            "confusion": dict(Counter((str(la[i]), str(lb[i])) for i in ids if la[i] != lb[i])),
        }
    out["disagreements"] = [{"id": i, "a": la[i], "b": lb[i]} for i in ids if la[i] != lb[i]]
    return out


def agreed_labels(
    task: str, primary: list[LabelRecord], secondary: list[LabelRecord]
) -> list[LabelRecord]:
    """Where the sources agree, that label; on disagreement the primary (stronger) model wins."""
    sec = {r.item_id: r.label for r in secondary}
    out = []
    for r in primary:
        note = None
        if sec.get(r.item_id) != r.label:
            note = f"disagreement: {r.label_source}={r.label!r} vs {sec.get(r.item_id)!r}"
        out.append(
            LabelRecord(
                task=task,
                item_id=r.item_id,
                label=r.label,
                label_source=f"agreed:{r.label_source}",
                note=note,
            )
        )
    return out


ADJUDICATIONS_PATH = LABELS_DIR / "adjudications.json"


def adjudicated_labels(
    task: str, base: list[LabelRecord], overrides: dict[str, dict]
) -> list[LabelRecord]:
    """The agreed labels with reviewed corrections applied. Every override must name an
    existing item, carry a valid label for it, and give a reason; silver and agreed label
    files are never touched, so the effect of the corrections stays measurable."""
    items = {i["id"]: i for i in items_for(task)}
    unknown = [i for i in overrides if i not in items]
    if unknown:
        raise ValueError(f"adjudication names unknown items: {unknown[:5]}")
    out = []
    for r in base:
        override = overrides.get(r.item_id)
        label, note = r.label, None
        if override:
            if not override.get("reason"):
                raise ValueError(f"{r.item_id}: an adjudication needs a reason")
            if err := validate_label(task, override["label"], items[r.item_id]):
                raise ValueError(f"{r.item_id}: {err}")
            label = override["label"]
            note = f"was {r.label!r} ({r.label_source}); {override['reason']}"
        out.append(
            LabelRecord(
                task=task, item_id=r.item_id, label=label, label_source="adjudicated", note=note
            )
        )
    return out


def write_adjudicated(path: Path = ADJUDICATIONS_PATH) -> dict[str, int]:
    """Build <task>.adjudicated.jsonl for every task listed in adjudications.json."""
    spec = json.loads(path.read_text(encoding="utf-8"))
    changed = {}
    for task, overrides in spec.items():
        base = read_labels(labels_path(task, "agreed"))
        records = adjudicated_labels(task, base, overrides)
        write_labels(labels_path(task, "adjudicated"), records)
        before = {r.item_id: r.label for r in base}
        changed[task] = sum(1 for r in records if r.label != before[r.item_id])
    return changed


def label_stats(records: list[LabelRecord]) -> dict:
    if records and isinstance(records[0].label, dict):
        spans = [r.label["end"] - r.label["start"] + 1 for r in records]
        return {"n": len(records), "mean_span_lines": sum(spans) / len(spans)}
    return {"n": len(records), "distribution": dict(Counter(str(r.label) for r in records))}


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

_RESPONSE_NOTE = """Respond with JSONL only: one JSON object per line, no prose, no code fences.
Include every item exactly once. {shape}"""


def _bounds_request(items: list[dict]) -> str:
    docs = "\n\n".join(
        f"### POSTING {i['id']} ({i['line_count']} lines)\n{numbered(i['markdown'])}" for i in items
    )
    return f"""# Task: locate the job description in each web page

{job_bounds.SYSTEM.strip().split("Return a JSON object")[0].strip()}

Instead of anchors, report line numbers. Each page below is shown with line numbers
(`  12| text`; the number is not part of the text). Lines are 1-indexed.
- "start": the first line of the actual job description content.
- "end": the last line of the actual job description content, just before any trailing
  EEO/legal boilerplate, application form or footer begins.
- The span is contiguous, and blank lines inside it count as part of it.

{_RESPONSE_NOTE.format(shape='Example line: {"id": "gh-01", "label": {"start": 12, "end": 88}}')}
Optional: add a short "note" field when a case is genuinely ambiguous.

{docs}
"""


def _semantic_request(items: list[dict]) -> str:
    defs = "\n".join(f"- {k}: {v}" for k, v in SEMANTIC_TYPES.items())
    by_posting: dict[str, list[dict]] = {}
    for c in items:
        by_posting.setdefault(c["posting_id"], []).append(c)
    docs = []
    for pid, chunks in by_posting.items():
        lines = [f"### POSTING {pid}"]
        for c in chunks:
            sec = f" (section: {c['section']})" if c["section"] else ""
            lines.append(f"[{c['id']}] {c['chunk_type']}{sec}: {c['content']}")
        docs.append("\n".join(lines))
    return f"""# Task: classify job posting chunks

Classify each chunk as exactly one of:
{defs}

Chunks are shown in order with the section heading they fall under; judge each chunk on its
own content, using the neighbors for context.

{_RESPONSE_NOTE.format(shape='Example line: {"id": "gh-01:7", "label": "job_requirement"}')}

""" + "\n\n".join(docs)


def _score_request(items: list[dict]) -> str:
    rubric = chunk_matching.SYSTEM.strip()
    headers: dict[str, str] = {}
    for i in items:
        headers.setdefault(i["profile_id"], i["candidate_header"])
    parts = []
    for it in items:
        ctx = it["grouped_context"]
        parts.append(
            f"### ITEM {it['id']} (profile: {it['profile_id']})\n"
            f"JOB REQUIREMENT:\n{it['job_requirement']}\n\n"
            f"RELEVANT EXPERIENCE:\n{ctx}"
        )
    hdr = "\n\n".join(f"## Candidate ({pid})\n{h}" for pid, h in headers.items())
    return f"""# Task: score job requirements against a candidate

Use the scoring rubric below. Ignore its JSON output format and any instructions about
rationales or blurbs: for this task return only the score as the label (2, 1, 0 or -1).

--- RUBRIC ---
{rubric}
--- END RUBRIC ---

{_RESPONSE_NOTE.format(shape='Example line: {"id": "gh-01:7:alex-chen-backend-engineer", "label": 1}')}

{hdr}

""" + "\n\n".join(parts)


_BUILDERS: dict[str, Callable[[list[dict]], str]] = {
    "job_bounds": _bounds_request,
    "semantic_type": _semantic_request,
    "match_score": _score_request,
}


def make_requests(task: str, per_part: int | None = None) -> list[Path]:
    """Write request file(s), split into parts of `per_part` items (default: bounds 10,
    semantic_type 150, match_score 100) so each fits comfortably in one model context."""
    per_part = per_part or {"job_bounds": 10, "semantic_type": 150, "match_score": 100}[task]
    items = items_for(task)
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for n, start in enumerate(range(0, len(items), per_part), 1):
        path = REQUESTS_DIR / f"{task}.part{n:02d}.md"
        path.write_text(_BUILDERS[task](items[start : start + per_part]), encoding="utf-8")
        paths.append(path)
    return paths


def import_files(task: str, files: list[Path], source: str) -> Path:
    text = "\n".join(f.read_text(encoding="utf-8") for f in files)
    records = import_labels(task, text, source)
    path = labels_path(task, source)
    write_labels(path, records)
    return path


def rebuild_chunks_from_bounds(source: str = "agreed") -> str:
    """Rebuild the chunks artifact using the given bounds label set (provisional)."""
    path = next(LABELS_DIR.glob(f"job_bounds.{source}*.jsonl"), None)
    if path is None:
        raise FileNotFoundError(f"no job_bounds labels for source {source!r}")
    records = read_labels(path)
    bounds = {r.item_id: (r.label["start"], r.label["end"]) for r in records}
    return build_chunks_artifact(
        bounds_by_posting=bounds, bounds_source=f"labels:{path.stem}", provisional=True
    )


def _print_report(rep: dict) -> None:
    for k, v in rep.items():
        if k == "disagreements":
            print(f"disagreements: {len(v)}")
            for d in v[:40]:
                print(f"  {d['id']}: {d['a']}  vs  {d['b']}")
        elif isinstance(v, float):
            print(f"{k}: {v:.3f}")
        else:
            print(f"{k}: {v}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("request")
    r.add_argument("task", choices=TASKS)
    r.add_argument("--per-part", type=int)
    i = sub.add_parser("import")
    i.add_argument("task", choices=TASKS)
    i.add_argument("files", nargs="+", type=Path)
    i.add_argument("--source", required=True)
    rep = sub.add_parser("report")
    rep.add_argument("task", choices=TASKS)
    rep.add_argument("source_a")
    rep.add_argument("source_b")
    ag = sub.add_parser("agree")
    ag.add_argument("task", choices=TASKS)
    ag.add_argument("--primary", required=True)
    ag.add_argument("--secondary", required=True)
    sub.add_parser("rebuild-chunks")
    sub.add_parser("adjudicate", help="apply data/labels/adjudications.json to the agreed labels")
    args = ap.parse_args()

    if args.cmd == "request":
        for p in make_requests(args.task, args.per_part):
            print(p)
    elif args.cmd == "import":
        print("wrote", import_files(args.task, args.files, args.source))
    elif args.cmd == "report":
        a = read_labels(labels_path(args.task, args.source_a))
        b = read_labels(labels_path(args.task, args.source_b))
        _print_report(agreement(args.task, a, b))
    elif args.cmd == "agree":
        p = read_labels(labels_path(args.task, args.primary))
        s = read_labels(labels_path(args.task, args.secondary))
        out = labels_path(args.task, "agreed")
        write_labels(out, agreed_labels(args.task, p, s))
        print("wrote", out, label_stats(read_labels(out)))
    elif args.cmd == "adjudicate":
        for task, n in write_adjudicated().items():
            print(
                f"{task}: {n} label(s) changed from the agreed set -> {labels_path(task, 'adjudicated')}"
            )
    elif args.cmd == "rebuild-chunks":
        print("chunks", rebuild_chunks_from_bounds()[:12])


if __name__ == "__main__":
    main()
