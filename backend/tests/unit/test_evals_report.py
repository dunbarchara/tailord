import pytest

from evals import report, runner
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
        "input_hash": runner.input_hash(TASK, next(i for i in ITEMS if i.id == item)),
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
    store = ResultStore("toy", model, tmp_path)
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
    r = report.build_report(TASK, ITEMS, root=results)
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
    weak = report.build_report(TASK, ITEMS, root=results)["models"]["weak"]
    subsets = weak["agreed_subsets"]
    assert subsets["unanimous"]["n"] == 3 and subsets["contested"]["n"] == 1
    assert subsets["contested"]["accuracy"] == 0.0  # i3: weak said a, agreed says b


def test_calibration_only_where_a_model_reports_probabilities(results):
    r = report.build_report(TASK, ITEMS, root=results)["models"]
    assert r["strong"]["calibration"]["agreed"]["n"] == 4
    assert r["weak"]["calibration"]["agreed"] is None


def test_pairwise_mcnemar_counts_discordant_items(results):
    pair = report.build_report(TASK, ITEMS, root=results)["pairwise"][0]
    # strong right on i1, i2, i3 where weak is wrong; weak never right where strong is wrong.
    assert (pair["a"], pair["b"]) == ("strong", "weak")
    assert pair["only_a_correct"] == 3 and pair["only_b_correct"] == 0
    assert pair["p_value"] == pytest.approx(0.25)


def test_partial_results_default_to_the_items_that_ran_and_all_items_shows_coverage(tmp_path):
    seed(tmp_path, "m", [rec("i0", "a"), rec("i1", "a")])
    default = report.build_report(TASK, ITEMS, root=tmp_path)
    assert default["n_items"] == 2 and default["models"]["m"]["coverage"] == 1.0
    full = report.build_report(TASK, ITEMS, root=tmp_path, all_items=True)
    assert full["n_items"] == 4 and full["models"]["m"]["coverage"] == 0.5
    assert full["models"]["m"]["quality"]["agreed"]["n"] == 2  # only what ran is scored


def test_stale_results_are_ignored(tmp_path):
    stale = {**rec("i0", "b"), "input_hash": "deadbeef"}
    seed(tmp_path, "m", [stale, rec("i1", "a")])
    m = report.build_report(TASK, ITEMS, root=tmp_path)["models"]["m"]
    assert m["n_results"] == 1  # i0's answer was for an input that no longer exists


def test_markdown_has_the_comparison_table_and_per_model_sections(results):
    r = report.build_report(TASK, ITEMS, root=results)
    md = report.render_markdown(r, list(TASK.labels))
    assert (
        "| model | coverage | no answer | acc vs agreed | acc vs silver:opus | acc vs silver:sonnet |"
        in md
    )
    assert "| strong | 100% | 0 | 100.0%" in md and "## weak" in md
    assert "Errors: ValidationError x1" in md
    assert "p = 0.250 (no significant difference)" in md
    assert "If only answers at or above a confidence were kept" in md  # strong only


def test_write_report_creates_json_and_markdown(results):
    r = report.build_report(TASK, ITEMS, root=results)
    json_path, md_path = report.write_report(r, list(TASK.labels), results / "toy")
    assert json_path.exists() and md_path.read_text().startswith("# Eval report: toy")


def test_repeats_feed_consistency_but_not_the_sample_size(tmp_path):
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
    m = report.build_report(TASK, ITEMS, root=tmp_path)["models"]["m"]
    assert m["consistency"] == 0.5
    assert m["quality"]["agreed"]["n"] == 2  # first run only: repeats do not inflate n
    assert m["n_results"] == 4 and m["coverage"] == 1.0  # coverage counts distinct items
    assert [(x["run"], x["accuracy"]) for x in m["accuracy_by_run"]] == [(0, 1.0), (1, 0.5)]


def test_classes_absent_from_the_data_render_as_na_not_zero(tmp_path):
    task = ClassificationTask("toy", {"a": "x", "b": "y", "c": "z"}, "Pick.", str)
    records = [{**rec(i.id, "a"), "input_hash": runner.input_hash(task, i)} for i in ITEMS[:2]]
    seed(tmp_path, "m", records)
    md = report.render_markdown(
        report.build_report(task, ITEMS[:2], root=tmp_path), list(task.labels)
    )
    assert "| c | n/a | n/a | n/a | 0 |" in md and "| a | 1.00 | 1.00 | 1.00 | 2 |" in md


