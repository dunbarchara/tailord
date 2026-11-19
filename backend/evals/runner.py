"""Runner: task x models x items, with cost estimates, a spend cap, and resumable results.

Spend is opt-in. `plan` prices the work and `execute` only makes paid calls under an explicit
cap. When the cap is reached the runner stops dispatching, lets in-flight calls finish
(overshoot is bounded by the concurrency and reported), then pauses for a decision or
aborts. Every call's result is appended to disk as it completes, so a crash, a rate limit
or an abort never repeats a paid call.
"""

import hashlib
import json
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import mean

from evals.adapters.base import PROMPT_VERSION, Adapter, CallResult
from evals.store import DATA_DIR, canonical
from evals.tasks.base import ClassificationTask, EvalItem

RESULTS_DIR = DATA_DIR.parent / "results"
CALIBRATION_MIN_RECORDS = 20
CAP_PADDING = 1.5  # suggested cap = estimate x this (schema retries, estimation error)
TOP_UP_PADDING = 1.2

# Errors worth re-trying on resume: the call never produced a model answer. Anything else
# (invalid labels, schema failures after retries) is a measured outcome of the model, and
# repeating it would only spend money.
TRANSIENT_ERRORS = frozenset(
    {
        "JevRateLimitedError",
        "JevConnectionError",
        "RateLimitError",
        "APIConnectionError",
        "APITimeoutError",
        "InternalServerError",
    }
)


# ── Results on disk ───────────────────────────────────────────────────────────


def task_hash(task: ClassificationTask) -> str:
    """Identity of the task as models see it: its name, labels and instructions, plus the
    adapters' prompt version. Changing any of them invalidates earlier results."""
    payload = {
        "name": task.name,
        "labels": task.labels,
        "ins": task.instructions,
        "prompt_version": PROMPT_VERSION,
    }
    return hashlib.sha256(canonical(payload).encode()).hexdigest()[:12]


def input_hash(task: ClassificationTask, item: EvalItem) -> str:
    """Identity of one question put to a model. A stored result is reused only while this
    still matches, so results survive adding or removing other items but never go stale."""
    payload = {"task": task_hash(task), "id": item.id, "input": item.input}
    return hashlib.sha256(canonical(payload).encode()).hexdigest()[:12]


def is_done(record: dict) -> bool:
    return record.get("error") not in TRANSIENT_ERRORS


class ResultStore:
    """Append-only JSONL per (task, model). The last record for an (item, run) wins, so a
    retried transient failure, or a rerun after the input changed, supersedes the earlier
    record. Each record carries the `input_hash` it answered."""

    def __init__(self, task: str, model: str, root: Path = RESULTS_DIR) -> None:
        self.path = root / task / f"{model}.jsonl"
        self._lock = threading.Lock()

    def load(self) -> dict[tuple[str, int], dict]:
        records: dict[tuple[str, int], dict] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    records[(r["item_id"], r["run"])] = r
        return records

    def append(self, record: dict) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(canonical(record) + "\n")


# ── Pricing and estimates ─────────────────────────────────────────────────────


def price_for(model: str) -> dict[str, float] | None:
    """USD per 1M tokens {input, cached, output} for a registry model, or None if unpriced."""
    from app.clients.llm_registry import get_registry
    from app.core.llm_pricing import get_pricing

    return get_pricing(get_registry().models[model].model)


def cost_usd(price: dict[str, float] | None, tokens_in: int, tokens_out: int) -> float | None:
    if price is None:
        return None
    return (tokens_in * price["input"] + tokens_out * price["output"]) / 1_000_000


@dataclass
class ModelPlan:
    model: str
    todo: int
    est_tokens_in: int
    est_tokens_out: int
    est_cost: float | None  # None: unpriced
    basis: str  # how input tokens were estimated


@dataclass
class Plan:
    task: ClassificationTask
    models: list[ModelPlan]
    units: list[tuple[str, EvalItem, int]] = field(
        repr=False, default_factory=list
    )  # (model, item, run)
    unit_cost: dict[tuple[str, str, int], float] = field(repr=False, default_factory=dict)

    @property
    def priced_estimate(self) -> float:
        return sum(m.est_cost or 0.0 for m in self.models)

    @property
    def unpriced_models(self) -> list[str]:
        return [m.model for m in self.models if m.todo and m.est_cost is None]

    @property
    def suggested_cap(self) -> float:
        return self.priced_estimate * CAP_PADDING


