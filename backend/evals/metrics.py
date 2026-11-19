"""Pure metric functions for classification evals (no I/O, no model calls).

Quality is always computed against one label source at a time. An item whose call failed
counts as wrong (the model gave no usable answer), and shows up in the confusion matrix
under ERROR_COLUMN so reliability problems are not hidden inside accuracy.
"""

import math
from collections import Counter, defaultdict
from collections.abc import Sequence

ERROR_COLUMN = "(error)"


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion (well-behaved at the extremes)."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def classification_quality(pairs: Sequence[tuple[str, str | None]], labels: Sequence[str]) -> dict:
    """pairs are (gold, predicted-or-None). Macro-F1 averages over classes that have gold
    support, so a class absent from the data cannot drag the score to zero."""
    confusion: dict[str, Counter] = defaultdict(Counter)
    for gold, pred in pairs:
        confusion[gold][pred if pred is not None else ERROR_COLUMN] += 1
    n = len(pairs)
    correct = sum(1 for g, p in pairs if g == p)
    per_class = {}
    for label in labels:
        tp = confusion[label][label]
        support = sum(confusion[label].values())
        predicted = sum(confusion[g][label] for g in confusion)
        precision = tp / predicted if predicted else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
            "predicted": predicted,
        }
    supported = [c for c in per_class.values() if c["support"]]
    low, high = wilson_interval(correct, n)
    return {
        "n": n,
        "accuracy": correct / n if n else 0.0,
        "accuracy_ci": (low, high),
        "macro_f1": sum(c["f1"] for c in supported) / len(supported) if supported else 0.0,
        "per_class": per_class,
        "confusion": {g: dict(c) for g, c in confusion.items()},
        "n_errors": sum(1 for _, p in pairs if p is None),
    }


def calibration(samples: Sequence[tuple[float, bool]], bins: int = 10) -> dict:
    """samples are (top-class probability, was it correct). ECE is the bin-size-weighted gap
    between mean confidence and accuracy; `thresholds` shows accuracy and coverage if only
    answers at or above a confidence level were kept (the routing use case)."""
    n = len(samples)
    buckets = []
    ece = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        members = [(p, ok) for p, ok in samples if (lo <= p < hi) or (b == bins - 1 and p == 1.0)]
        if not members:
            continue
        conf = sum(p for p, _ in members) / len(members)
        acc = sum(1 for _, ok in members if ok) / len(members)
        ece += len(members) / n * abs(conf - acc)
        buckets.append(
            {"range": (lo, hi), "n": len(members), "mean_confidence": conf, "accuracy": acc}
        )
    thresholds = []
    for t in (0.5, 0.7, 0.9, 0.99):
        kept = [ok for p, ok in samples if p >= t]
        thresholds.append(
            {
                "threshold": t,
                "coverage": len(kept) / n if n else 0.0,
                "accuracy": sum(kept) / len(kept) if kept else None,
            }
        )
    return {"n": n, "ece": ece if n else None, "buckets": buckets, "thresholds": thresholds}


def percentile(values: Sequence[float], q: float) -> float | None:
    """Nearest-rank percentile (q in 0-100)."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100 * len(ordered)))
    return ordered[rank - 1]


def latency_stats(ms: Sequence[float]) -> dict:
    return {"p50": percentile(ms, 50), "p95": percentile(ms, 95), "max": max(ms) if ms else None}


def mcnemar_exact(only_a_correct: int, only_b_correct: int) -> float:
    """Two-sided exact McNemar p-value for 'the two models are equally accurate', from the
    counts of items only one of them got right."""
    n = only_a_correct + only_b_correct
    if n == 0:
        return 1.0
    k = min(only_a_correct, only_b_correct)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def consistency(runs_by_item: dict[str, list[str | None]]) -> float | None:
    """Share of repeated items where every run gave the same prediction (items with fewer
    than two successful runs are skipped). None if nothing was repeated."""
    comparable = [
        [p for p in preds if p is not None] for preds in runs_by_item.values() if len(preds) >= 2
    ]
    comparable = [preds for preds in comparable if len(preds) >= 2]
    if not comparable:
        return None
    return sum(1 for preds in comparable if len(set(preds)) == 1) / len(comparable)
