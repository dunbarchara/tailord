# Platform Flows

Reference documentation for the core operational flows in Tailord. Each flow covers
all phases, steps, and responsibilities — including concurrency behavior and what is
observable in logs, metrics, and traces.

Tags used in flow diagrams:
- `[SEQ]` — sequential, waits for previous step to complete
- `[PAR]` — parallel, dispatched concurrently via ThreadPoolExecutor
- `[LLM]` — LLM API call
- `[HTTP]` — external HTTP request
- `[DB]` — database read or write

---

## Tailoring Generation

### Overview

Transforms a job URL (or manual description) and a candidate's experience profile into
a structured, role-specific Tailoring document with gap analysis questions.

| | |
|-|-|
| **Entry points** | `POST /tailorings`, `POST /tailorings/{id}/regenerate` |
| **HTTP handler** | `_stream_tailoring` — `backend/app/api/tailorings.py` |
| **Background task** | `_finalize_tailoring` — `backend/app/api/tailorings.py` |
| **Services** | `job_extractor.py`, `chunk_matcher.py`, `tailoring_generator.py`, `gap_analyzer.py` |
| **Typical duration** | 20–35 seconds (letter + gap run concurrently; total ≈ max(letter, gap)) |
| **Phases** | 5 (1 pre-phase in HTTP handler, 4 in background task; letter + gap run in parallel) |

---

### Flow diagram

```
POST /tailorings
│
├── PRE-PHASE  validate_job_posting                                         [SEQ]
│   ├── validate URL format                                                 [SEQ]
│   ├── try ATS direct API (Greenhouse / Lever)                             [SEQ · HTTP]
│   │   └── if matched → return clean markdown, skip Playwright
│   ├── Playwright headless render                                          [SEQ · HTTP]
│   ├── BeautifulSoup markdown extraction                                   [SEQ]
│   ├── truncate to 12,000 tokens                                           [SEQ]
│   ├── validate content looks like a real job posting                      [SEQ]
│   ├── create Job + Tailoring DB records                                   [SEQ · DB]
│   └── schedule background task, emit SSE "ready" → client redirects      [SEQ]
│       └── logged: phase_complete  phase=validate_job_posting  duration_ms=…
│
│   ╌╌╌╌╌ HTTP handler ends. Background task starts. ╌╌╌╌╌
│
├── PHASE 1  extract_job                                                    [SEQ · 1 LLM]
│   ├── deterministic hint extraction from HTML                             [SEQ]
│   │   ├── try JSON-LD structured data → title, company
│   │   └── fallback: meta / title tag parsing
│   ├── LLM call → ExtractedJob                                             [SEQ · LLM]
│   │   └── outputs: title, company, description, responsibilities,
│   │               requirements list
│   └── apply deterministic hints as fallback where LLM returned null       [SEQ]
│       └── logged: phase_complete  phase=extract_job  duration_ms=…
│
├── PHASE 2  enrich_job_chunks                                              [PAR · N LLM]
│   ├── extract_chunks(job_markdown) → typed units                          [SEQ]
│   │   └── chunk_type: header | requirement | paragraph
│   │       logged: chunks_extracted  chunk_count=…  duration_ms=…
│   ├── delete existing JobChunk rows (idempotent)                          [SEQ · DB]
│   │
│   ├── [vector mode]  per-chunk scoring                                    [PAR · N threads]
│   │   └── for each scoreable chunk, concurrently:
│   │       ├── embed_text(chunk) → embedding vector                        [PAR · HTTP]
│   │       ├── cosine similarity query → top-K ExperienceChunks            [PAR · DB]
│   │       ├── build grouped context block from top-K results              [PAR]
│   │       └── LLM call → ChunkMatchBatch (single chunk)                   [PAR · LLM]
│   │           └── outputs: score, advocacy_blurb, should_render,
│   │                        experience_sources
│   │
│   └── [llm mode]  per-batch scoring                                       [PAR · N threads]
│       └── for each batch of 3 chunks per section, concurrently:
│           └── LLM call → ChunkMatchBatch (batch of 3)                     [PAR · LLM]
│               └── outputs: scores, advocacy_blurbs, should_render
│
│       ├── persist JobChunk rows to DB                                      [SEQ · DB]
│       └── embed_job_chunks() — embed remaining unembedded chunks           [SEQ · HTTP]
│           logged: chunks_embeddings_complete  duration_ms=…
│           logged: phase_complete  phase=enrich_job_chunks  duration_ms=…
│
├── PHASE 3  generate_advocacy_letter  ──────────────────────────┐          [PAR · 1 LLM]
│   ├── build_ranked_matches_from_chunks() — internal DB read    │          [SEQ · DB]
│   ├── format_sourced_profile() → structured profile text       │          [SEQ]
│   └── LLM call → TailoringContent                              │          [SEQ · LLM]
│       └── outputs: advocacy letter sections                    │
│       logged: phase_complete  phase=generate_advocacy_letter…  │
│                                                                │
├── PHASE 4  gap_analysis  ──────────────────────────────────────┘          [PAR · N LLM]
│   ├── load scored JobChunks from DB                                        [SEQ · DB]
│   ├── derive gap/partial counts arithmetically (no LLM)                    [SEQ]
│   │   ├── sourced:  score ≥ 1
│   │   ├── gaps:     score = 0, should_render = true
│   │   └── partials: score = 1, should_render = true
│   ├── for each gap chunk, sequentially:
│   │   └── LLM call → GapQuestion (gap-filling question)                    [SEQ · LLM]
│   └── for each partial chunk, sequentially:
│       └── LLM call → GapQuestion (path-to-strong question)                 [SEQ · LLM]
│       logged: phase_complete  phase=gap_analysis  duration_ms=…
│       ✓  tailoring.gap_analysis_status = "complete" — gap questions available
│
└── (after both Phase 3 + Phase 4 complete)
    ├── write letter results to DB                                            [SEQ · DB]
    ├── tailoring.generation_status = "ready"                                 [SEQ · DB]
    └── logged: generation_complete  total_duration_ms=…  phase_durations={…}
```

