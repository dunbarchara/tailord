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

---

## Experience Flows

The Experience system manages a user's professional background — resume, GitHub repos,
manual claims, and gap responses. All data lives in a single `Experience` row per user.
The `extracted_profile` JSON column is keyed by source (`"resume"`, `"github"`,
`"user_input"`, `"corrections"`). `ExperienceChunk` rows are the vector-searchable units
consumed by the tailoring pipeline.

---

## Resume Upload & Processing

### Overview

Uploads a resume file (PDF, DOCX, or TXT), extracts structured profile data via LLM,
and produces searchable `ExperienceChunk` rows for use in tailoring generation.

| | |
|-|-|
| **Entry points** | `POST /experience/upload-url` → direct blob PUT → `POST /experience/process` |
| **HTTP handler** | `trigger_process` — `backend/app/api/experience.py` (SSE stream) |
| **Background task** | `embed_experience_chunks_task` — `backend/app/services/experience_embedder.py` |
| **Services** | `experience_processor.py` (extraction + LLM), `experience_embedder.py` (embeddings) |
| **Typical duration** | 5–15 seconds (SSE stream); embedding runs as a background task after SSE closes |

---

### Flow diagram

```
POST /experience/upload-url
│   ├── look up or create Experience row (status=pending)                        [SEQ · DB]
│   └── generate presigned blob upload URL                                       [SEQ · HTTP]
│       └── return { upload_url, experience_id }
│
│   ╌╌╌╌╌ Frontend PUTs file directly to blob storage ╌╌╌╌╌
│
POST /experience/process   (SSE stream)
│
├── STAGE: extracting
│   ├── download blob from storage → raw bytes                                   [SEQ · HTTP]
│   ├── extract_text(bytes, filename) → plain text                               [SEQ]
│   │   └── strategy by extension: pypdf (PDF), python-docx (DOCX), utf-8 (TXT)
│   ├── _normalize_resume_text() — strip control chars, collapse whitespace       [SEQ]
│   ├── persist raw_resume_text to Experience row                                 [SEQ · DB]
│   └── emit SSE stage="extracting"
│
├── STAGE: analyzing
│   ├── extract_profile(raw_text) → ExtractedProfile                             [SEQ · LLM]
│   │   └── LLM call → schema: ExtractedProfile
│   │       outputs: email, phone, linkedin, title, headline, summary,
│   │               work_experience[], skills{}, education[], projects[],
│   │               certifications[]
│   ├── apply profile corrections (extracted_profile["corrections"]) if present  [SEQ]
│   │   └── correction fields (yoe_override, headline, title, etc.) overwrite
│   │       corresponding resume profile fields
│   ├── persist extracted_profile["resume"] to Experience row                    [SEQ · DB]
│   ├── experience.status = "ready"                                               [SEQ · DB]
│   └── emit SSE stage="analyzing"
│
├── chunk_resume(experience) → ExperienceChunk rows                              [SEQ · DB]
│   ├── for each work_experience entry: one chunk per bullet (claim_type=work_experience)
│   ├── for each skill: one chunk per skill (claim_type=skill)
│   ├── for each project: one chunk per project (claim_type=project)
│   ├── for each education entry: one chunk (claim_type=education)
│   └── all chunks: source_type="resume", group_key=company/institution, date_range=…
│
├── schedule embed_experience_chunks_task as BackgroundTask                       [SEQ]
│
└── emit SSE event="ready" → client polls GET /experience until status="ready"
```

---

### Phase reference

#### Stage 1 — `extracting`

Downloads the file from blob storage and converts it to plain text. Three extraction
strategies keyed on file extension:
- **PDF** — `pypdf.PdfReader` page-by-page text extraction
- **DOCX** — `python-docx` paragraph extraction
- **TXT** — direct UTF-8 decode

`_normalize_resume_text` strips non-printable characters, normalises Unicode, and
collapses consecutive blank lines. The normalised text is persisted as `raw_resume_text`
for debug and regeneration use.

**Failure modes:** blob not found (404), unsupported format (400), PDF encrypted/corrupt
(`experience.status = "error"`).

---

#### Stage 2 — `analyzing`

