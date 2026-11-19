import pytest

from evals import report
from evals.runner import ResultStore
from evals.tasks.base import ClassificationTask, EvalItem

TASK = ClassificationTask("toy", {"a": "x", "b": "y"}, "Pick.", str)
# Four items. Sources disagree on i3 (sonnet=a, opus=b, agreed=b); everything else is unanimous.
ITEMS = [
    EvalItem("i0", {}, {"silver:sonnet": "a", "silver:opus": "a", "agreed": "a"}),
    EvalItem("i1", {}, {"silver:sonnet": "a", "silver:opus": "a", "agreed": "a"}),
    EvalItem("i2", {}, {"silver:sonnet": "b", "silver:opus": "b", "agreed": "b"}),
    EvalItem("i3", {}, {"silver:sonnet": "a", "silver:opus": "b", "agreed": "b"}),
]


def rec(item, pred, probs=None, error=None, cost=0.01, run=0, ms=100, attempts=1):
    return {
        "task": "toy",
        "model": "m",
        "item_id": item,
        "run": run,
        "prediction": pred,
        "confidence": None,
        "probabilities": probs,
        "tokens_in": 100,
        "tokens_out": 5,
        "latency_ms": ms,
        "attempts": attempts,
        "error": error,
        "detail": {},
        "cost_usd": cost,
        "ts": 0,
    }


def seed(tmp_path, model, records):
    store = ResultStore("toy", "fp1", model, tmp_path)
    for r in records:
        store.append({**r, "model": model})


@pytest.fixture
def results(tmp_path):
    # "strong" is right on everything the agreed labels say, and reports probabilities.
    seed(
        tmp_path,
        "strong",
        [
            rec("i0", "a", {"a": 0.9, "b": 0.1}),
            rec("i1", "a", {"a": 0.8, "b": 0.2}),
            rec("i2", "b", {"a": 0.1, "b": 0.9}),
            rec("i3", "b", {"a": 0.4, "b": 0.6}),
        ],
    )
    # "weak" misses i1 and i3, errors on i2 (a transient-looking failure), no probabilities.
    seed(
        tmp_path,
        "weak",
        [
            rec("i0", "a"),
            rec("i1", "b", attempts=2),
            rec("i2", None, error="ValidationError", cost=0.02),
            rec("i3", "a"),
        ],
    )
    return tmp_path


def test_model_report_quality_per_source_and_error_accounting(results):
    r = report.build_report(TASK, ITEMS, "fp1", root=results)
    strong, weak = r["models"]["strong"], r["models"]["weak"]
    assert strong["quality"]["agreed"]["accuracy"] == 1.0
    assert strong["quality"]["silver:sonnet"]["accuracy"] == pytest.approx(3 / 4)  # i3 contested
    assert weak["quality"]["agreed"]["accuracy"] == pytest.approx(1 / 4)
    assert weak["quality"]["agreed"]["n_errors"] == 1
    assert weak["reliability"] == {
        "error_rate": 0.25,
        "retry_rate": 0.25,
        "errors_by_type": {"ValidationError": 1},
    }
    assert weak["cost"]["total_usd"] == pytest.approx(0.05) and weak["coverage"] == 1.0


def test_contested_items_are_separated_from_unanimous_ones(results):
    weak = report.build_report(TASK, ITEMS, "fp1", root=results)["models"]["weak"]
    subsets = weak["agreed_subsets"]
    assert subsets["unanimous"]["n"] == 3 and subsets["contested"]["n"] == 1
    assert subsets["contested"]["accuracy"] == 0.0  # i3: weak said a, agreed says b


def test_calibration_only_where_a_model_reports_probabilities(results):
    r = report.build_report(TASK, ITEMS, "fp1", root=results)["models"]
    assert r["strong"]["calibration"]["agreed"]["n"] == 4
    assert r["weak"]["calibration"]["agreed"] is None


def test_pairwise_mcnemar_counts_discordant_items(results):
    pair = report.build_report(TASK, ITEMS, "fp1", root=results)["pairwise_agreed"][0]
    # strong right on i1, i2, i3 where weak is wrong; weak never right where strong is wrong.
    assert (pair["a"], pair["b"]) == ("strong", "weak")
    assert pair["only_a_correct"] == 3 and pair["only_b_correct"] == 0
    assert pair["p_value"] == pytest.approx(0.25)


def test_partial_results_report_coverage_and_score_only_what_ran(tmp_path):
    seed(tmp_path, "m", [rec("i0", "a"), rec("i1", "a")])
    m = report.build_report(TASK, ITEMS, "fp1", root=tmp_path)["models"]["m"]
    assert m["coverage"] == 0.5 and m["quality"]["agreed"]["n"] == 2


def test_markdown_has_the_comparison_table_and_per_model_sections(results):
    r = report.build_report(TASK, ITEMS, "fp1", root=results)
    md = report.render_markdown(r, list(TASK.labels))
    assert "| model | coverage | acc vs agreed | acc vs silver:opus | acc vs silver:sonnet |" in md
    assert "| strong | 100% | 100.0%" in md and "## weak" in md
    assert "Errors: ValidationError x1" in md
    assert "p = 0.250 (no significant difference)" in md
    assert "If only answers at or above a confidence were kept" in md  # strong only


def test_write_report_creates_json_and_markdown(results):
    r = report.build_report(TASK, ITEMS, "fp1", root=results)
    json_path, md_path = report.write_report(r, list(TASK.labels), results / "toy" / "fp1")
    assert json_path.exists() and md_path.read_text().startswith("# Eval report: toy")


def test_repeats_feed_consistency(tmp_path):
    seed(
        tmp_path,
        "m",
        [
            rec("i0", "a", run=0),
            rec("i0", "a", run=1),
            rec("i1", "a", run=0),
            rec("i1", "b", run=1),
        ],
    )
    m = report.build_report(TASK, ITEMS, "fp1", root=tmp_path)["models"]["m"]
    assert m["consistency"] == 0.5