---

### Phase reference

#### PRE-PHASE — `validate_job_posting`

Runs synchronously in the HTTP handler before the background task is scheduled.
Covered by the `tailoring.phase.validate_job_posting` OTel span, which is a direct
child of FastAPI's auto-instrumented `POST /tailorings` span.

`tailoring_id` is created partway through this phase (after DB records are written)
and is logged on `phase_complete`. `correlation_id` is bound for the entire request
by `CorrelationIdMiddleware` and bridges pre-phase logs to background task logs.

The OTel carrier injection (W3C `traceparent`) happens inside this span, so the
background task's root span is parented to `validate_job_posting` in the trace
waterfall.

For manual tailorings (description provided directly), Playwright is skipped and
`duration_ms` will be under 100ms.

**Failure modes:** Playwright timeout (422), bot-blocked URL (422), content fails
job-posting validation (soft warning, user may retry with `skip_validation=True`).

---

#### PHASE 1 — `extract_job`

Produces the structured job record used by all downstream phases. The deterministic
hint extraction (JSON-LD → meta) runs first to give the LLM high-confidence signals
for title and company without relying on it to parse those from raw text.

`extracted_job` is persisted to the `Job` record and reused on regeneration — the
job is not re-extracted unless the URL changes.

**Failure modes:** LLM returns malformed JSON (retried via `llm_parse_with_retry`),
Playwright failed upstream (caught in pre-phase, never reaches here).

---

#### PHASE 2 — `enrich_job_chunks`

The most time-consuming phase. Splits the job posting into scored units that become
the backbone of the tailoring letter and gap analysis.

**Vector mode** (`MATCHING_MODE=vector`): one embedding call + one focused LLM call
per chunk. More precise context — the LLM sees only the most relevant experience
rather than the full profile. Requires `experience_id`.

**LLM mode** (default): full formatted profile sent to every batch. Simpler, no
embeddings required. Falls back to LLM mode automatically if vector mode is
configured but `experience_id` is unavailable.

Both modes use a `ThreadPoolExecutor` with a 5-minute wall-clock budget. Chunks that
time out receive `score=-1` and are excluded from the letter. Thread count is
controlled by `CHUNK_SCORER_CONCURRENCY` env var.

`embed_job_chunks` at the end is a no-op in vector mode (chunks already embedded
during scoring) and runs the embedding pass in LLM mode.

**Failure modes:** individual chunk scoring failures are counted in `chunk_error_count`
and do not abort the phase. A full phase failure marks `enrichment_status=error`.

---

#### PHASE 3 — `generate_advocacy_letter`  *(runs in parallel with Phase 4)*

Reads `JobChunk` scores from Phase 2 (via `build_ranked_matches_from_chunks` — an
internal DB read, not a separate logged phase), then makes one LLM call to produce
the tailoring output. The ranked match list ensures the letter opens with the
strongest fit signals.

