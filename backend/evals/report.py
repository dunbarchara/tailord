"""Turn stored run results into a comparison report (JSON + markdown).

Reads evals/results/<task>/<model>.jsonl, keeping only results whose input hash still
matches the current task and item (stale results are ignored). Quality is reported separately
against every label source (never a blend), plus on the items every source agrees on versus
the contested ones, so a model is not blamed for noise in the labels themselves.

Quality, calibration and significance use each item's first run only, so repeats never inflate
the sample size; repeats feed the consistency metric and the per-run accuracy line.
"""

import json
from collections import Counter
from itertools import combinations
from pathlib import Path

from evals import metrics
from evals.runner import RESULTS_DIR, TRANSIENT_ERRORS, ResultStore, input_hash
from evals.tasks.base import ClassificationTask, EvalItem


def _ok(record: dict) -> bool:
    return not record.get("error")


def _unanswered(record: dict) -> bool:
    """A transient failure (rate limit, connection): no model answer was ever obtained, so
    it says nothing about the model's quality and is excluded from every quality metric."""
    return record.get("error") in TRANSIENT_ERRORS


def model_report(task: ClassificationTask, items: list[EvalItem], records: dict) -> dict:
    """One model's metrics. `records` is ResultStore.load() output for the model."""
    by_id = {i.id: i for i in items}
    all_results = [r for r in records.values() if r["item_id"] in by_id]
    unanswered = [r for r in all_results if _unanswered(r)]
    results = [r for r in all_results if not _unanswered(r)]  # every run that got an answer
    first = [r for r in results if r["run"] == 0]  # one sample per item
    sources = sorted({s for i in items for s in i.labels})
    quality, calib, subsets = {}, {}, {}
    for source in sources:
        pairs = [
            (by_id[r["item_id"]].labels[source], r["prediction"] if _ok(r) else None)
            for r in first
            if source in by_id[r["item_id"]].labels
        ]
        quality[source] = metrics.classification_quality(pairs, list(task.labels))
        samples = [
            (
                max(r["probabilities"].values()),
                r["prediction"] == by_id[r["item_id"]].labels[source],
            )
            for r in first
            if _ok(r) and r.get("probabilities")
        ]
        calib[source] = metrics.calibration(samples) if samples else None

    # Contested = the individual label sources disagree with each other on the item.
    raw = [s for s in sources if s != "agreed"]
    for name, pick in (
        ("unanimous", lambda i: len({i.labels[s] for s in raw}) == 1),
        ("contested", lambda i: len({i.labels[s] for s in raw}) > 1),
    ):
        pairs = [
            (by_id[r["item_id"]].labels["agreed"], r["prediction"] if _ok(r) else None)
            for r in first
            if "agreed" in by_id[r["item_id"]].labels and pick(by_id[r["item_id"]])
        ]
        subsets[name] = metrics.classification_quality(pairs, list(task.labels)) if pairs else None

    runs: dict[str, list] = {}
    for r in results:
        runs.setdefault(r["item_id"], []).append(r["prediction"] if _ok(r) else None)
    costs = [r["cost_usd"] for r in results]
    priced = all(c is not None for c in costs) and bool(costs)
    errors = [r for r in results if not _ok(r)]
    acc_by_run = []
    for run in sorted({r["run"] for r in results}):
        rows = [r for r in results if r["run"] == run and "agreed" in by_id[r["item_id"]].labels]
        right = sum(
            1 for r in rows if _ok(r) and r["prediction"] == by_id[r["item_id"]].labels["agreed"]
        )
        acc_by_run.append(
            {"run": run, "n": len(rows), "accuracy": right / len(rows) if rows else 0.0}
        )
    return {
        "accuracy_by_run": acc_by_run,
        "unanswered": len({r["item_id"] for r in unanswered} - {r["item_id"] for r in results}),
        "unanswered_by_type": dict(Counter(r["error"] for r in unanswered)),
        "n_results": len(results),
        "coverage": len({r["item_id"] for r in results}) / len(items)
        if items
        else 0.0,  # distinct items run
        "quality": quality,
        "calibration": calib,
        "agreed_subsets": subsets,
        "latency_ms": metrics.latency_stats([r["latency_ms"] for r in results if _ok(r)]),
        "cost": {
            "total_usd": sum(costs) if priced else None,
            "per_1k_items_usd": sum(costs) / len(results) * 1000 if priced else None,
            "tokens_in": sum(r["tokens_in"] for r in results),
            "tokens_out": sum(r["tokens_out"] for r in results),
        },
        "reliability": {
            "error_rate": len(errors) / len(results) if results else 0.0,
            "retry_rate": sum(1 for r in results if r["attempts"] > 1) / len(results)
            if results
            else 0.0,
            "errors_by_type": dict(Counter(r["error"] for r in errors)),
        },
        "consistency": metrics.consistency(runs),
    }