One LLM call via `llm_parse_with_retry` with `response_model=ExtractedProfile`. The
full normalised resume text is included in the prompt.

Corrections stored in `extracted_profile["corrections"]` are applied immediately after
LLM extraction: fields like `yoe_override`, `headline`, `title`, `location`, and contact
fields overwrite what the LLM produced.

The merged result is persisted as `extracted_profile["resume"]` and `experience.status`
is set to `"ready"`.

---

#### Chunking + Embedding (post-stream background)

`chunk_resume` converts the structured `ExtractedProfile` into flat `ExperienceChunk`
rows — one chunk per atomic unit (bullet, skill, project, etc.). Group keys and date
ranges from work experience are preserved as chunk metadata for context construction
during tailoring enrichment.

`embed_experience_chunks_task` is dispatched as a FastAPI `BackgroundTask` immediately
before the SSE stream closes. It embeds all unembedded chunks via the embedding endpoint.
Embeddings are required for vector-mode tailoring generation.

---

### Observability

#### Key log events

| Event | Stage | Notable fields |
|-------|-------|----------------|
| `phase_complete` | extracting / analyzing | `phase`, `duration_ms` |
| `resume_chunks_extracted` | chunking | `chunk_count`, `duration_ms` |
| `processing_complete` | summary | `total_duration_ms`, `phase_durations` |
| `llm_call_complete` | analyzing | `schema=ExtractedProfile`, `input_tokens`, `output_tokens`, `latency_ms` |
| `embed_experience_chunks_complete` | background | `embedded`, `total`, `duration_ms` |
| `processing_error` | any | exception traceback |

#### Prometheus metrics

| Metric | Labels | Description |
|--------|--------|-------------|
| `experience_phase_duration_ms` | `phase` | Per-phase histogram (extracting / analyzing / chunking) |
| `experience_processing_total` | `status` (success / error) | Completion counter |
| `experience_processing_duration_ms` | — | End-to-end histogram |

```promql
# P95 LLM extraction time
histogram_quantile(0.95, rate(experience_phase_duration_ms_bucket{phase="analyzing"}[1h]))
```

#### OTel trace waterfall

```
POST /experience/process
└── experience.phase.extracting
└── experience.phase.analyzing
    └── llm.call  (schema=ExtractedProfile)
└── experience.phase.chunking
```

#### All log lines for one processing run

```logql
{job="tailord-backend"} | json | experience_id = "<id>"
```

#### Phase breakdown

```logql
{job="tailord-backend"} | json | experience_id = "<id>" | event = "phase_complete"
```

#### Processing summary

```logql
{job="tailord-backend"} | json | experience_id = "<id>" | event = "processing_complete"
```

---

## GitHub Enrichment

### Overview

Connects a GitHub account, lists its public repos, and enriches each repo using the
GitHub API and LLM. Produces `ExperienceChunk` rows keyed to `source_type="github"`.

| | |
|-|-|
| **Entry points** | `GET /experience/github/{username}/repos` → `POST /experience/github` |
| **Background task** | `enrich_github_repos` — `backend/app/services/github_enricher.py` |
| **Services** | `github_enricher.py`, `experience_embedder.py` |
| **Typical duration** | 30–120 seconds background (depends on repo count; GitHub API + N LLM calls) |

---

### Flow diagram

