# Day 19 — Three Improvements

**Branch:** `dunbarchara/ycdemo`
**Theme:** Live dashboard empty-experience state, parallel chunk scoring, YOE gap prompt fix.

---

## Item 1 — Empty experience state on live dashboard Home

Show the "Head to My Experience" subtitle on the live dashboard when no experience is connected,
instead of always showing "Welcome back to Tailord".

- [x] `frontend/src/lib/tailorings.ts` — added `fetchExperience(userId, userEmail, userName)` → `ExperienceRecord | null`; same header pattern as `fetchTailorings`; returns `null` on error/non-OK
- [x] `frontend/src/app/(dashboard)/dashboard/page.tsx` — added `fetchExperience` to `Promise.all`; computes `hasExperience` from `extracted_profile.resume || extracted_profile.github || github_username`; passes `hasExperience` to `<DashboardHome>`
- [x] `frontend/src/components/dashboard/DashboardHome.tsx` — added `hasExperience?: boolean` prop (defaults `true` so demo page unaffected); subtitle condition changed to `(readOnly || !hasExperience)` — live users with experience still see "Welcome back to Tailord"; `New Tailoring` button disable logic unchanged (still gated on `readOnly` only)

---

## Item 2 — Parallel requirement scoring

Both the vector and LLM batch paths in `chunk_matcher.py` were sequential. Parallelised using
`ThreadPoolExecutor` (sync-safe — `_finalize_tailoring` is a sync BackgroundTask, not async).

- [x] `backend/app/config.py` — added `chunk_scorer_concurrency: int = 8` (reads `CHUNK_SCORER_CONCURRENCY` env var)
- [x] `backend/app/services/chunk_matcher.py` — imported `ThreadPoolExecutor`, `as_completed`; **vector mode**: replaced sequential `for chunk in scoreable` loop with `ThreadPoolExecutor` + `as_completed`; `batch_count` set upfront to `len(scoreable)`; per-chunk error handling preserved; **LLM mode**: pre-collected all `(section, batch_start, batch, preceding)` units into `batch_units` list, then dispatched all via `ThreadPoolExecutor`; inner `_run_llm_batch` closure returns `(batch, results)`; `batch_count += len(batch_units)`; error handling and padding preserved
- [~] `anyio.to_thread.run_sync` / `asyncio.gather` approach from plan — not used; `_finalize_tailoring` is a sync function so `anyio` would require making `enrich_job_chunks` async and the caller async too; `ThreadPoolExecutor` achieves the same parallelism without changing any async boundaries

---

## Item 3 — YOE gap detection prompt fix

Score 0 (not 1) when candidate total YOE falls below a numeric year threshold.

- [x] `backend/app/prompts/chunk_matching.py` — CRITICAL RULE 3 expanded from one-liner to explicit decision tree: YOE ≥ threshold → score 2; YOE < threshold → score 0, never score 1; added rationale ("the skill evidence is irrelevant once the numeric bar is not cleared")
- [x] `backend/app/prompts/chunk_matching.py` — added EXAMPLE 5: 5.0-year profile vs "10+ years shipping production software" → score 0; correct output shows null advocacy_blurb and gap rationale citing pre-computed total