def pairwise(task_items: list[EvalItem], loaded: dict[str, dict]) -> list[dict]:
    """Exact McNemar between each pair of models on the agreed labels, over items both ran."""
    out = []
    for a, b in combinations(loaded, 2):
        both = [
            i
            for i in task_items
            if (i.id, 0) in loaded[a]
            and (i.id, 0) in loaded[b]
            and not _unanswered(loaded[a][(i.id, 0)])
            and not _unanswered(loaded[b][(i.id, 0)])
            and "agreed" in i.labels
        ]

        def correct(model: str, item: EvalItem) -> bool:
            r = loaded[model][(item.id, 0)]
            return _ok(r) and r["prediction"] == item.labels["agreed"]

        only_a = sum(1 for i in both if correct(a, i) and not correct(b, i))
        only_b = sum(1 for i in both if correct(b, i) and not correct(a, i))
        out.append(
            {
                "a": a,
                "b": b,
                "n": len(both),
                "only_a_correct": only_a,
                "only_b_correct": only_b,
                "p_value": metrics.mcnemar_exact(only_a, only_b),
            }
        )
    return out


def build_report(
    task: ClassificationTask,
    items: list[EvalItem],
    models: list[str] | None = None,
    root: Path = RESULTS_DIR,
    all_items: bool = False,
) -> dict:
    """Report on every model with results. By default the scope is the items that have a
    current result from at least one model; `all_items` scores against the full item set
    (so a partial run shows its true coverage)."""
    names = models or sorted(p.stem for p in (root / task.name).glob("*.jsonl"))
    hashes = {i.id: input_hash(task, i) for i in items}
    loaded = {}
    for m in names:
        current = {
            k: r
            for k, r in ResultStore(task.name, m, root).load().items()
            if r.get("input_hash") == hashes.get(k[0])
        }
        if current:
            loaded[m] = current
    covered = {k[0] for records in loaded.values() for k in records}
    scope = items if all_items else [i for i in items if i.id in covered]
    return {
        "task": task.name,
        "n_items": len(scope),
        "models": {m: model_report(task, scope, r) for m, r in loaded.items()},
        "pairwise_agreed": pairwise(scope, loaded),
        "label_sources": sorted({s for i in scope for s in i.labels}),
    }


# ── Markdown ──────────────────────────────────────────────────────────────────


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def _usd(x: float | None, digits: int = 4) -> str:
    return "n/a" if x is None else f"${x:.{digits}f}"


def _ms(x: float | None) -> str:
    return "n/a" if x is None else f"{x:,.0f}"