```
GET /experience/github/{username}/repos   (preview — no write)
│   ├── GET https://api.github.com/users/{username}/repos                        [SEQ · HTTP]
│   │   └── returns list: name, description, language, stars, pushed_at
│   └── return repo list to frontend for user selection
│
POST /experience/github
│   ├── persist github_username + github_repos (metadata list) to Experience     [SEQ · DB]
│   └── schedule enrich_github_repos as BackgroundTask                           [SEQ]
│       └── return immediately (202-style)
│
│   ╌╌╌╌╌ Background enrichment ╌╌╌╌╌
│
enrich_github_repos(experience_id)
│
├── for each repo (sequentially):                                                 [SEQ]
│   ├── GET /repos/{owner}/{repo}/languages                                      [SEQ · HTTP]
│   ├── GET /repos/{owner}/{repo}/topics                                         [SEQ · HTTP]
│   ├── GET /repos/{owner}/{repo}/readme → base64 decode                         [SEQ · HTTP]
│   ├── GET /repos/{owner}/{repo}/contents (package.json / requirements.txt /    [SEQ · HTTP]
│   │       pyproject.toml / Cargo.toml — first match wins)
│   ├── GET /repos/{owner}/{repo}/actions/workflows (CI presence signal)         [SEQ · HTTP]
│   └── _llm_enrich_repo(repo_data) → GitHubRepoEnrichment                      [SEQ · LLM]
│       └── LLM call → schema: GitHubRepoEnrichment
│           outputs: readme_summary, detected_stack[], project_domain,
│                    confidence (high/medium/low)
│
├── merge results into extracted_profile["github"]                               [SEQ · DB]
│   └── additive: preserves existing "resume", "user_input", "corrections" keys
│
├── chunk_github_repo(experience, repo) → ExperienceChunk rows                  [SEQ · DB]
│   └── one chunk per repo: source_type="github", claim_type="project",
│       group_key=repo_name, content=formatted enrichment summary
│
└── embed_experience_chunks(db, experience_id)                                   [SEQ · HTTP]
    └── embeds all newly created chunks
```

---

### Phase reference

#### Repo metadata fetch

All five GitHub API calls per repo are made sequentially to stay within rate limits.
The readme is base64-decoded and truncated before being passed to the LLM. The manifest
check (package.json, requirements.txt, etc.) is a best-effort signal — missing files
are silently skipped.

`enrich_github_repos` creates its own DB session (background task, no request context).

---

#### LLM enrichment per repo

`_llm_enrich_repo` takes all fetched signals (language breakdown, topics, readme text,
manifest deps, CI presence) and produces a `GitHubRepoEnrichment` schema. The
`confidence` field (`high`/`medium`/`low`) reflects how much signal was available.
Repos with empty readmes and no manifest get `low` confidence.

**Failure modes:** GitHub API rate limit (logs error, marks repo failed, continues);
individual LLM call failure (repo skipped, others continue). A full background task
failure leaves `extracted_profile["github"]` partially populated.

---

#### Chunking + Embedding

Each enriched repo becomes one `ExperienceChunk`. The chunk content is a formatted
summary including stack, domain, readme summary, and confidence level — designed to
be semantically rich enough for vector similarity against job requirements.

`embed_experience_chunks` is called synchronously at the end of the background task
(not as a further nested background task).

---

### Observability

#### Key log events

| Event | Notable fields |
|-------|----------------|
| `github_repo_enrichment_complete` | `repo_name`, `confidence`, `duration_ms` |
| `github_repo_enrichment_failed` | `repo_name`, `duration_ms` |
| `github_enrichment_complete` | `repo_count`, `error_count`, `chunk_count`, `duration_ms` |
| `llm_call_complete` | `schema=GitHubRepoEnrichment`, `latency_ms` (one per repo) |
| `embed_experience_chunks_complete` | `embedded`, `total`, `duration_ms` |

#### Prometheus metrics

| Metric | Labels | Description |
|--------|--------|-------------|
| `github_enrichment_total` | `status` (success / partial / error) | Completion counter |
| `github_enrichment_duration_ms` | — | End-to-end histogram |

```promql
# GitHub enrichment success rate
rate(github_enrichment_total{status="success"}[1h]) /
rate(github_enrichment_total[1h])
```

#### OTel trace waterfall

```
background_task.experience.github_enrichment     ← root span (no HTTP parent)
    ├── experience.github.enrich_repo  (repo=A)
    │     └── llm.call  (schema=GitHubRepoEnrichment)
    └── experience.github.enrich_repo  (repo=B)
          └── llm.call  (schema=GitHubRepoEnrichment)
```

#### All enrichment logs for one experience

```logql
{job="tailord-backend"} | json | experience_id = "<id>"
```

#### Per-repo timing

```logql
{job="tailord-backend"} | json | experience_id = "<id>" | event = "github_repo_enrichment_complete"
```

#### Enrichment summary

