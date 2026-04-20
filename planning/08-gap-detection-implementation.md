# Day 8 — Gap Detection: Implementation Plan

*Sprint: 2026-04-10–19 | Status: planning*

---

## What we're building

After a tailoring generates, run a background LLM pass that identifies job requirements the candidate's profile doesn't fully address. Surface those as targeted follow-up questions in the UI. When the user answers, append the answer to their `user_input_text` and re-score **only the affected `JobChunk`** — not the whole tailoring. The regenerate button still exists for that.

---

## Data flow

```
_finalize_tailoring completes
        ↓
run_gap_analysis(tailoring_id) [background thread]
  → reads: tailoring.job.extracted_job, tailoring.job.chunks, experience.extracted_profile
  → LLM call → ProfileGap[] (each gap names a job_requirement string)
  → lookup: for each gap, find JobChunk.id where content matches job_requirement text
  → writes: tailoring.gap_analysis = GapAnalysis JSON
        ↓
Frontend polls GET /tailorings/{id} → sees gap_analysis in response
        ↓
User fills in answer → POST /api/tailorings/{id}/gap-answer {gap_index, answer}
        ↓
Backend:
  1. Append answer to experience.user_input_text
  2. Re-score ONE chunk: enrich_single_chunk(chunk_id, updated_profile)
  3. Return updated chunk score
```

---

## Step-by-step implementation

### 1. Pydantic schemas — `backend/app/schemas/gaps.py` (new file)

```python
class ProfileGap(BaseModel):
    job_requirement: str          # verbatim requirement text from extracted_job
    question_for_candidate: str   # specific, role-contextualised question
    context: str                  # one sentence: why this matters for THIS role
    source_searched: str          # which profile sources were checked (resume, github, user_input)
    chunk_id: str | None = None   # UUID of the matching JobChunk — populated post-LLM by service layer

class GapAnalysis(BaseModel):
    gaps: list[ProfileGap]
    sourced_claim_count: int      # requirements that ARE evidenced
    unsourced_claim_count: int    # requirements that produced a gap
```

`chunk_id` is nullable in the schema because the LLM doesn't produce it — the service layer resolves it against the DB after the LLM call.

---

### 2. Prompt — `backend/app/prompts/gap_analysis.py` (new file)

```python
TEMPERATURE = 0.3

SYSTEM = """
You are a career coach reviewing a job description against a candidate's profile.

Your task: identify job requirements that are NOT evidenced or only weakly evidenced in the
candidate's profile. For each gap, write a specific follow-up question that would surface
concrete evidence if the candidate has relevant experience.

Rules:
- Only surface genuine gaps — where the profile lacks credible evidence.
- Questions must be specific to this role, not generic ("Tell me about a time you led a team").
  Bad: "Do you have experience with performance optimisation?"
  Good: "The role requires sub-100ms API latency at 10k RPS — do you have a concrete example
        of profiling and optimising a high-throughput service?"
- context must explain WHY this requirement matters for THIS specific role/company.
- source_searched should list the profile sections you checked (e.g. "resume work_experience, github").
- Do NOT include requirements that are already well-evidenced — only gaps.
"""

USER_TEMPLATE = """
## Candidate profile
{formatted_profile}

## Job requirements
{requirements_block}

Identify requirements that are gaps. Return a GapAnalysis object.
"""
```

---

### 3. Gap analysis service — `backend/app/services/gap_analyzer.py` (new file)

Key responsibilities:
1. Build inputs from DB (profile, extracted_job requirements, existing chunks)
2. LLM call → `GapAnalysis` (without `chunk_id`s yet)
3. For each gap, find the best-matching `JobChunk` by comparing `gap.job_requirement` against `chunk.content` — use `difflib.SequenceMatcher` or substring search; exact/near-exact match is expected because `extracted_job.requirements` items were themselves derived from job text
4. Annotate each `ProfileGap.chunk_id`
5. Write `tailoring.gap_analysis` as JSON

