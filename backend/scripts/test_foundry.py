"""
Test script for validating LLM extraction against the configured endpoint
(Azure AI Foundry, OpenAI, or local) without deploying to production.

Usage (from backend/):
    uv run python scripts/test_foundry.py
    uv run python scripts/test_foundry.py --task profile
    uv run python scripts/test_foundry.py --task job
    uv run python scripts/test_foundry.py --task tailoring
    uv run python scripts/test_foundry.py --task all        # default
    uv run python scripts/test_foundry.py --timeout 300    # seconds (default: 120)
"""

import argparse
import json
import os
import sys
import textwrap
import traceback
from pathlib import Path

# Make `app` importable when running from scripts/ or backend/
sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_RESUME = textwrap.dedent("""
    Jane Smith
    jane.smith@example.com | linkedin.com/in/janesmith | github.com/janesmith

    EXPERIENCE

    Acme Corp – Senior Software Engineer                          Austin, TX
    Platform Team                                          06/2021 – Present
    • Led migration of monolith to microservices, reducing p99 latency by 40%.
    • Designed internal developer platform used by 120+ engineers.
    • Mentored 4 junior engineers; 3 promoted within 18 months.

    Startup Inc – Software Engineer                              Remote
                                                         01/2019 – 05/2021
    • Built real-time analytics pipeline processing 500k events/day (Kafka, Flink).
    • Owned full-stack feature delivery (React, Node.js, PostgreSQL).

    SKILLS
    Python, TypeScript, Go, Kubernetes, Docker, Terraform, AWS, PostgreSQL, Kafka

    EDUCATION
    University of Texas at Austin – B.S. Computer Science, 2018 (GPA 3.7)

    CERTIFICATIONS
    AWS Certified Solutions Architect – Associate
""").strip()

