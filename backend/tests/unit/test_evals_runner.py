import pytest

from evals import runner
from evals.adapters.base import CallResult
from evals.tasks.base import ClassificationTask, EvalItem

TASK = ClassificationTask(
    name="toy", labels={"a": "first", "b": "second"}, instructions="Pick.", render_state=str
)
ITEMS = [EvalItem(f"i{n}", {"n": n}, {"agreed": "a"}) for n in range(6)]
BY_ID = {i.id: i for i in ITEMS}
# $1 per 1M input tokens and 100k tokens per call: every call costs exactly $0.10.
PRICE = {"input": 1.0, "cached": 0.0, "output": 0.0}
CALL_TOKENS = 100_000


class Fake:
    overhead_tokens = 5

    def __init__(self, model, results=None):
        self.model = model
        self.calls = []
        self.results = results or {}

    def run(self, task, item):
        self.calls.append(item.id)
        return self.results.get(item.id) or CallResult(
            prediction="a", tokens_in=CALL_TOKENS, tokens_out=0, latency_ms=10
        )

    def payload_tokens(self, task, item):
        return CALL_TOKENS - self.overhead_tokens

    def expected_output_tokens(self, task):
        return 0


@pytest.fixture(autouse=True)
def priced(monkeypatch):
    monkeypatch.setattr(runner, "price_for", lambda model: PRICE)


def plan_for(adapters, tmp_path, items=ITEMS, repeats=1):
    return runner.build_plan(TASK, items, adapters, repeats, results_root=tmp_path)


def run(adapters, tmp_path, cap, **kwargs):
    plan = plan_for(adapters, tmp_path)
    return plan, runner.execute(plan, adapters, BY_ID, cap, results_root=tmp_path, **kwargs)


def test_fingerprint_tracks_task_and_inputs():
    base = runner.fingerprint(TASK, ITEMS)
    assert base == runner.fingerprint(TASK, ITEMS)
    changed_item = [EvalItem("i0", {"n": 99}, {}), *ITEMS[1:]]
    assert runner.fingerprint(TASK, changed_item) != base
    retitled = ClassificationTask("toy", TASK.labels, "Different.", str)
    assert runner.fingerprint(retitled, ITEMS) != base


def test_plan_prices_work_interleaves_models_and_suggests_a_cap(tmp_path):
    adapters = {"m1": Fake("m1"), "m2": Fake("m2")}
    plan = plan_for(adapters, tmp_path)
    assert [m.todo for m in plan.models] == [6, 6]
    assert plan.models[0].est_cost == pytest.approx(0.6)
    assert plan.priced_estimate == pytest.approx(1.2)
    assert plan.suggested_cap == pytest.approx(1.2 * runner.CAP_PADDING)
    assert [(m, i.id) for m, i, _ in plan.units[:4]] == [
        ("m1", "i0"),
        ("m2", "i0"),
        ("m1", "i1"),
        ("m2", "i1"),
    ]


def test_unpriced_model_is_flagged_and_excluded_from_the_estimate(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "price_for", lambda m: None if m == "free" else PRICE)
    plan = plan_for({"m1": Fake("m1"), "free": Fake("free")}, tmp_path)
    assert plan.unpriced_models == ["free"]
    assert plan.priced_estimate == pytest.approx(0.6)
    assert "needs --allow-unpriced" in runner.format_plan(plan)


def test_full_run_stores_results_and_a_second_run_has_nothing_to_do(tmp_path):
    adapters = {"m1": Fake("m1")}
    plan, stats = run(adapters, tmp_path, cap=10)
    assert stats.calls == 6 and stats.spend == pytest.approx(0.6) and not stats.aborted
    assert len(adapters["m1"].calls) == 6
    stored = runner.ResultStore("toy", plan.fp, "m1", tmp_path).load()
    assert len(stored) == 6 and stored[("i3", 0)]["cost_usd"] == pytest.approx(0.1)
    assert plan_for(adapters, tmp_path).units == []  # resume repeats no paid call


def test_cap_stops_dispatching_aborts_and_resumes_without_repeating_calls(tmp_path):
    adapters = {"m1": Fake("m1")}
    plan, stats = run(adapters, tmp_path, cap=0.25, concurrency=1)
    assert stats.aborted and stats.cap_hits == 1
    assert stats.calls == 3 and stats.remaining == 3  # crossed the cap on the third call
    # Resume: only the unfinished items are planned and called.
    adapters2 = {"m1": Fake("m1")}
    plan2, stats2 = run(adapters2, tmp_path, cap=10)
    assert sorted(adapters2["m1"].calls) == ["i3", "i4", "i5"] and not stats2.aborted