```logql
{job="tailord-backend"} | json | experience_id = "<id>" | event = "github_enrichment_complete"
```

---

## User Input (Manual Claims)

### Overview

Allows users to add freeform experience claims that don't appear in their resume or
GitHub. Supports a preview parse step and a persist step. Produces `ExperienceChunk`
rows with `source_type="user_input"`.

| | |
|-|-|
| **Entry points** | `POST /experience/user-input/parse` (preview) · `POST /experience/user-input/chunks` (persist) |
| **Services** | `experience_embedder.py` |
| **Typical duration** | Parse: 1–3 seconds (LLM); Persist: < 1 second + background embed |

---

### Flow diagram

```
POST /experience/user-input/parse   (optional preview — no write)
│   ├── if text length > threshold:
│   │   └── LLM call → ParsedClaims                                              [SEQ · LLM]
│   │       └── outputs: structured list of atomic claims extracted from text
│   └── return parsed claims to frontend (preview only, nothing persisted)
│
POST /experience/user-input/chunks
│   ├── receive list of claim strings
│   ├── upsert ExperienceChunk rows (source_type="user_input")                   [SEQ · DB]
│   │   └── one row per claim; position assigned sequentially
│   ├── schedule embed_experience_chunks_task as BackgroundTask                  [SEQ]
│   └── return updated chunks list
```

---

### Phase reference

#### Parse (preview)

`POST /experience/user-input/parse` is a stateless preview endpoint. It runs a
`ParsedClaims` LLM call to break long freeform text into discrete, atomic claims —
one per meaningful statement — so the user can review before committing. Nothing is
written to the DB. The frontend may show the result as an editable list.

For short input (under the length threshold), the text is returned as a single claim
without an LLM call.

---

#### Persist + Embed

`POST /experience/user-input/chunks` accepts the final list of claim strings. Each
becomes one `ExperienceChunk`. Position is assigned sequentially starting from the
current max position for `user_input` chunks on that experience.

`embed_experience_chunks_task` is dispatched as a background task. Until it completes,
the new chunks have no embedding vector and are not searchable in vector mode.

---

### Observability

| Event | Notable fields |
|-------|----------------|
| `llm_call_complete` | `schema=ParsedClaims`, `latency_ms` (parse preview only) |
| `embed_experience_chunks_complete` | `chunk_count`, `duration_ms` |

---

## Gap Response / Re-scoring

### Overview

The most operationally complex experience flow. When a user answers a gap or partial
question from the tailoring analysis, their answer is stored as an `ExperienceChunk`,
the relevant `JobChunk` is immediately re-scored against the new evidence, and the
gap analysis is updated synchronously in the same request.

| | |
|-|-|
| **Entry point** | `POST /experience/gap-response` |
| **Services** | `chunk_matcher.py` (`re_enrich_single_chunk`), `gap_analyzer.py` (`_generate_question`) |
| **Typical duration** | 1–5 seconds (1–2 synchronous LLM calls) |

---

### Flow diagram

```
POST /experience/gap-response
│   (body: tailoring_id, job_chunk_id, answer_text, response_type)
│
├── validate tailoring ownership + gap_analysis_status = "complete"              [SEQ · DB]
│
├── upsert ExperienceChunk for the answer                                        [SEQ · DB]
│   ├── source_type = "gap_response"     (if response_type="gap")
│   ├── source_type = "partial_response" (if response_type="partial")
│   └── source_type = "additional_experience" (freeform addition)
│
├── embed answer chunk synchronously                                             [SEQ · HTTP]
│   └── re_embed_chunk(chunk) — single-chunk embedding call
│
├── re_enrich_single_chunk(tailoring_id, job_chunk_id) → new score              [SEQ · LLM]
│   ├── load job chunk + current experience profile                              [SEQ · DB]
│   ├── [vector mode] cosine similarity against updated experience chunks        [SEQ · DB]
│   ├── LLM call → ChunkMatchBatch (single chunk, updated context)               [SEQ · LLM]
│   │   └── outputs: new match_score, advocacy_blurb, should_render,
│   │                experience_sources
│   └── persist updated JobChunk fields to DB                                    [SEQ · DB]
│
├── if new score = 1 (partial):
│   └── _generate_question("partial", job_chunk) → GapQuestion                  [SEQ · LLM]
│       └── on-demand partial question for the newly-partial requirement
│
└── return { updated_chunk, new_score, partial_question? }
```

