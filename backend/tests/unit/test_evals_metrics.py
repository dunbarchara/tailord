import math

import pytest

from evals import metrics
from evals.metrics import ERROR_COLUMN

LABELS = ["a", "b", "c"]


def test_wilson_interval_brackets_the_estimate_and_handles_extremes():
    lo, hi = metrics.wilson_interval(90, 100)
    assert lo < 0.9 < hi and hi - lo < 0.15
    assert metrics.wilson_interval(0, 0) == (0.0, 0.0)
    lo, hi = metrics.wilson_interval(10, 10)
    assert hi == pytest.approx(1.0) and 0.7 < lo < 1.0


def test_quality_by_hand():
    pairs = [("a", "a"), ("a", "a"), ("a", "b"), ("b", "b"), ("b", "a"), ("c", None)]
    q = metrics.classification_quality(pairs, LABELS)
    assert q["n"] == 6 and q["accuracy"] == pytest.approx(3 / 6) and q["n_errors"] == 1
    a = q["per_class"]["a"]  # tp 2, predicted 3 (a,a from a + a from b), support 3
    assert a["precision"] == pytest.approx(2 / 3) and a["recall"] == pytest.approx(2 / 3)
    b = q["per_class"]["b"]  # tp 1, predicted 2, support 2
    assert b["precision"] == pytest.approx(1 / 2) and b["recall"] == pytest.approx(1 / 2)
    assert q["per_class"]["c"]["recall"] == 0.0 and q["per_class"]["c"]["support"] == 1
    assert q["confusion"]["c"] == {ERROR_COLUMN: 1}
    assert q["macro_f1"] == pytest.approx((2 / 3 + 1 / 2 + 0) / 3)


def test_macro_f1_ignores_classes_with_no_gold_support():
    q = metrics.classification_quality([("a", "a"), ("a", "a")], LABELS)
    assert q["macro_f1"] == 1.0  # b and c have no support, so they do not drag it down


def test_calibration_perfect_and_overconfident():
    perfect = [(0.8, True)] * 8 + [(0.8, False)] * 2
    assert metrics.calibration(perfect)["ece"] == pytest.approx(0.0, abs=1e-9)
    overconfident = [(0.95, True)] * 5 + [(0.95, False)] * 5
    assert metrics.calibration(overconfident)["ece"] == pytest.approx(0.45)
    assert metrics.calibration([])["ece"] is None


def test_thresholds_trade_coverage_for_accuracy():
    samples = [(0.99, True)] * 6 + [(0.6, True), (0.6, False), (0.55, False), (0.5, False)]
    t = {row["threshold"]: row for row in metrics.calibration(samples)["thresholds"]}
    assert t[0.5]["coverage"] == 1.0 and t[0.5]["accuracy"] == pytest.approx(7 / 10)
    assert t[0.9]["coverage"] == 0.6 and t[0.9]["accuracy"] == 1.0
    assert metrics.calibration([(0.1, True)])["thresholds"][3]["accuracy"] is None


def test_probability_of_exactly_one_lands_in_the_top_bucket():
    cal = metrics.calibration([(1.0, True), (1.0, True)])
    assert cal["buckets"][0]["range"][1] == 1.0 and cal["buckets"][0]["n"] == 2


def test_percentiles_nearest_rank():
    values = list(range(1, 101))
    assert metrics.percentile(values, 50) == 50 and metrics.percentile(values, 95) == 95
    assert metrics.percentile([], 50) is None
    assert metrics.latency_stats([5, 1, 9]) == {"p50": 5, "p95": 9, "max": 9}


def test_mcnemar_exact_known_values():
    assert metrics.mcnemar_exact(5, 1) == pytest.approx(0.21875)
    assert metrics.mcnemar_exact(0, 0) == 1.0
    assert metrics.mcnemar_exact(10, 0) == pytest.approx(2 / 1024)
    assert metrics.mcnemar_exact(3, 3) == 1.0


def test_consistency():
    runs = {
        "i1": ["a", "a", "a"],
        "i2": ["a", "b"],
        "i3": ["a"],
        "i4": ["a", None],
        "i5": ["b", "b"],
    }
    # comparable: i1 (same), i2 (differs), i5 (same); i3 single run, i4 only one successful
    assert metrics.consistency(runs) == pytest.approx(2 / 3)
    assert metrics.consistency({"x": ["a"]}) is None
    assert math.isclose(metrics.consistency({"x": ["a", "a"]}), 1.0)