def test_rate_limited_items_are_excluded_from_scores_flagged_and_not_counted_as_wrong(tmp_path):
    seed(
        tmp_path,
        "m",
        [
            rec("i0", "a"),
            rec("i1", "a"),
            rec("i2", None, error="RateLimitError", cost=None),
            rec("i3", None, error="RateLimitError", cost=None),
        ],
    )
    r = report.build_report(TASK, ITEMS, root=tmp_path)
    m = r["models"]["m"]
    assert m["unanswered"] == 2 and m["unanswered_by_type"] == {"RateLimitError": 2}
    assert m["quality"]["agreed"]["n"] == 2 and m["quality"]["agreed"]["accuracy"] == 1.0
    assert m["quality"]["agreed"]["n_errors"] == 0  # not wrong: never answered
    assert m["coverage"] == 0.5 and m["reliability"]["error_rate"] == 0.0
    md = report.render_markdown(r, list(TASK.labels))
    assert "**INCOMPLETE:** m has 2 item(s) with no answer yet" in md
    assert "No answer (transient, excluded from scores): RateLimitError x2" in md


def test_model_errors_still_count_as_wrong_but_pairwise_skips_unanswered_items(tmp_path):
    seed(tmp_path, "a", [rec("i0", "a"), rec("i1", "a"), rec("i2", "b"), rec("i3", "b")])
    seed(
        tmp_path,
        "b",
        [
            rec("i0", "a"),
            rec("i1", None, error="RateLimitError", cost=None),
            rec("i2", None, error="ValidationError"),
            rec("i3", "b"),
        ],
    )
    r = report.build_report(TASK, ITEMS, root=tmp_path)
    assert r["models"]["b"]["quality"]["agreed"]["n_errors"] == 1  # ValidationError only
    pair = r["pairwise"][0]
    assert pair["n"] == 3  # i1 dropped: b never answered it
    assert pair["only_a_correct"] == 1 and pair["only_b_correct"] == 0  # i2


def test_adjudicated_labels_become_the_reference_and_are_scored_alongside_agreed(tmp_path):
    # i3 is relabeled from b to a after review; "strong" answered b there, "weak" answered a.
    items = [*ITEMS[:3], EvalItem("i3", {}, {**ITEMS[3].labels, "adjudicated": "a"})]
    items = [
        EvalItem(
            i.id,
            i.input,
            {**i.labels, "adjudicated": i.labels.get("adjudicated", i.labels["agreed"])},
        )
        for i in items
    ]
    seed(tmp_path, "strong", [rec("i0", "a"), rec("i1", "a"), rec("i2", "b"), rec("i3", "b")])
    seed(tmp_path, "weak", [rec("i0", "a"), rec("i1", "a"), rec("i2", "b"), rec("i3", "a")])
    r = report.build_report(TASK, items, root=tmp_path)
    assert r["reference"] == "adjudicated"
    strong, weak = r["models"]["strong"]["quality"], r["models"]["weak"]["quality"]
    assert strong["agreed"]["accuracy"] == 1.0 and strong["adjudicated"]["accuracy"] == 0.75
    assert weak["agreed"]["accuracy"] == 0.75 and weak["adjudicated"]["accuracy"] == 1.0
    sources = {p["source"] for p in r["pairwise"]}
    assert sources == {"agreed", "adjudicated"}
    md = report.render_markdown(r, list(TASK.labels))
    assert "use the **adjudicated** labels" in md and "macro-F1 (adjudicated)" in md
    assert "- vs adjudicated labels:" in md and "- vs agreed labels:" in md


def test_contested_items_ignore_the_adjudicated_source(tmp_path):
    # Adjudication changes labels, not whether the independent silver sources disagreed.
    items = [EvalItem(i.id, i.input, {**i.labels, "adjudicated": "a"}) for i in ITEMS]
    seed(tmp_path, "m", [rec(i.id, "a") for i in ITEMS])
    m = report.build_report(TASK, items, root=tmp_path)["models"]["m"]
    assert m["agreed_subsets"]["contested"]["n"] == 1  # only i3, where sonnet and opus split