```python
def run_gap_analysis(tailoring_id: str) -> None:
    """Background task: run after _finalize_tailoring. Creates its own DB session."""
    from app.clients.database import SessionLocal
    ...
```

Chunk ID resolution: iterate over `gap.job_requirement`, compare against all `job.chunks` where `chunk_type != "header"`. Take the chunk with the highest `SequenceMatcher.ratio()` above a threshold (0.6). If no match found, leave `chunk_id = None` — the gap still surfaces in the UI but can't trigger targeted re-enrichment (user sees a prompt to use the regenerate button instead).

---

### 4. DB — `gap_analysis` column on `Tailoring`

Add to `backend/app/models/database.py`:
```python
gap_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

New Alembic migration (next in sequence after the profile snapshot migration).

---

### 5. Wire gap analysis into `_finalize_tailoring`

In `backend/app/api/tailorings.py`, after the `enrich_job_chunks` call at the bottom of `_finalize_tailoring`:

```python
# Gap analysis runs after chunk enrichment (needs chunk IDs for resolution)
try:
    run_gap_analysis(tailoring_id)
except Exception:
    logger.exception("Gap analysis failed for tailoring %s — non-fatal", tailoring_id)
```

Gap analysis failure must never fail the tailoring. Run it after `enrich_job_chunks` so chunks are already in the DB when we do chunk ID resolution.

---

### 6. `GET /tailorings/{id}` — include `gap_analysis`

Add to the return dict in `get_tailoring`:
```python
"gap_analysis": tailoring.gap_analysis,
```

No schema change needed — it's already JSON stored as a dict.

---

### 7. Single-chunk re-enrichment — `backend/app/services/chunk_matcher.py`

Add a new function (do not touch `enrich_job_chunks`):

```python
def re_enrich_single_chunk(chunk_id: str, extracted_profile: dict, pronouns: str | None = None) -> None:
    """
    Re-score one JobChunk against an updated profile.
    Used when a gap answer is submitted — avoids re-processing the entire job.
    Creates its own DB session.
    """
    from app.clients.database import SessionLocal
    ...
    # 1. Load the chunk
    # 2. Build a single-item batch: [ChunkInput(content=chunk.content, section=chunk.section, chunk_type=chunk.chunk_type, position=chunk.position)]
    # 3. Run the chunk matching LLM for just this one chunk (same prompt/model as enrich_job_chunks)
    # 4. Update chunk.match_score, chunk.match_rationale, chunk.advocacy_blurb, chunk.enriched_at
    # 5. Commit and close
```

This re-uses `ChunkMatchBatch` / the existing chunk matching prompt — just with a list of one.

---

### 8. Gap answer endpoint — `backend/app/api/tailorings.py`

```python
class GapAnswerRequest(BaseModel):
    gap_index: int
    answer: str

