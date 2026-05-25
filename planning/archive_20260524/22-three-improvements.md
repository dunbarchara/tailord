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

---

## Item 4 — GitHub experience claims

Extended GitHub enrichment to extract concrete, resume-style work bullets from repo READMEs and manifests — no new API calls, same LLM pass.

- [x] `backend/app/schemas/llm_outputs.py` — added `experience_claims: list[str]` field to `GitHubRepoEnrichment` (default `[]`; 0–3 past-tense bullets grounded in README/manifest content)
- [x] `backend/app/prompts/github_enrichment.py` — added `experience_claims` rules block to SYSTEM prompt (past-tense verb requirement, ≤20 words, must add signal beyond `detected_stack`, return `[]` if not enough concrete detail, bad/good examples); added field to USER_TEMPLATE JSON schema
- [x] `backend/app/services/github_enricher.py` — added `"experience_claims": llm_result.experience_claims` to the `enriched.append(...)` dict; was missing, causing claims to be silently dropped before reaching the chunker
- [x] `backend/app/services/experience_chunker.py` — in `_github_repo_chunks()`, added loop after `detected_stack` that emits `claim_type="work_experience"` chunks for each claim, grouped under `group_key=repo_name`
- [x] `backend/app/services/tailoring_generator.py` — in `_fmt_github_prose()`, renders each claim as a bullet after `Stack:` in the enriched repo block so claims appear in the LLM profile context