def render_markdown(report: dict, labels: list[str]) -> str:
    models = report["models"]
    sources = report["label_sources"]
    lines = [
        f"# Eval report: {report['task']}",
        "",
        f"{report['n_items']} items. Quality is against each label source separately, on each "
        "item's first run; an item whose model gave an invalid answer counts as wrong. Items "
        "with no answer because of rate limits or connection errors are excluded, not wrong.",
        "",
    ]
    incomplete = {m: r["unanswered"] for m, r in models.items() if r["unanswered"]}
    if incomplete:
        lines += [
            "> **INCOMPLETE:** "
            + "; ".join(f"{m} has {n} item(s) with no answer yet" for m, n in incomplete.items())
            + ". Scores below exclude them. Run the same command again to retry only those.",
            "",
        ]
    lines += [
        "## Comparison",
        "",
        "| model | coverage | no answer | "
        + " | ".join(f"acc vs {s}" for s in sources)
        + " | macro-F1 (agreed) | ECE | p50 ms | p95 ms | $/1k items | errors | retried |"
        " consistency |",
        "|" + "---|" * (len(sources) + 11),
    ]
    for m, r in models.items():
        accs = []
        for s in sources:
            q = r["quality"][s]
            lo, hi = q["accuracy_ci"]
            accs.append(f"{q['accuracy']:.1%} ({lo:.1%}-{hi:.1%})")
        ece = (r["calibration"].get("agreed") or {}).get("ece")
        lines.append(
            f"| {m} | {r['coverage']:.0%} | {r['unanswered']} | "
            + " | ".join(accs)
            + f" | {r['quality']['agreed']['macro_f1']:.3f} | "
            + ("n/a" if ece is None else f"{ece:.3f}")
            + f" | {_ms(r['latency_ms']['p50'])} | {_ms(r['latency_ms']['p95'])} | "
            + f"{_usd(r['cost']['per_1k_items_usd'])} | {_pct(r['reliability']['error_rate'])} | "
            + f"{_pct(r['reliability']['retry_rate'])} | "
            + ("n/a" if r["consistency"] is None else f"{r['consistency']:.1%}")
            + " |"
        )
    lines += [
        "",
        "Accuracy shows the 95% Wilson interval. ECE is expected calibration error "
        "on the top-class probability (n/a where a model reports none).",
        "",
    ]

    if report["pairwise_agreed"]:
        lines += ["## Pairwise (agreed labels, exact McNemar)", ""]
        for p in report["pairwise_agreed"]:
            verdict = "no significant difference" if p["p_value"] >= 0.05 else "significant"
            lines.append(
                f"- {p['a']} vs {p['b']} on {p['n']} items: only {p['a']} right on "
                f"{p['only_a_correct']}, only {p['b']} right on {p['only_b_correct']}; "
                f"p = {p['p_value']:.3f} ({verdict})"
            )
        lines.append("")

    for m, r in models.items():
        q = r["quality"]["agreed"]
        lines += [
            f"## {m}",
            "",
            f"Cost {_usd(r['cost']['total_usd'])} total, "
            f"{r['cost']['tokens_in']:,} tokens in, {r['cost']['tokens_out']:,} out. "
            f"Latency p50 {_ms(r['latency_ms']['p50'])} ms, max {_ms(r['latency_ms']['max'])} ms.",
            "",
        ]
        if r["unanswered_by_type"]:
            counts = ", ".join(f"{k} x{v}" for k, v in r["unanswered_by_type"].items())
            lines += [f"No answer (transient, excluded from scores): {counts}", ""]
        if len(r["accuracy_by_run"]) > 1:
            per_run = ", ".join(
                f"run {x['run']}: {x['accuracy']:.1%}" for x in r["accuracy_by_run"]
            )
            lines += [f"Accuracy by run (agreed labels): {per_run}", ""]
        if r["reliability"]["errors_by_type"]:
            lines += [
                "Errors: "
                + ", ".join(f"{k} x{v}" for k, v in r["reliability"]["errors_by_type"].items()),
                "",
            ]
        subsets = r["agreed_subsets"]
        parts = [
            f"{name}: {subsets[name]['accuracy']:.1%} of {subsets[name]['n']}"
            for name in ("unanimous", "contested")
            if subsets.get(name)
        ]
        if parts:
            lines += [
                "Accuracy on items all label sources agree on vs contested items (agreed labels): "
                + "; ".join(parts),
                "",
            ]
        lines += ["| class | precision | recall | F1 | support |", "|---|---|---|---|---|"]
        for label in labels:
            c = q["per_class"][label]
            if not c["support"] and not c["predicted"]:  # class absent from this data
                lines.append(f"| {label} | n/a | n/a | n/a | 0 |")
                continue
            lines.append(
                f"| {label} | {c['precision']:.2f} | {c['recall']:.2f} | {c['f1']:.2f} | {c['support']} |"
            )
        lines += ["", "Confusion (rows gold = agreed, columns predicted; non-zero cells only):", ""]
        cells = [
            f"{g} -> {p}: {n}"
            for g, row in q["confusion"].items()
            for p, n in row.items()
            if g != p
        ]
        lines += ["- " + c for c in sorted(cells)] if cells else ["No errors."]
        cal = r["calibration"].get("agreed")
        if cal:
            lines += [
                "",
                "Calibration on the top-class probability (agreed labels):",
                "",
                "| confidence | n | mean conf | accuracy |",
                "|---|---|---|---|",
            ]
            for b in cal["buckets"]:
                lo, hi = b["range"]
                lines.append(
                    f"| {lo:.1f}-{hi:.1f} | {b['n']} | {b['mean_confidence']:.2f} | {b['accuracy']:.1%} |"
                )
            lines += [
                "",
                "If only answers at or above a confidence were kept:",
                "",
                "| threshold | coverage | accuracy |",
                "|---|---|---|",
            ]
            for t in cal["thresholds"]:
                lines.append(f"| {t['threshold']} | {t['coverage']:.1%} | {_pct(t['accuracy'])} |")
        lines.append("")
    return "\n".join(lines)


def write_report(report: dict, labels: list[str], directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    json_path, md_path = directory / "report.json", directory / "report.md"
    json_path.write_text(json.dumps(report, indent=2, default=list), encoding="utf-8")
    md_path.write_text(render_markdown(report, labels), encoding="utf-8")
    return json_path, md_path