@router.post("/tailorings/{tailoring_id}/gap-answer")
def submit_gap_answer(
    tailoring_id: str,
    body: GapAnswerRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
```

Logic:
1. Load tailoring — 404 if not found or wrong user
2. Validate `gap_index` is in bounds against `tailoring.gap_analysis["gaps"]`
3. Get `chunk_id` from the gap at that index (may be None)
4. Load `experience` for user — 404 if not found
5. Append answer to `experience.user_input_text` (newline-separated, prefixed with a marker like `[Gap answer — {gap.job_requirement[:60]}]: `)
6. Commit
7. If `chunk_id` is not None: `background_tasks.add_task(re_enrich_single_chunk, chunk_id, experience.extracted_profile, user.pronouns)`
8. Return `{"status": "saved", "chunk_reenrichment_queued": chunk_id is not None}`

Answer format in `user_input_text`:
```
[Gap answer — Senior backend engineering at scale]: I optimised a payment processing service
from 800ms p99 to 45ms by profiling with py-spy and switching to async batch inserts...
```
This is human-readable, persists across sessions, and feeds naturally into the profile formatter.

---

### 9. Frontend API route — `frontend/src/app/api/tailorings/[id]/gap-answer/route.ts` (new file)

Thin proxy via `proxyToBackendWithUser`. POST only.

```typescript
import { proxyToBackendWithUser } from "@/lib/proxy";

export async function POST(
  req: Request,
  { params }: { params: { id: string } }
) {
  return proxyToBackendWithUser(req, `/tailorings/${params.id}/gap-answer`);
}
```

---

### 10. TypeScript types — `frontend/src/types/index.ts`

```typescript
export interface ProfileGap {
  job_requirement: string;
  question_for_candidate: string;
  context: string;
  source_searched: string;
  chunk_id: string | null;
}

export interface GapAnalysis {
  gaps: ProfileGap[];
  sourced_claim_count: number;
  unsourced_claim_count: number;
}
```

Add to the `Tailoring` interface:
```typescript
gap_analysis?: GapAnalysis | null;
```

---

### 11. `GapQuestions.tsx` — `frontend/src/components/dashboard/GapQuestions.tsx` (new file)

Props: `tailoringId: string`, `gaps: ProfileGap[]`

State per gap: `answers: Record<number, string>`, `saving: Record<number, boolean>`, `saved: Record<number, boolean>`

Layout per gap card:
```
┌─────────────────────────────────────────────┐
│ [job_requirement]                 (heading)  │
│ [question_for_candidate]          (prompt)   │
│ [context]                         (muted)    │
│                                              │
│ ┌──────────────────────────────────────────┐ │
│ │ textarea (4 rows)                        │ │
│ └──────────────────────────────────────────┘ │
│                              [Save answer →] │
│  ✓ Saved — experience updated. View →        │  ← shown post-save
└─────────────────────────────────────────────┘
```

On save:
```typescript
await fetch(`/api/tailorings/${tailoringId}/gap-answer`, {
  method: "POST",
  body: JSON.stringify({ gap_index: i, answer }),
});
```
Show inline confirmation. Link "View →" goes to `/dashboard/experience`.

No re-fetch of the tailoring needed — the chunk re-enrichment is fire-and-forget. If the user wants to see the updated chunk scores, they refresh; if they want updated tailoring prose, they use the regenerate button.

---

### 12. `TailoringDetail.tsx` — wire in the section

In the Analysis tab, after `<FitAnalysis ... />`:

```tsx
{tailoring.gap_analysis && tailoring.gap_analysis.gaps.length > 0 && (
  <details open={false}>
    <summary className="...">
      Strengthen your profile ({tailoring.gap_analysis.gaps.length} gaps found)
    </summary>
    <GapQuestions
      tailoringId={tailoring.id}
      gaps={tailoring.gap_analysis.gaps}
    />
  </details>
)}
```

Use a native `<details>` / `<summary>` for the collapsible — no JS needed, consistent with the existing accordion patterns.

---

## Order of implementation

1. Schemas (`gaps.py`)
2. Prompt (`gap_analysis.py`)
3. DB column + migration
4. `gap_analyzer.py` service
5. Wire into `_finalize_tailoring`
6. `re_enrich_single_chunk` in `chunk_matcher.py`
7. `POST /tailorings/{id}/gap-answer` endpoint
8. `GET /tailorings/{id}` — add `gap_analysis` field
9. Frontend: types → API route → `GapQuestions.tsx` → `TailoringDetail.tsx`

---

## What's explicitly out of scope

| Item | Why |
|------|-----|
| Re-generating tailoring prose on answer | User's choice — regenerate button exists |
| Rate-limiting gap-answer endpoint | It's a cheap write + one small LLM call (one chunk); the tailoring hourly limit already protects the expensive paths |
| Showing updated chunk score in the UI immediately after answer | Fire-and-forget background task; polling is unnecessary complexity at this stage |
| Gap analysis for regenerated tailorings | Gaps are re-run in `_finalize_tailoring` which runs on both create and regen — already covered |
| Deleting answered gaps from the list | Answered gaps stay visible; the "Saved" confirmation communicates success |
