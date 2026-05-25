# Day 18 — Path to Strong: enrichment questions for partial matches

## Status: complete

Gap analysis previously only generated follow-up questions for `match_score == 0` (gap) chunks.
Partial matches (`match_score == 1`) received no guided enrichment path. This sprint adds the
"Path to Strong" enrichment loop — same pipeline and data structures as the gap loop, with
different prompt framing and a dedicated `partial_response` source type.

---

## Design decisions

- **Separate `partial_response` source_type** — clean provenance, different semantics from `gap_response`
- **No cap on partial questions** — users only see questions on click, volume is not a UX problem
- **Same `run_gap_analysis` pipeline** — gaps loop first, then partials loop, single DB commit at end
- **Gap → partial inline transition** — when a `gap_response` re-scores a chunk to partial (score=1),
  the backend generates the partial question on the spot and returns it in the response; the UI
  renders it immediately without a reload
- **Prompt framing differs** — gap = "do you have any evidence?"; partial = "you have some — what specific
  example takes this to fully met?"

---

## Changes

- [x] `backend/app/prompts/gap_analysis.py` — Added `PARTIAL_SYSTEM` and `PARTIAL_USER_TEMPLATE`
- [x] `backend/app/schemas/gaps.py` — Added `partials: list[ProfileGapWithChunk] = []` to `GapAnalysis`
- [x] `backend/app/services/gap_analyzer.py` — Added `_generate_partial_question`; partial chunk loop in `run_gap_analysis`; updated log + `GapAnalysis` construction
- [x] `backend/app/api/experience.py` — Added `response_type` to `GapResponseRequest`; source_type logic for `partial_response`; upsert now searches all response source types; on-demand partial question generation when re-score lands at 1; `partial_question`/`partial_context` in response; `partial_response` bucket in `_group_experience_chunks`
- [x] `backend/app/models/database.py` — Updated `ExperienceChunk` source_type docstring with `partial_response` lifecycle
- [x] `frontend/src/types/index.ts` — Added `partials` to `GapAnalysis`; `partial_response` to source_type union; `partial_response` to `ExperienceChunksResponse`
- [x] `frontend/src/components/dashboard/AnalysisView.tsx` — `GapAnswerForm` accepts `responseType` prop; `onSuccess` extended with `partialQuestion`/`partialContext`; `ChunkContextPanel` renders "Path to Strong" section for `variant === 'partial'`; `AnalysisView` gains `partialResponses` prop, `inlinePartialQuestions` state, `partialByChunkId`/`partialAnsweredByChunkId` maps, and merges inline + pre-generated partial questions
- [x] `frontend/src/components/dashboard/TailoringDetail.tsx` — Fetches `partial_response` alongside `gap_response` from `/api/experience/chunks`; passes `partialResponses` to `AnalysisView`
- [x] `frontend/src/components/dashboard/ChunkedProfile.tsx` — Added "Path to Strong" section rendering `partial_response` chunks; `patchChunkInResponse` and `removeChunkFromResponse` handle `partial_response`

## What did NOT change

- `ProfileGapWithChunk` schema — reused as-is for both gaps and partials
- `gap_response` source_type and its lifecycle — unchanged
- `GapAnswerForm` component — reused with different labels/response_type
- Gap enrichment section for score=0 chunks — unchanged
- `unsourced_claim_count` — still counts only gap (score=0) chunks
- DB migration — not needed (`source_type` is a free `String(30)` column)
