# Backend Refactoring Candidates

> Status: review-pending — no changes made yet. This document records findings from a
> full pass through the backend (May 2026). Each item is a candidate for future work,
> not a committed plan.

---

## 1. `chunk_matcher.py` — Duplicated scoring loops (HIGH IMPACT)

**Files:** `backend/app/services/chunk_matcher.py`

`enrich_job_chunks` and `refresh_job_chunks` are two public background-task functions
that each contain the full LLM scoring path AND the full vector scoring path. The two
implementations are nearly line-for-line identical (~180 lines duplicated):

**LLM path (both functions):**
- Build `section_map` from scoreable chunks
- Build `batch_units` (section, batch_start, batch, preceding_paragraph)
- Define `_run_llm_batch` inner closure (identical validation logic, identical LLM call)
- Submit all units to `ThreadPoolExecutor`
- Handle `done` / `not_done` from `wait()` with identical timeout/error logic

**Vector path (both functions):**
- Build `candidate_header`
- Define `_score_one_vector` inner closure
- Submit to `ThreadPoolExecutor`
- Handle `done` / `not_done` with identical timeout/error logic

**Differences between the two functions:**
- `enrich_job_chunks` deletes existing chunks first, creates new `JobChunk` rows
- `refresh_job_chunks` updates existing chunks in-place, scoped to `is_requirement=True`

**Suggested refactor:** Extract the scoring dispatch into a shared helper:
```python
def _run_scoring_pass(
    chunks, extracted_profile, pronouns, experience_id, candidate_name, job_id
) -> dict[..., ChunkMatchResult]:
    ...
```
Both public functions call `_run_scoring_pass` and then do their own persistence.
The `_validate_batch` inner function is also identical between them and should be
a module-level private helper.

---

## 2. `_format_sourced_profile` lives in the wrong module (MEDIUM IMPACT)

**Files:** `tailoring_generator.py`, `requirement_matcher.py`, `chunk_matcher.py`, `gap_analyzer.py`

`_format_sourced_profile` is defined in `tailoring_generator.py` with a leading underscore
indicating it's private to that module. It's imported by three other service modules:

```python
# In requirement_matcher.py, chunk_matcher.py, gap_analyzer.py:
from app.services.tailoring_generator import _format_sourced_profile
```

Same situation for `_build_ranked_matches_from_chunks`, imported into `tailorings.py`.

**Suggested refactor:** Move `_format_sourced_profile` (and `_compute_profile_signals`,
`_fmt_resume_prose`, `_fmt_github_prose`) into a new `services/profile_formatter.py`
module (or `core/profile_formatter.py`). Remove the leading underscore. This cleans up
the module boundary and makes the dependency explicit.

---

## 3. `_generate_gap_question` / `_generate_partial_question` near-identical (LOW-MEDIUM)

**File:** `backend/app/services/gap_analyzer.py`

Both functions have the same signature and identical structure — the only difference
is which prompt template they use (`SYSTEM`/`USER_TEMPLATE` vs `PARTIAL_SYSTEM`/`PARTIAL_USER_TEMPLATE`).

**Suggested refactor:**
```python
def _generate_question(
    mode: Literal["gap", "partial"], requirement, match_rationale, ...
) -> GapQuestion:
    sys_prompt = prompt.SYSTEM if mode == "gap" else prompt.PARTIAL_SYSTEM
    user_template = prompt.USER_TEMPLATE if mode == "gap" else prompt.PARTIAL_USER_TEMPLATE
    ...
```

---

## 4. Candidate name resolution repeated across background tasks (LOW)

**Files:** `tailorings.py` (`_finalize_tailoring`), `gap_analyzer.py` (`run_gap_analysis`)

Both resolve the display name the same way:
```python
preferred = " ".join(filter(None, [user.preferred_first_name, user.preferred_last_name])).strip()
candidate_name = preferred or user.name or user.email
```

This logic also lives in `users.py` as `_display_name()`. The function should be a
shared utility — either a method on the `User` model or a helper in `core/deps_user.py`
or a new `core/user_utils.py`.

---

## 5. `_use_managed_identity()` duplicated with subtle inconsistency (LOW)

**Files:** `clients/llm_client.py`, `clients/embedding_client.py`

Both define:
```python
def _use_managed_identity() -> bool:
    return settings.environment in ("staging", "production") and not settings.llm_api_key
```