def _overhead(
    adapter: Adapter, task, items: list[EvalItem], store: ResultStore
) -> tuple[float, str]:
    """Per-call overhead tokens: observed on this model's finished calls once there are
    enough of them, else the adapter's calibrated default."""
    by_id = {i.id: i for i in items}
    deltas = [
        r["tokens_in"] - adapter.payload_tokens(task, by_id[r["item_id"]])
        for r in store.load().values()
        if r["item_id"] in by_id
        and r.get("input_hash") == input_hash(task, by_id[r["item_id"]])
        and not r.get("error")
        and r["tokens_in"]
    ]
    if len(deltas) >= CALIBRATION_MIN_RECORDS:
        return mean(deltas), f"observed overhead from {len(deltas)} calls"
    return adapter.overhead_tokens, "local token count + default overhead"


def build_plan(
    task: ClassificationTask,
    items: list[EvalItem],
    adapters: dict[str, Adapter],
    repeats: int = 1,
    results_root: Path = RESULTS_DIR,
) -> Plan:
    plan = Plan(task=task, models=[])
    per_model: dict[str, list[tuple[EvalItem, int]]] = {}
    hashes = {item.id: input_hash(task, item) for item in items}
    for model, adapter in adapters.items():
        store = ResultStore(task.name, model, results_root)
        done = {
            k
            for k, r in store.load().items()
            if is_done(r) and r.get("input_hash") == hashes.get(k[0])
        }
        per_model[model] = [
            (item, run) for item in items for run in range(repeats) if (item.id, run) not in done
        ]
        overhead, basis = _overhead(adapter, task, items, store)
        price = price_for(model)
        out_tokens = adapter.expected_output_tokens(task)
        tin = tout = 0
        for item, run in per_model[model]:
            est_in = adapter.payload_tokens(task, item) + round(overhead)
            tin, tout = tin + est_in, tout + out_tokens
            cost = cost_usd(price, est_in, out_tokens)
            plan.unit_cost[(model, item.id, run)] = cost or 0.0
        plan.models.append(
            ModelPlan(model, len(per_model[model]), tin, tout, cost_usd(price, tin, tout), basis)
        )
    # Interleave models item by item so a stopped run leaves comparable coverage.
    for i in range(max((len(v) for v in per_model.values()), default=0)):
        for model, todo in per_model.items():
            if i < len(todo):
                plan.units.append((model, *todo[i]))
    return plan


def format_plan(plan: Plan) -> str:
    rows = [
        "model".ljust(18) + "todo".rjust(6) + "est tokens in/out".rjust(22) + "est cost".rjust(12)
    ]
    for m in plan.models:
        cost = f"${m.est_cost:.4f}" if m.est_cost is not None else "unpriced"
        tokens = f"{m.est_tokens_in:,} / {m.est_tokens_out:,}"
        rows.append(m.model.ljust(18) + str(m.todo).rjust(6) + tokens.rjust(22) + cost.rjust(12))
    rows.append(f"estimate basis: {'; '.join(sorted({m.basis for m in plan.models}))}")
    rows.append(f"total estimate (priced models): ${plan.priced_estimate:.4f}")
    if plan.unpriced_models:
        rows.append(
            f"WARNING: no pricing for {', '.join(plan.unpriced_models)}: excluded from the total, "
            "and the spend cap cannot cover them. Running them needs --allow-unpriced."
        )
    return "\n".join(rows)


# ── Execution ─────────────────────────────────────────────────────────────────


@dataclass
class RunStats:
    spend: float = 0.0
    calls: int = 0
    est_done: float = 0.0  # estimated cost of completed units (progress is weighted by this)
    est_total: float = 0.0
    errors: int = 0
    cap_hits: int = 0
    aborted: bool = False
    remaining: int = 0
    cap: float = 0.0  # the cap in force when the run ended

    @property
    def progress(self) -> float:
        return self.est_done / self.est_total if self.est_total else 1.0

    @property
    def projected_total(self) -> float:
        # Before anything has finished there is no actual spend to extrapolate from.
        return self.spend / self.progress if self.est_done else self.est_total

    @property
    def overshoot(self) -> float:
        return max(self.spend - self.cap, 0.0)


# on_cap decides what happens when the cap is reached: returns the new cap, or None to stop.
CapDecision = Callable[[RunStats, float], float | None]


