"""
LLM task catalog.

Every LLM call site in the app declares which TaskName it serves. The model used
for a task is resolved through the registry (see app/clients/llm_registry.py), so a
task can be pointed at a different model without touching call-site code.

TaskKind groups tasks by what kind of model suits them:
  - GENERATIVE: free text or structured extraction produced token by token
  - SYSTEM_ONE: classification/scoring — the output is a choice among known options
                (suited to System One models, which return calibrated probabilities)

Each kind has its own default model in the registry, so switching every
classification task to a different model is a one-line change.
"""

from enum import StrEnum


class TaskKind(StrEnum):
    GENERATIVE = "generative"
    SYSTEM_ONE = "system_one"


class TaskName(StrEnum):
    PROFILE_EXTRACTION = "profile_extraction"
    PROFILE_IDENTITY = "profile_identity"
    JOB_EXTRACTION = "job_extraction"
    JOB_BOUNDS = "job_bounds"
    CHUNK_MATCHING = "chunk_matching"
    GAP_ANALYSIS = "gap_analysis"
    LETTER_GENERATION = "letter_generation"
    GITHUB_ENRICHMENT = "github_enrichment"
    GITHUB_PR_EXTRACTION = "github_pr_extraction"
    RESUME_POLISH = "resume_polish"
    USER_INPUT_PARSE = "user_input_parse"


# Every current call site produces generated or extracted structured output, so all
# tasks are GENERATIVE today. SYSTEM_ONE tasks are added as calls are split into
# classification (e.g. chunk semantic-type classification).
TASK_KINDS: dict[TaskName, TaskKind] = {task: TaskKind.GENERATIVE for task in TaskName}


def task_kind(task: TaskName) -> TaskKind:
    return TASK_KINDS[task]
