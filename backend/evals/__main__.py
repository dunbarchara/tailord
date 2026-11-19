"""Eval harness CLI.

    uv run python -m evals run --suite vet                      # dry run: estimate only
    uv run python -m evals run --suite vet --max-spend 0.25     # paid run under a cap
    uv run python -m evals run --task semantic_type --models gpt-5.4-mini,jev-1.14.0 --limit 20
    uv run python -m evals report --task semantic_type

Spend is opt-in: without --max-spend nothing paid is called. Results are cached per task,
input fingerprint and model, so re-running only fills what is missing.
"""

import argparse
import logging
import shlex
import sys
from pathlib import Path

import structlog

from evals import runner
from evals.adapters import adapter_for
from evals.tasks import TASKS
from evals.tasks.semantic_type import load_items

LOADERS = {"semantic_type": load_items}


def _selection(args) -> dict[str, list[str]]:
    if args.suite:
        suites = runner.load_suites()
        if args.suite not in suites:
            raise SystemExit(f"unknown suite '{args.suite}'; defined: {', '.join(suites)}")
        selection = {t: list(m) for t, m in suites[args.suite].items()}
        if args.task:
            selection = {t: m for t, m in selection.items() if t == args.task}
        if args.models:
            raise SystemExit("--models overrides a task's model list; use --task with it")
    elif args.task and args.models:
        selection = {args.task: args.models.split(",")}
    else:
        raise SystemExit("choose --suite NAME, or --task T --models a,b")
    excluded = set(args.exclude.split(",")) if args.exclude else set()
    return {t: [m for m in models if m not in excluded] for t, models in selection.items()}


def cmd_run(args) -> int:
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))
    selection = _selection(args)
    exit_code = 0
    for task_name, models in selection.items():
        if task_name not in TASKS:
            raise SystemExit(f"unknown task '{task_name}'; defined: {', '.join(TASKS)}")
        task, items = TASKS[task_name], LOADERS[task_name]()
        if args.limit:
            items = items[: args.limit]
        adapters = {m: adapter_for(m) for m in models}
        plan = runner.build_plan(task, items, adapters, repeats=args.repeats)
        print(f"\nTask {task.name}: {len(items)} items x {args.repeats} run(s), inputs {plan.fp}")
        print(runner.format_plan(plan))
        if plan.unpriced_models and not args.allow_unpriced:
            print("\nRefusing to run unpriced models without --allow-unpriced.")
            exit_code = 2
            continue
        if args.max_spend is None:
            if plan.units:
                cap = max(plan.suggested_cap, 0.0001)
                print(f"\nDry run (nothing called). To run, with a cap of ${cap:.4f}:")
                print(
                    f"  uv run python -m evals {' '.join(shlex.quote(a) for a in sys.argv[1:])} "
                    f"--max-spend {cap:.4f}"
                )
            else:
                print("\nNothing to do: every item already has a result.")
            continue
        interactive = args.on_cap == "pause" and runner.stdout_is_interactive()
        stats = runner.execute(
            plan,
            adapters,
            {i.id: i for i in items},
            cap=args.max_spend,
            on_cap=runner.interactive_decision if interactive else runner.abort_decision,
            concurrency=args.concurrency,
        )
        print(
            f"\n{stats.calls} calls, ${stats.spend:.4f} spent, {stats.errors} errors"
            f"{', cap hit' if stats.cap_hits else ''}."
        )
        if stats.aborted:
            exit_code = 3
            rerun = " ".join(
                shlex.quote(a) for a in sys.argv[1:] if not a.startswith("--max-spend")
            )
            print(
                f"Stopped at the cap with {stats.remaining} calls left. Results so far are saved; resume with:"
            )
            print(f"  uv run python -m evals {rerun} --max-spend <new cap>")
    return exit_code


def cmd_report(args) -> int:
    from evals import report as report_mod

    if args.task not in TASKS:
        raise SystemExit(f"unknown task '{args.task}'; defined: {', '.join(TASKS)}")
    task, items = TASKS[args.task], LOADERS[args.task]()
    task_dir = runner.RESULTS_DIR / task.name
    fp = args.fingerprint or runner.fingerprint(task, items)
    if not (task_dir / fp).exists():
        known = (
            sorted(task_dir.glob("*"), key=lambda p: p.stat().st_mtime) if task_dir.exists() else []
        )
        if args.fingerprint or not known:
            raise SystemExit(
                f"no results for inputs {fp}. Known fingerprints: "
                f"{', '.join(p.name for p in known) or 'none'}"
            )
        # A --limit run fingerprints its subset of items; report the latest results.
        fp = known[-1].name
        print(f"(no results for the full item set; reporting the latest run, inputs {fp})\n")
    directory = task_dir / fp
    models = args.models.split(",") if args.models else None
    report = report_mod.build_report(task, items, fp, models)
    if not report["models"]:
        raise SystemExit("no results to report on")
    _, md_path = report_mod.write_report(report, list(task.labels), directory)
    print(md_path.read_text(encoding="utf-8"))
    print(f"\nWritten: {md_path} and report.json")
    if args.out:
        Path(args.out).write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Copied to {args.out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="evals")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run a task over models (dry run unless --max-spend)")
    run.add_argument("--suite")
    run.add_argument("--task")
    run.add_argument("--models", help="comma-separated registry model names (with --task)")
    run.add_argument("--exclude", help="comma-separated models to skip")
    run.add_argument("--max-spend", type=float, help="USD cap; omit for a dry run")
    run.add_argument(
        "--on-cap",
        choices=["pause", "abort"],
        default="pause",
        help="at the cap: ask what to do (needs a terminal) or stop; default pause",
    )
    run.add_argument("--concurrency", type=int, default=8)
    run.add_argument("--repeats", type=int, default=1, help="runs per item (consistency)")
    run.add_argument("--limit", type=int, help="only the first N items (cheap vetting)")
    run.add_argument("--allow-unpriced", action="store_true")
    rep = sub.add_parser("report", help="metrics and a comparison table from stored results")
    rep.add_argument("--task", required=True)
    rep.add_argument("--fingerprint", help="inputs fingerprint (default: the current inputs)")
    rep.add_argument("--models", help="comma-separated; default: every model with results")
    rep.add_argument("--out", help="also copy the markdown here (e.g. a path under planning/)")
    args = ap.parse_args()
    return cmd_report(args) if args.cmd == "report" else cmd_run(args)


if __name__ == "__main__":
    raise SystemExit(main())