def interactive_decision(
    stats: RunStats,
    cap: float,
    ask: Callable[[str], str] = input,
    out: Callable[[str], None] = print,
) -> float | None:
    top_up = max(stats.projected_total - stats.spend, 0.0) * TOP_UP_PADDING
    est_spent = stats.est_done
    ratio = stats.spend / est_spent if est_spent else float("nan")
    out(
        f"\nSpend cap reached: ${stats.spend:.4f} spent of ${cap:.4f}; the next call would exceed it.\n"
        f"Progress {stats.progress:.0%} (weighted by estimated cost), {stats.remaining} calls left.\n"
        f"Estimated so far ${est_spent:.4f}, actual ${stats.spend:.4f} (actual/estimate {ratio:.2f}x).\n"
        f"Projected total ${stats.projected_total:.4f}; suggested top-up ${top_up:.4f} "
        f"(remaining projected x{TOP_UP_PADDING})."
    )
    answer = ask(
        "'continue' (add the suggested top-up), a new total cap in USD, or 'quit': "
    ).strip()
    if answer.lower() in ("continue", "c", "y", "yes"):
        return stats.spend + top_up
    try:
        new_cap = float(answer.lstrip("$"))
    except ValueError:
        return None
    return new_cap if new_cap > stats.spend else None


def abort_decision(stats: RunStats, cap: float) -> float | None:
    return None


def execute(
    plan: Plan,
    adapters: dict[str, Adapter],
    items_by_id: dict[str, EvalItem],
    cap: float,
    on_cap: CapDecision = abort_decision,
    concurrency: int = 8,
    results_root: Path = RESULTS_DIR,
    out: Callable[[str], None] = print,
    clock: Callable[[], float] = time.time,
) -> RunStats:
    """Run the plan's units, appending each result as it completes."""
    task = plan.task
    stores = {m: ResultStore(task.name, m, results_root) for m in adapters}
    prices = {m: price_for(m) for m in adapters}
    stats = RunStats(est_total=sum(plan.unit_cost.values()), remaining=len(plan.units))
    queue = list(plan.units)
    pos = 0
    inflight: dict[Future, tuple[str, str, int]] = {}
    next_report = 0.1

    def finish(fut: Future) -> None:
        nonlocal next_report
        model, item_id, run = inflight.pop(fut)
        result: CallResult = fut.result()
        price = prices[model]
        cost = cost_usd(price, result.tokens_in, result.tokens_out)
        record = {
            "task": task.name,
            "model": model,
            "item_id": item_id,
            "run": run,
            "input_hash": input_hash(task, items_by_id[item_id]),
            **{k: v for k, v in asdict(result).items()},
            "cost_usd": cost,
            "ts": clock(),
        }
        stores[model].append(record)
        stats.calls += 1
        stats.spend += cost or 0.0
        stats.est_done += plan.unit_cost[(model, item_id, run)]
        stats.remaining -= 1
        stats.errors += 0 if result.ok else 1
        if stats.progress >= next_report:
            out(f"  {stats.progress:.0%}  {stats.calls} calls  ${stats.spend:.4f}")
            next_report = (int(stats.progress * 10) + 1) / 10

    def can_dispatch() -> bool:
        """Dispatch only if the cap still holds after counting what is already in flight, so
        the cap is not overshot by a whole batch of concurrent calls."""
        if pos >= len(queue):
            return False
        model, item, run = queue[pos]
        reserved = sum(plan.unit_cost[key] for key in inflight.values())
        return stats.spend + reserved + plan.unit_cost[(model, item.id, run)] <= cap

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        while pos < len(queue) or inflight:
            while len(inflight) < concurrency and can_dispatch():
                model, item, run = queue[pos]
                pos += 1
                fut = pool.submit(adapters[model].run, task, items_by_id[item.id])
                inflight[fut] = (model, item.id, run)
            if inflight:
                done, _ = wait(list(inflight), return_when=FIRST_COMPLETED)
                for fut in done:
                    finish(fut)
            elif pos < len(queue):  # nothing in flight and the next call does not fit
                stats.cap_hits += 1
                stats.cap = cap
                new_cap = on_cap(stats, cap)
                if new_cap is None:
                    stats.aborted = True
                    break
                cap = new_cap
    stats.cap = cap
    return stats


def load_suites(path: Path | None = None) -> dict[str, dict[str, list[str]]]:
    path = path or Path(__file__).parent / "suites.json"
    return json.loads(path.read_text(encoding="utf-8"))["suites"]


def stdout_is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()