def test_overshoot_is_bounded_by_concurrency(tmp_path):
    many = [EvalItem(f"j{n}", {"n": n}, {}) for n in range(40)]  # far more work than the cap
    adapters = {"m1": Fake("m1")}
    plan = plan_for(adapters, tmp_path, items=many)
    stats = runner.execute(
        plan, adapters, {i.id: i for i in many}, 0.25, concurrency=4, results_root=tmp_path
    )
    assert stats.aborted and stats.remaining > 0
    # At most `concurrency - 1` calls can already be in flight when the cap is crossed.
    assert 0.25 <= stats.spend <= 0.25 + 3 * 0.1 + 0.1 + 1e-9


def test_pause_can_raise_the_cap_and_continue(tmp_path):
    seen = []

    def decide(stats, cap):
        seen.append((round(stats.progress, 2), cap))
        return 10.0

    _, stats = run({"m1": Fake("m1")}, tmp_path, cap=0.25, concurrency=1, on_cap=decide)
    assert not stats.aborted and stats.calls == 6 and stats.cap_hits == 1
    assert seen == [(0.5, 0.25)]


def test_transient_errors_are_retried_on_resume_but_model_errors_are_kept(tmp_path):
    results = {
        "i0": CallResult(error="JevRateLimitedError", attempts=5),
        "i1": CallResult(error="InvalidLabel", tokens_in=CALL_TOKENS),
    }
    adapters = {"m1": Fake("m1", results)}
    run(adapters, tmp_path, cap=10)
    again = plan_for({"m1": Fake("m1")}, tmp_path)
    assert [i.id for _, i, _ in again.units] == ["i0"]  # i1's InvalidLabel is a real outcome


def test_failed_calls_still_count_what_they_cost(tmp_path):
    bad = CallResult(error="ValidationError", tokens_in=CALL_TOKENS, attempts=3)
    _, stats = run({"m1": Fake("m1", {"i0": bad})}, tmp_path, cap=10)
    assert stats.errors == 1 and stats.spend == pytest.approx(0.6)


def test_repeats_are_separate_units(tmp_path):
    plan = plan_for({"m1": Fake("m1")}, tmp_path, items=ITEMS[:2], repeats=3)
    assert len(plan.units) == 6 and {r for _, _, r in plan.units} == {0, 1, 2}


def test_estimate_recalibrates_from_observed_overhead(tmp_path):
    adapters = {"m1": Fake("m1")}
    # Observed calls used 40 tokens more than the payload count, versus the default of 5.
    items = ITEMS + [EvalItem(f"x{n}", {"n": n}, {}) for n in range(25)]
    store = runner.ResultStore("toy", runner.fingerprint(TASK, items), "m1", tmp_path)
    for n in range(25):
        store.append({"item_id": f"x{n}", "run": 0, "tokens_in": CALL_TOKENS + 35, "error": None})
    plan = runner.build_plan(TASK, items, adapters, results_root=tmp_path)
    assert "observed overhead from 25 calls" in plan.models[0].basis
    assert plan.models[0].est_tokens_in == 6 * (CALL_TOKENS - 5 + 40)


class TestInteractiveDecision:
    def stats(self):
        s = runner.RunStats(spend=0.3, est_done=0.2, est_total=0.8, remaining=5)
        return s  # progress 25%, projected total 1.2

    def decide(self, answer):
        lines = []
        result = runner.interactive_decision(
            self.stats(), 0.3, ask=lambda prompt: answer, out=lines.append
        )
        return result, "\n".join(lines)

    def test_continue_adds_the_padded_remaining_projection(self):
        result, text = self.decide("continue")
        assert result == pytest.approx(0.3 + (1.2 - 0.3) * runner.TOP_UP_PADDING)
        assert "Progress 25%" in text and "1.50x" in text and "Projected total $1.2000" in text

    def test_custom_cap_must_exceed_spend(self):
        assert self.decide("$2.5")[0] == 2.5
        assert self.decide("0.1")[0] is None

    @pytest.mark.parametrize("answer", ["quit", "q", "", "nonsense"])
    def test_anything_else_stops(self, answer):
        assert self.decide(answer)[0] is None


def test_dry_run_never_calls_a_model(tmp_path, monkeypatch, capsys):
    from evals import __main__ as cli

    fake = Fake("m1")
    monkeypatch.setattr(cli, "adapter_for", lambda name: fake)
    monkeypatch.setattr(cli, "TASKS", {"toy": TASK})
    monkeypatch.setitem(cli.LOADERS, "toy", lambda: ITEMS)
    args = cli.argparse.Namespace(
        suite=None,
        task="toy",
        models="m1",
        exclude=None,
        max_spend=None,
        on_cap="abort",
        concurrency=2,
        repeats=1,
        limit=None,
        allow_unpriced=False,
    )
    monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path)
    assert cli.cmd_run(args) == 0
    out = capsys.readouterr().out
    assert "Dry run (nothing called)" in out and "--max-spend" in out
    assert fake.calls == []