Runs concurrently with Phase 4 via `ThreadPoolExecutor(max_workers=2)`. Gap analysis
depends only on `JobChunk` scores from Phase 2, not on the letter, so there is no
dependency between Phase 3 and Phase 4.

`tailoring.generation_status` is set to `"ready"` only after BOTH Phase 3 and Phase 4
complete successfully. This ensures the UI reveals fully-complete content.

**Failure modes:** LLM timeout or malformed output. Tailoring is marked `error`,
user can regenerate. Gap analysis failure does not abort this phase.

---

#### PHASE 4 — `gap_analysis`  *(runs in parallel with Phase 3)*

Uses `JobChunk.match_score` from Phase 2 as the authoritative source of gap
identification — no re-scoring. LLM calls are made only for question generation.

Runs concurrently with Phase 3. Wall-clock time for the parallel block is
`max(letter_time, gap_time)` rather than their sum.

Gap questions (score = 0) and partial questions (score = 1) are generated
sequentially within this phase. Each LLM call is targeted to one requirement.

`generation_complete` is logged after both phases finish, with `total_duration_ms`
covering all 4 background phases. If gap analysis fails, `generation_complete` is
still logged with `gap_analysis_failed=true`. On failure, `gap_analysis_status` is
set to `"error"` and the frontend shows a retry banner with
`POST /tailorings/{id}/retry-gap-analysis`.

---

### Observability

#### Key log events (all carry `tailoring_id` and `correlation_id`)

| Event | Phase | Notable fields |
|-------|-------|----------------|
| `phase_complete` | all | `phase`, `duration_ms` |
| `generation_complete` | after Phases 3+4 | `total_duration_ms`, `phase_durations` (all 4 background phases) |
| `generation_started` | start of background task | `matching_mode` |
| `chunks_extracted` | Phase 2 | `chunk_count`, `duration_ms` |
| `chunks_embeddings_complete` | Phase 2 | `duration_ms` |
| `enrich_job_chunks_complete` | Phase 2 | `chunk_count`, `batch_count`, `error_count`, `mode` |
| `llm_call_complete` | all LLM phases | `schema`, `input_tokens`, `output_tokens`, `latency_ms` |
| `run_gap_analysis_scoring_summary` | Phase 4 | `total_scored`, `sourced_count`, `gap_count`, `partial_count` |
| `phase_error` | any | `phase`, `error_message` |

#### End-to-end phase breakdown (Loki)

```logql
{job="tailord-backend"} | json | tailoring_id = "<id>" | event = "phase_complete"
```

Returns all 5 phases including pre-phase (`validate_job_posting`), each with `duration_ms`.

#### Full generation summary (Loki)

```logql
{job="tailord-backend"} | json | tailoring_id = "<id>" | event = "generation_complete"
```

Returns one line with `total_duration_ms` and the full `phase_durations` breakdown
for all 4 background phases.

#### Joining pre-phase to background task

The `correlation_id` bridges the HTTP handler (pre-phase) to the background task.
Both carry the same value. The `generation_started` event in the background task
carries both `correlation_id` and `tailoring_id`, making it the join key.

To get every log line for the full lifecycle of one tailoring creation:

```logql
{job="tailord-backend"} | json | correlation_id = "<correlation_id>"
```

Or find the `correlation_id` first via `tailoring_id`, then broaden:

```logql
# Step 1: find correlation_id
{job="tailord-backend"} | json | tailoring_id = "<id>" | event = "generation_started"

# Step 2: full timeline including pre-phase HTTP work
{job="tailord-backend"} | json | correlation_id = "<correlation_id>"
```

#### Trace waterfall (Tempo)

All 4 background phases have OTel spans. The `validate_job_posting` pre-phase span is
a direct child of the HTTP request span. The background task root span is parented
to the pre-phase span via W3C `traceparent` carrier injection (injected while the
pre-phase span is active), so the full waterfall appears as one trace.

```
POST /tailorings
└── tailoring.phase.validate_job_posting
    └── background_task.tailoring.generate
        ├── tailoring.phase.extract_job
        │     └── llm.call  (schema=ExtractedJob)
        ├── tailoring.phase.enrich_job_chunks
        │     ├── llm.call  (schema=ChunkMatchBatch) × N  [parallel]
        │     └── ...
        ├── tailoring.phase.generate_advocacy_letter        [parallel ─┐
        │     └── llm.call  (schema=TailoringContent)                  │
        └── tailoring.phase.gap_analysis                   [parallel ─┘
              ├── llm.call  (schema=GapQuestion) × gaps   [sequential]
              └── llm.call  (schema=GapQuestion) × partials [sequential]
```
