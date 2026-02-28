# Technical Debt & Polish Notes

*Things to address alongside the sprint — or before shipping publicly*

---

## High Priority (Fix Before Public Launch)

### LLM Pipeline Robustness

The current approach is functional but needs defensive hardening before real users stress it:

- **Token limits:** No `max_tokens` is set on any LLM call. A very long resume or a deeply verbose job posting could exceed the model's context window and fail silently or truncate. Add `max_tokens=4000` as a sensible ceiling on extraction calls, `max_tokens=2000` on tailoring generation.

- **Timeout on Playwright:** `get_rendered_content()` has no timeout. If Playwright hangs on a JavaScript-heavy page or a slow server, the entire `/tailorings` request hangs indefinitely. Add `page.set_default_timeout(30000)` (30 seconds) and catch `TimeoutError`.

- **JSON validation after extraction:** `_strip_json_fences()` strips fences but doesn't validate that the result is actually the right schema before returning. Add a lightweight check after `json.loads`: confirm the expected keys exist (`title`, `company`, `responsibilities`, etc.) and default missing ones to null/empty rather than failing.

- **The `job_cache` on `app.state`:** This was initialized but never used. Remove it — dead state is confusing.

### Backend Endpoint Cleanup

Three endpoints exist that aren't wired to anything in the current frontend:

- `/parse` — legacy scrape+parse endpoint. Remove.
- `/generate` — generates a one-paragraph match text. Not used. Remove.
- `/job` — scrapes + extracts a job standalone. Duplicated by `tailorings.py`. Remove.

Keeping dead endpoints is a maintenance burden and creates confusion when reading the codebase.

### Database Migrations

There's no mention of Alembic migration files in the repo. If the schema is evolving (and it will be during this sprint — adding `is_public`, `public_slug`, `notion_access_token`, `username_slug`, `additional_context`), migrations need to exist. Without them, schema changes require manual `CREATE TABLE` or `ALTER TABLE` in production, which is error-prone.

Set up Alembic properly if it isn't already:
```bash
cd backend && uv run alembic init alembic
```

Each column addition in this sprint should be its own migration file.

### CORS Configuration

The FastAPI app doesn't have explicit CORS headers configured. For now the frontend and backend are on the same origin in production, but:
- Local development has frontend on `:3000` and backend on `:8000` — CORS is needed for this to work without a proxy
- Any future direct API consumer (browser extension, third-party integration) will need CORS headers

Add `CORSMiddleware` in `main.py` with origins restricted to your actual domains.

---

## Medium Priority (Before Significant User Traffic)

### Structured Logging

The backend mixes `print()` (the triple-print in `mvp_llm.py` was just removed) with `logger.debug()` and `logger.exception()`. For production visibility, standardize on:

- `logger.info()` for all request-level events
- `logger.warning()` for recoverable failures (Playwright timeout, LLM JSON parse retry)
- `logger.exception()` for unhandled errors

Remove any remaining `print()` calls. CloudWatch picks up stdout in ECS, but structured log levels make filtering much easier.

### Rate Limiting

Currently nothing stops a single user from triggering 50 tailoring generations in a row, each with a Playwright scrape and two LLM calls. This is both expensive and a denial-of-service vector. Add a simple per-user rate limit:

- Max 10 tailoring generations per hour per user
- Return HTTP 429 with a clear message and retry-after header

FastAPI's `slowapi` package is the standard approach. Or implement manually with a Redis counter if you add Redis for other reasons.

### Resume Processing Memory

`resume_processor.py` downloads the entire resume into memory (`file_bytes`). For large PDFs this is fine (resumes are rarely > 5MB), but it's worth noting. If you ever accept other file types (e.g., video portfolios, large portfolios), this pattern won't scale.

### S3 Key Collision

The S3 key uses `uuid4()` for uniqueness — this is fine, but when a user re-uploads a resume, the old S3 key is deleted and a new one is created. Confirm that the delete actually runs before the new presigned URL is issued, and that there's no window where both exist.

---

## Low Priority (Nice to Have)

### Frontend Type Safety on API Responses

Several API route handlers cast responses to `any` or leave them untyped. Adding Zod validation on the frontend API responses would catch backend schema changes earlier — but this is polish work that adds lines without adding features.

### Accessibility Audit

- Missing `aria-label` on icon-only buttons (the copy button, the delete button)
- Missing `role="alert"` on error states
- Keyboard navigation through the sidebar tailoring list could be improved

These matter for real users and are fast to fix, but they're not blocking.

### Mobile Layout

The dashboard layout (sidebar + main content) collapses responsively, but the tailoring detail view on mobile is dense. The header with three buttons (View Posting, Copy, Regenerate, Export to Notion) will need a dropdown or a different layout at small sizes.

### Test Coverage

There are no tests in the repository. For a portfolio project this is acceptable, but for the LLM extraction pipeline specifically, a small suite of fixture-based tests (given this HTML input, expect these extracted fields) would:
1. Catch regressions when prompts change
2. Demonstrate testing discipline to interviewers

Even 5–10 tests in `backend/tests/` using pytest with fixture HTML files would be meaningful. Consider adding one test file for `extract_job()` with 2–3 real job posting examples.

---

## The Three Prints

The three `print(job_posting_markdown)` calls in `extract_job()` were removed, but double-check there are no other debug artifacts scattered through the codebase before public launch:

```bash
grep -rn "print(" backend/app/
```

Any remaining `print()` should be converted to `logger.debug()` or removed.