---

### Phase reference

#### Answer storage

The answer text is stored as an `ExperienceChunk` with `source_type` derived from
`response_type`. This means gap answers permanently join the user's experience profile
and are available in future tailoring runs — not just the current one.

`chunk_id` on the `ProfileGap` record is updated to link the gap question to its answer
chunk for display purposes.

---

#### Synchronous re-scoring

`re_enrich_single_chunk` re-runs the full scoring pipeline for one job chunk — with
the new answer included as part of the experience context. In vector mode this involves
a cosine similarity search that will now rank the newly-embedded answer chunk, giving
the LLM access to it. In LLM mode, the full formatted profile (including the new
chunk) is passed.

This is a synchronous, in-request LLM call. The score change is immediately visible
to the caller.

**Failure modes:** embedding failure (500, answer is persisted but re-scoring aborts);
LLM failure (500, answer persisted, score not updated).

---

#### Conditional partial question generation

If re-scoring moves a chunk from score 0 (gap) to score 1 (partial), the answer was
good but not sufficient for a `STRONG` match. A `_generate_question("partial", ...)` call
produces a follow-up question asking the user to strengthen the evidence. This question
is returned inline in the response — no DB poll needed.

---

### Observability

| Event | Notable fields |
|-------|----------------|
| `gap_response_complete` | `job_chunk_id`, `new_score`, `duration_ms`, `partial_question_generated` |
| `re_enrich_single_chunk_complete` | `chunk_id`, `old_score`, `new_score` |
| `llm_call_complete` | `schema=ChunkMatchBatch`, `latency_ms` (re-scoring) |
| `llm_call_complete` | `schema=GapQuestion`, `latency_ms` (partial question, if generated) |

#### Prometheus metrics

| Metric | Labels | Description |
|--------|--------|-------------|
| `gap_response_duration_ms` | — | End-to-end histogram including embed + re-score + optional question |

```promql
# P95 gap response latency
histogram_quantile(0.95, rate(gap_response_duration_ms_bucket[1h]))
```

#### OTel trace waterfall

```
POST /experience/gap-response
└── experience.gap_response
    └── llm.call  (schema=ChunkMatchBatch)      ← re-scoring
    └── llm.call  (schema=GapQuestion)           ← partial question (if triggered)
```

#### All gap response events for a tailoring

```logql
{job="tailord-backend"} | json | tailoring_id = "<id>" | event =~ "re_enrich.*|gap_response.*"
```

#### LLM calls attributed to gap responses

```logql
{job="tailord-backend"} | json | tailoring_id = "<id>" | event = "llm_call_complete"
  | schema =~ "ChunkMatchBatch|GapQuestion"
```

---

## Profile Corrections

### Overview

Lightweight flow. Allows users to override specific fields from the LLM-extracted
resume profile without re-uploading their resume.

| | |
|-|-|
| **Entry point** | `PATCH /experience/profile` |
| **Typical duration** | < 100ms (pure DB write, no LLM) |

---

### Flow diagram

```
PATCH /experience/profile
│   (body: yoe_override?, headline?, title?, summary?, location?,
│          email?, phone?, linkedin?)
│
├── store correction fields in extracted_profile["corrections"]                  [SEQ · DB]
│   └── only non-null fields are stored; null = "remove correction"
│
├── re-apply corrections to extracted_profile["resume"] in place                 [SEQ · DB]
│   └── correction fields overwrite LLM-extracted equivalents
│
└── return updated extracted_profile
```

Corrections are applied at two points:
1. On `PATCH /experience/profile` — immediately overwrites the in-memory profile
2. On the next resume re-process — corrections are re-applied after LLM extraction,
   so a re-upload does not lose corrections

No re-chunking or re-embedding is triggered. If corrections change data that is
already chunked (e.g. headline), the user must re-upload for those changes to propagate
to `ExperienceChunk` rows and downstream tailoring generation.