The embedding client's version checks `settings.llm_api_key` (not `settings.embedding_api_key`).
This is intentional (see updated comment in `embedding_client.py`) but fragile — if the
behavior needs to diverge, the duplication makes it easy to miss.

**Suggested refactor:** Move to a shared helper:
```python
# In config.py or a new core/env_utils.py
def use_managed_identity() -> bool:
    return settings.environment in ("staging", "production") and not settings.llm_api_key
```

---

## 6. `clients/database.py` — `echo=True` in all environments (LOW)

**File:** `backend/app/clients/database.py`

```python
engine = create_engine(DATABASE_URL, echo=True)
```

`echo=True` logs every SQL statement at INFO level. In staging/production this is
extremely noisy and may surface PII embedded in query parameters in log storage.

**Suggested fix:**
```python
engine = create_engine(DATABASE_URL, echo=settings.environment == "local")
```

A comment has been added flagging this. The change itself is safe but should be
tested to confirm nothing downstream depends on the SQL log output.

---

## 7. `models/mvp_schemas.py` — name doesn't match content (LOW)

**File:** `backend/app/models/mvp_schemas.py`

The file is named `mvp_schemas.py` (a dated artifact from the MVP phase) but contains:
1. SSRF protection logic (`_validate_job_url`, IP/network blocking constants)
2. Pydantic request/response models (`TailoringCreate`, `TailoringResponse`, etc.)

The SSRF logic (`_validate_job_url`) is imported and called directly from `tailorings.py`.
The name makes this hard to discover.

**Suggested refactor:**
- Rename the file to `schemas/tailoring_requests.py` (or just move models to `schemas/`)
- Move SSRF logic to `core/ssrf.py` or `core/url_validation.py`
- Update all imports

---

## 8. `Experience.s3_key` field name is provider-specific (LOW)

**File:** `backend/app/models/database.py`, multiple callers

The `Experience.s3_key` column is used by `AzureStorageClient` and referenced throughout
the codebase. CLAUDE.md explicitly says to use neutral naming (`storage_key` not `s3_key`).

This requires an Alembic migration to rename the column and a find-replace across all
callers. Low urgency since it's behind the abstraction layer, but worth tracking.

---

## 9. Mixing `structlog` and `logging.getLogger` (COSMETIC)

Most observability-era files (added with the observability sprint) use:
```python
logger = structlog.get_logger(__name__)
```

Older service/client files use:
```python
logger = logging.getLogger(__name__)
```

**Functional impact:** None. The stdlib loggers are routed through `ProcessorFormatter`
in `logging.py`, so they also get `correlation_id` via `merge_contextvars`. The format
is the same in production (JSON).

**Style impact:** stdlib loggers use `%s` percent-formatting while structlog native
loggers use key=value kwargs. The stdlib pattern is slightly less machine-queryable
in Log Analytics but still works.

**Files still using stdlib logging:** `requirement_matcher.py`, `experience_processor.py`,
`github_enricher.py`, `experience_chunker.py`, `experience_embedder.py`, `gap_analyzer.py`,
`job_extractor.py`, `notion_export.py`, `storage_azure.py`, `storage_aws.py`,
`llm_client.py`, `embedding_client.py`, `github_client.py`.

Low-priority; migrate incrementally when touching these files.

---

## 10. `tailoring_generator.py` has no logger (COSMETIC)

**File:** `backend/app/services/tailoring_generator.py`

The module does significant work (profile formatting, date arithmetic, rendering) but
has no logger. LLM calls are logged by `llm_utils.py`, but formatting decisions,
validation failures, and render branches are invisible. Add a logger when next editing
this file.

---

## Summary by priority

| # | Item | Effort | Impact |
|---|------|--------|--------|
| 1 | chunk_matcher.py scoring loop duplication | Large | High |
| 2 | `_format_sourced_profile` in wrong module | Medium | Medium |
| 3 | `_generate_gap/partial_question` duplication | Small | Low-Medium |
| 4 | Candidate name resolution repeated | Small | Low |
| 5 | `_use_managed_identity()` duplication | Small | Low |
| 6 | `echo=True` in all environments | Trivial | Low |
| 7 | `mvp_schemas.py` naming/organization | Medium | Low |
| 8 | `s3_key` → `storage_key` rename | Medium (migration) | Low |
| 9 | Stdlib vs structlog mixing | Large (many files) | Cosmetic |
| 10 | No logger in tailoring_generator | Trivial | Cosmetic |