SAMPLE_JOB = textwrap.dedent("""
    Staff Software Engineer – Platform
    Initech | San Francisco, CA (Hybrid)

    About the role:
    We're looking for a Staff Engineer to lead our developer platform efforts.
    You'll work across engineering to define standards, reduce toil, and accelerate delivery.

    Responsibilities:
    - Design and build internal tooling and developer platforms
    - Define and drive engineering best practices across teams
    - Lead cross-functional technical initiatives with product and infrastructure
    - Mentor senior and mid-level engineers

    Required qualifications:
    - 7+ years of software engineering experience
    - Strong background in distributed systems or platform engineering
    - Experience leading technical projects across multiple teams
    - Proficiency in at least one of: Python, Go, TypeScript

    Preferred qualifications:
    - Experience with Kubernetes and cloud infrastructure (AWS, GCP, or Azure)
    - Prior experience in a staff or principal engineer role
    - Open source contributions
""").strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def header(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def ok(label: str, value: object = None) -> None:
    msg = f"  [PASS] {label}"
    if value is not None:
        msg += f": {value}"
    print(msg)


def fail(label: str, exc: BaseException) -> None:
    # Classify the error so the cause is immediately obvious
    exc_type = type(exc).__name__
    if "Timeout" in exc_type or "timeout" in str(exc).lower():
        category = "TIMEOUT — model took too long; try --timeout <seconds>"
    elif "APIStatusError" in exc_type or "StatusError" in exc_type:
        category = f"API ERROR — {exc}"
    elif "ValidationError" in exc_type:
        category = f"PARSE ERROR — response did not match schema: {exc}"
    else:
        category = f"{exc_type}: {exc}"

    print(f"  [FAIL] {label}")
    print(f"  {category}")
    print()
    traceback.print_exc()


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def test_profile() -> bool:
    header("Task: profile extraction (ExtractedProfile)")
    try:
        from app.services.profile_extractor import extract_profile
        result = extract_profile(SAMPLE_RESUME)
        ok("Parsed successfully")
        ok("summary present", bool(result.get("summary")))
        ok("work_experience entries", len(result.get("work_experience", [])))
        ok("technical skills", result.get("skills", {}).get("technical", []))
        ok("education entries", len(result.get("education", [])))
        print("\n  Full output:")
        print(textwrap.indent(json.dumps(result, indent=2), "    "))
        return True
    except BaseException as exc:
        fail("profile extraction", exc)
        return False


def test_job() -> bool:
    header("Task: job extraction (ExtractedJob)")
    try:
        from app.services.job_extractor import extract_job
        result = extract_job(SAMPLE_JOB)
        ok("Parsed successfully")
        ok("company", result.get("company"))
        ok("title", result.get("title"))
        ok("required qualifications", len(result.get("requirements", {}).get("required", [])))
        ok("preferred qualifications", len(result.get("requirements", {}).get("preferred", [])))
        ok("technical skills", result.get("skills", {}).get("technical", []))
        print("\n  Full output:")
        print(textwrap.indent(json.dumps(result, indent=2), "    "))
        return True
    except BaseException as exc:
        fail("job extraction", exc)
        return False


def test_tailoring() -> bool:
    header("Task: tailoring generation (Markdown)")
    try:
        from app.services.tailoring_generator import generate_tailoring

        # Build a minimal profile in the expected sourced format
        profile = {
            "resume": {
                "summary": "Platform engineer with 7 years experience.",
                "work_experience": [
                    {
                        "title": "Senior Software Engineer",
                        "company": "Acme Corp",
                        "duration": "06/2021 – Present",
                        "bullets": [
                            "Led migration to microservices, reducing latency 40%.",
                            "Designed internal developer platform for 120+ engineers.",
                        ],
                    }
                ],
                "skills": {"technical": ["Python", "Kubernetes", "Terraform", "AWS"], "soft": []},
                "education": [{"degree": "B.S. Computer Science", "institution": "UT Austin", "year": "2018"}],
                "projects": [],
                "certifications": ["AWS Certified Solutions Architect"],
            }
        }
        job = {
            "company": "Initech",
            "title": "Staff Software Engineer – Platform",
            "responsibilities": ["Build internal tooling", "Define engineering best practices"],
            "requirements": {
                "required": ["7+ years experience", "Distributed systems background"],
                "preferred": ["Kubernetes experience", "Staff/principal engineer background"],
            },
            "skills": {"technical": ["Python", "Go", "TypeScript", "Kubernetes", "AWS"], "soft": []},
        }

        result = generate_tailoring(profile, job, candidate_name="Jane Smith")
        ok("Generated successfully")
        ok("Output length (chars)", len(result))
        ok("Contains candidate name", "Jane Smith" in result)
        ok("Contains company name", "Initech" in result)
        print("\n  Output preview (first 800 chars):")
        print(textwrap.indent(result[:800] + ("..." if len(result) > 800 else ""), "    "))
        return True
    except BaseException as exc:
        fail("tailoring generation", exc)
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

TASKS = {
    "profile": test_profile,
    "job": test_job,
    "tailoring": test_tailoring,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Test LLM tasks against the configured endpoint.")
    parser.add_argument(
        "--task",
        choices=[*TASKS.keys(), "all"],
        default="all",
        help="Which task to run (default: all)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Request timeout in seconds. Overrides LLM_TIMEOUT_SECONDS (default: 120).",
    )
    args = parser.parse_args()

    # Apply timeout override before any app imports instantiate the client
    if args.timeout is not None:
        import app.clients.llm_client as llm_client_module
        llm_client_module.LLM_TIMEOUT_SECONDS = args.timeout

    # Print endpoint info before running
    from app.config import settings
    from app.core.model_config import get_json_mode
    from app.clients.llm_client import LLM_TIMEOUT_SECONDS

    print("\nEndpoint configuration:")
    print(f"  model    : {settings.llm_model}")
    print(f"  base_url : {settings.llm_base_url or '(OpenAI default)'}")
    print(f"  json_mode: {get_json_mode(settings.llm_model).value}")
    print(f"  timeout  : {LLM_TIMEOUT_SECONDS}s")

    tasks_to_run = list(TASKS.items()) if args.task == "all" else [(args.task, TASKS[args.task])]

    results: dict[str, bool] = {}
    for name, fn in tasks_to_run:
        results[name] = fn()

    # Summary
    header("Results")
    all_passed = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        if not passed:
            all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
