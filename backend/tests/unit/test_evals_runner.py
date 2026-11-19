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


def test_input_hash_tracks_the_task_and_each_items_own_input():
    base = runner.input_hash(TASK, ITEMS[0])
    assert base == runner.input_hash(TASK, ITEMS[0])
    assert runner.input_hash(TASK, EvalItem("i0", {"n": 99}, {})) != base
    retitled = ClassificationTask("toy", TASK.labels, "Different.", str)
    assert runner.input_hash(retitled, ITEMS[0]) != base
    relabeled = ClassificationTask("toy", {"a": "x"}, TASK.instructions, str)
    assert runner.input_hash(relabeled, ITEMS[0]) != base
    # Other items changing, or being added, does not touch this item's identity.
    assert runner.input_hash(TASK, ITEMS[0]) == base != runner.input_hash(TASK, ITEMS[1])


def test_prompt_version_bump_invalidates_results(monkeypatch):
    before = runner.input_hash(TASK, ITEMS[0])
    monkeypatch.setattr(runner, "PROMPT_VERSION", 2)
    assert runner.input_hash(TASK, ITEMS[0]) != before


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
    stored = runner.ResultStore("toy", "m1", tmp_path).load()
    assert len(stored) == 6 and stored[("i3", 0)]["cost_usd"] == pytest.approx(0.1)
    assert stored[("i3", 0)]["input_hash"] == runner.input_hash(TASK, BY_ID["i3"])
    assert plan_for(adapters, tmp_path).units == []  # resume repeats no paid call


def test_cap_stops_before_the_call_that_would_exceed_it_and_resume_repeats_nothing(tmp_path):
    adapters = {"m1": Fake("m1")}
    plan, stats = run(adapters, tmp_path, cap=0.25, concurrency=1)
    # Two calls fit ($0.20); a third would reach $0.30 > $0.25, so it is never made.
    assert stats.aborted and stats.cap_hits == 1 and stats.overshoot == 0
    assert stats.calls == 2 and stats.remaining == 4 and stats.cap == 0.25
    adapters2 = {"m1": Fake("m1")}
    plan2, stats2 = run(adapters2, tmp_path, cap=10)
    assert sorted(adapters2["m1"].calls) == ["i2", "i3", "i4", "i5"] and not stats2.aborted


def test_in_flight_calls_are_reserved_so_concurrency_cannot_overshoot_the_cap(tmp_path):
    many = [EvalItem(f"j{n}", {}, {}) for n in range(40)]  # far more work than the cap
    adapters = {"m1": Fake("m1")}
    plan = plan_for(adapters, tmp_path, items=many)
    stats = runner.execute(
        plan, adapters, {i.id: i for i in many}, 0.25, concurrency=8, results_root=tmp_path
    )
    assert stats.aborted and stats.calls == 2  # 3 x $0.10 would break the cap, however many workers
    assert stats.spend == pytest.approx(0.2) and stats.overshoot == 0


def test_underestimated_calls_can_still_overshoot_and_it_is_reported(tmp_path):
    expensive = CallResult(
        prediction="a", tokens_in=CALL_TOKENS * 3, tokens_out=0
    )  # 3x the estimate
    adapters = {"m1": Fake("m1", {i.id: expensive for i in ITEMS})}
    _, stats = run(adapters, tmp_path, cap=0.25, concurrency=2)
    assert stats.overshoot > 0 and stats.spend > 0.25


def test_pause_can_raise_the_cap_and_continue(tmp_path):
    seen = []

    def decide(stats, cap):
        seen.append((round(stats.progress, 2), cap))
        return 10.0

    _, stats = run({"m1": Fake("m1")}, tmp_path, cap=0.25, concurrency=1, on_cap=decide)
    assert not stats.aborted and stats.calls == 6 and stats.cap_hits == 1
    assert seen == [(0.33, 0.25)]


def test_a_cap_below_the_first_call_pauses_immediately_with_a_sane_projection(tmp_path):
    seen = []

    def decide(stats, cap):
        seen.append(stats.projected_total)
        return None

    _, stats = run({"m1": Fake("m1")}, tmp_path, cap=0.05, on_cap=decide)
    assert stats.calls == 0 and stats.aborted
    assert seen == [pytest.approx(0.6)]  # the plan's estimate, not 0 or a division error


def test_results_are_reused_when_the_item_set_changes_but_not_when_an_input_does(tmp_path):
    adapters = {"m1": Fake("m1")}
    run(adapters, tmp_path, cap=10)  # all six items done
    more = ITEMS + [EvalItem("i6", {"n": 6}, {})]
    plan = plan_for(adapters, tmp_path, items=more)
    assert [i.id for _, i, _ in plan.units] == ["i6"]  # only the new item needs paying for
    edited = [EvalItem("i0", {"n": 123}, {}), *ITEMS[1:]]
    plan = plan_for(adapters, tmp_path, items=edited)
    assert [i.id for _, i, _ in plan.units] == ["i0"]  # i0's input changed, so its result is stale


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
    items = ITEMS + [EvalItem(f"x{n}", {"n": n}, {}) for n in range(25)]
    # Observed calls used 40 tokens more than the payload count, versus the default of 5.
    store = runner.ResultStore("toy", "m1", tmp_path)
    for n in range(25):
        item = items[6 + n]
        store.append(
            {
                "item_id": item.id,
                "run": 0,
                "input_hash": runner.input_hash(TASK, item),
                "tokens_in": CALL_TOKENS + 35,
                "error": None,
            }
        )
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


@pytest.mark.parametrize(
    "argv, expected",
    [
        (
            ["run", "--suite", "vet", "--max-spend", "0.004", "--on-cap", "abort"],
            "run --suite vet --on-cap abort",
        ),
        (["run", "--max-spend=0.5", "--limit", "40"], "run --limit 40"),
        (["run", "--suite", "vet"], "run --suite vet"),
    ],
)
def test_resume_command_drops_max_spend_and_its_value(argv, expected):
    from evals import __main__ as cli

    assert cli._without_max_spend(argv) == expected
