# Observability Walkthrough — Reflections

This document captures questions, answers, exercises, and notes from working through
`planning/26-observability-walkthrough.md`. The goal is to build genuine understanding
of how the platform is observed in production — not just that the tooling exists, but
why each piece is there and how to use it under pressure.

---

## Purpose of this directory

`reflections/` is a space to document understanding, not just decisions. Code and
features are often built by agents — this is where we make sure the human in the loop
stays current on what was built, why, and what it takes to operate it. Expect: learning
notes, answered questions, hands-on exercise results, and gaps flagged for follow-up.

---

## The Mental Model

Three signal types, each answering a different question:

| Signal | Question | Local tool | Azure equivalent |
|--------|----------|------------|-----------------|
| Logs | What happened, and when? | Loki + Grafana | Log Analytics |
| Metrics | How much / how fast / how often? | Prometheus + Grafana | Azure Managed Prometheus |
| Traces | Which operations caused which others? | Tempo + Grafana | Application Insights |

### Technology quick-reference

**Loki** — Log aggregation. Indexes only labels (metadata), not full text — cheap to
run. Logs are queried with LogQL. Locally via Docker; replaced by Log Analytics in Azure.

**Grafana** — Visualization UI. Connects to Prometheus, Loki, Tempo, PostgreSQL and
renders dashboards. Locally in Docker; Azure has a managed equivalent.

**Log Analytics** — Azure's managed log store. Container Apps auto-ship stdout here —
no Promtail needed. Queried with KQL instead of LogQL.

**Prometheus** — Metrics collection. Scrapes `/metrics` every 15s, stores numeric
time-series. Queried with PromQL. Locally in Docker.

**Azure Managed Prometheus** — Hosted Prometheus. Same PromQL queries, Microsoft manages
the infrastructure.

**Tempo** — Distributed tracing backend. Receives spans via OTLP, stores them, lets
you view trace waterfalls in Grafana Explore. No direct UI — local only.

**Application Insights** — Azure's tracing (and more) service. Receives OTel spans via
`AzureMonitorTraceExporter`. Provides transaction search, waterfall views, live metrics.
Replaces Tempo in production.

**structlog** — Python structured logging library. Produces dicts of key/value pairs
serialised to JSON instead of flat text strings. Makes logs machine-queryable and
filterable without regex.

**Histogram** — A metric type tracking the distribution of a value (e.g. latency) by
counting observations into predefined buckets. Lets you compute P95, P99 at query time.

**LGTM** — Acronym for the local stack: Loki + Grafana + Tempo + (managed) Prometheus.

**OTel (OpenTelemetry)** — Vendor-neutral standard for instrumentation. Defines a common
API and wire format (OTLP) for traces, metrics, and logs. Code instruments against the
OTel API; the exporter (Tempo locally, App Insights in Azure) is swapped without touching
instrumentation code.

**OTLP (OpenTelemetry Protocol)** — The wire format OTel uses to send telemetry between
systems. Supports gRPC (port 4317, used locally to Tempo) and HTTP/protobuf (port 4318).
The key idea: instrumentation code is decoupled from the backend — swap the exporter, not
the instrumentation.

---

## Section 1 — Logs

### How Loki works

Loki only indexes labels (metadata like `job="tailord-backend"`). Log content is stored
compressed and unindexed. This makes storage cheap but full-text search requires scanning
compressed chunks. The common case — you know which stream you want, then filter within
it — is fast.

Local flow:
1. Python writes JSON lines to `logs/app.jsonl`
2. Promtail tails the file and ships lines to Loki with labels attached
3. Loki stores lines indexed by labels only
4. Grafana queries with LogQL: label selector first (`{job="tailord-backend"}`), then
   optional pipeline filters (`| json | level = "error"`)

The `| json` step is key: it parses each line as JSON at query time, making any field
(like `tailoring_id`) filterable without pre-indexing it.

---

### Section 1 observability tasks

These are hands-on exercises using a real tailoring created during this walkthrough
session. Tailoring ID: `19a64901-7d97-4507-8a54-c6d6f95e8c07`

All tasks use **Grafana → Explore → Loki → Code mode** at `http://localhost:3001`.
Substitute your own tailoring ID when repeating these.

---

#### Task 1 — Pull every log line for a tailoring

**Goal:** confirm `tailoring_id` propagates through the background task.

```logql
{job="tailord-backend"} | json | tailoring_id = "19a64901-7d97-4507-8a54-c6d6f95e8c07"
```

Expect hundreds of lines — mostly SQLAlchemy and httpcore debug noise. What matters is
that every line carries `tailoring_id`, which proves the background task re-bound context
correctly at the top of `_finalize_tailoring`.

---

#### Task 2 — Get the phase breakdown

**Goal:** see all five pipeline phases and their individual durations (1 pre-phase + 4 background).

```logql
{job="tailord-backend"} | json | tailoring_id = "19a64901-7d97-4507-8a54-c6d6f95e8c07" | event = "phase_complete"
```

Expand each result to see the `phase` and `duration_ms` parsed fields.

Results from this session (tailoring `19a64901`):
```
validate_job_posting      →     82ms   (pre-phase, logged from HTTP handler)
extract_job               →  2,194ms
enrich_job_chunks         →  6,690ms
generate_advocacy_letter  →  4,419ms  ┐ parallel — wall-clock contribution
gap_analysis              → 12,295ms  ┘ is max(4419, 12295) = 12,295ms
```

Note: `validate_job_posting` is the pre-phase and carries `tailoring_id` but not yet
`correlation_id` (it fires before the background task binds context). The other four
phases all carry both fields.

---

#### Task 3 — Get the total generation time in one line

**Goal:** read the `generation_complete` summary event.

```logql
{job="tailord-backend"} | json | tailoring_id = "19a64901-7d97-4507-8a54-c6d6f95e8c07" | event = "generation_complete"
```

Expand the single result — `total_duration_ms` and a nested `phase_durations` object are
both present. This session: `total_duration_ms = 13,353`.

Note: `generation_complete` fires after all 4 background phases complete (including
`gap_analysis`, which runs in parallel with `generate_advocacy_letter`). The
`phase_durations` object contains all 4 phases. `total_duration_ms` reflects wall-clock
time, so the parallel block contributes `max(letter, gap)`, not their sum.

---

#### Task 4 — Inspect individual LLM calls

**Goal:** see every LLM call attributed to this tailoring with token counts and latency.

```logql
{job="tailord-backend"} | json | tailoring_id = "19a64901-7d97-4507-8a54-c6d6f95e8c07" | event = "llm_call_complete"
```

Expand any line — `prompt_name`, `call_id`, `schema`, `input_tokens`, `output_tokens`,
`latency_ms` are all present.

- `schema` — Pydantic response model class name (e.g., `TailoringContent`, `GapQuestion`)
- `prompt_name` — human-readable constant from the prompt module (e.g., `tailoring_generation`,
  `gap_question`, `partial_match_question`). Defaults to the schema name if no constant is set.
  Useful for distinguishing calls that share a schema but use different prompts
  (e.g., `chunk_match_vector_single` vs `chunk_match_batch` — both use `ChunkMatchBatch`).
- `call_id` — 12-char hex that links `llm_parse_request`, `llm_refusal` (if any),
  `llm_parse_response`, and `llm_call_complete` for the same call. Filter by this to see
  the full request/response pair without time-range guessing.

Schemas visible here: `TailoringContent` (main generation call, `prompt_name=tailoring_generation`)
and `GapQuestion` (one per gap question, `prompt_name=gap_question` or `partial_match_question`).

The `enrich_job_chunks` LLM calls (`ChunkMatchBatch`) will not appear in runs created before the
ThreadPoolExecutor context propagation fix — see the ~~Gap~~ Fixed note below. All new runs emit
these with `tailoring_id` and `prompt_name` set to `chunk_match_vector_single`,
`chunk_match_vector_batch`, `chunk_match_batch`, or `chunk_match_single` depending on mode.

---

#### Task 5 — Find the slowest LLM call in the session

**Goal:** practice LogQL filtering across all requests.

```logql
{job="tailord-backend"} | json | event = "llm_call_complete"
```

In the results panel, use the Fields sidebar to sort by `latency_ms` descending. The
slowest call in this session was a `TailoringContent` schema call (`prompt_name=tailoring_generation`)
at ~4,407ms.

You can also filter by `prompt_name` directly to isolate a specific prompt type across
all tailorings — useful for tracking whether a particular prompt has regressed:

```logql
{job="tailord-backend"} | json | event = "llm_call_complete" | prompt_name = "tailoring_generation"
```

---

### ~~Gap~~ Fixed — enrich_chunks LLM calls now carry tailoring_id

`chunk_matcher.py` now captures `structlog.contextvars.get_contextvars()` before
dispatching to each `ThreadPoolExecutor`, and re-binds the context at the top of every
worker function. All `llm_call_complete` events inside the parallel scoring threads now
carry `tailoring_id` and `correlation_id`. Applied to all four dispatch sites: enrich
vector, enrich LLM, refresh vector, refresh LLM.

### ~~Gap~~ Fixed — positional log args converted to structured fields

All `logger.info("msg %s", val)` patterns in `chunk_matcher.py` and `gap_analyzer.py`
converted to `logger.info("event_name", field=val)`. Values are now queryable as
structured fields in Loki.

---

## Tailoring generation — pipeline reference

See `reflections/platform-flows.md` for the full canonical reference with line art
diagram, [SEQ]/[PAR] tags, phase failure modes, and observability queries.

Summary: 5 phases total — 1 pre-phase in the HTTP handler (`validate_job_posting`), 4 in
the background task (`extract_job`, `enrich_job_chunks`, `generate_advocacy_letter`,
`gap_analysis`). Phases 3 and 4 run in parallel via `ThreadPoolExecutor`. `generation_complete`
fires after all 4 background phases and includes `phase_durations` for all of them.

### Logging coverage (current state)

| Step | Logged? | Notes |
|------|---------|-------|
| Pre-phase validate_job_posting | `phase_complete` ✓ | carries `tailoring_id` + `correlation_id` |
| Phase 1 extract_job | `phase_complete` ✓ | |
| Phase 2 enrich_job_chunks | `phase_complete` ✓ | |
| Chunk parsing (inside phase 2) | `chunks_extracted` ✓ | `chunk_count`, `duration_ms` |
| Chunk scoring LLM calls | `llm_call_complete` ✓ | `prompt_name=chunk_match_vector_single/batch`, `call_id`; ThreadPoolExecutor context propagated |
| Chunk embedding step | `chunks_embeddings_complete` ✓ | |
| Phase 3 generate_advocacy_letter | `phase_complete` ✓ | runs in parallel with gap_analysis |
| generate_advocacy_letter LLM call | `llm_call_complete` ✓ | `prompt_name=tailoring_generation`, `call_id` |
| Phase 4 gap_analysis | `phase_complete` ✓ | runs in parallel with generate_advocacy_letter |
| Gap/partial question LLM calls | `llm_call_complete` ✓ | `prompt_name=gap_question` or `partial_match_question`, `call_id`; sequential |
| End-to-end summary | `generation_complete` ✓ | all 4 background phases in `phase_durations` |
| All phase errors | `phase_error` ✓ | |

---

## Experience flows — pipeline reference

See `reflections/platform-flows.md` for full flow diagrams and phase reference for all
experience flows. Summary below.

---

### Resume Upload & Processing

Three stages: `extracting` (blob download + text extraction) → `analyzing` (LLM profile
extraction) → `chunking` (resume → ExperienceChunk rows). The SSE stream closes after
chunking is complete; embedding runs as a background task.

Each stage emits a `phase_complete` event with `duration_ms`. A `processing_complete`
summary event fires at the end with `total_duration_ms` and a `phase_durations` breakdown.

#### Key log events

| Event | Stage | Notable fields |
|-------|-------|----------------|
| `phase_complete` | extracting / analyzing | `phase`, `duration_ms` |
| `resume_chunks_extracted` | chunking | `chunk_count`, `duration_ms` |
| `processing_complete` | summary | `total_duration_ms`, `phase_durations` |
| `llm_call_complete` | analyzing (call 1) | `prompt_name=resume_structure_extraction`, `schema=ExtractedStructure`, `input_tokens`, `output_tokens`, `latency_ms` |
| `llm_call_complete` | analyzing (call 2) | `prompt_name=profile_prose_generation`, `schema=ProfileIdentity`, `input_tokens`, `output_tokens`, `latency_ms` |
| `embed_experience_chunks_complete` | background | `embedded`, `total`, `duration_ms` |

#### Pull all logs for a processing run

Use `correlation_id` to scope to a specific run. Use `user_id` to see all experience events
for a user across sessions.

```logql
{job="tailord-backend"} | json | correlation_id = "<correlation_id>"
```

#### Phase breakdown

```logql
{job="tailord-backend"} | json | correlation_id = "<correlation_id>" | event = "phase_complete"
```

#### Processing summary

```logql
{job="tailord-backend"} | json | correlation_id = "<correlation_id>" | event = "processing_complete"
```

#### Find the profile extraction LLM calls

```logql
{job="tailord-backend"} | json | correlation_id = "<correlation_id>" | event = "llm_call_complete"
```

Two calls appear in the `analyzing` phase:
- `prompt_name=resume_structure_extraction` (`schema=ExtractedStructure`) — structured data extraction. Typically the most expensive call (~4–5s).
- `prompt_name=profile_prose_generation` (`schema=ProfileIdentity`) — generates headline and summary prose from the structured output (~1–1.5s).

---

### GitHub Enrichment

Background task. Fetches metadata per repo from the GitHub API, then calls the LLM
once per repo to produce a list of experience claims. Each claim becomes one
`ExperienceChunk` row (skills and prose experience bullets are separate chunks).
Runs after `POST /experience/github`.

`user_id` and `github_username` are bound as contextvars at the top of the background
task, so all log lines — including `llm_call_complete` from `llm_utils.py` — carry
these fields automatically.

#### Key log events

| Event | Notable fields |
|-------|----------------|
| `github_repo_enrichment_complete` | `repo_name`, `confidence`, `duration_ms` |
| `github_repo_enrichment_failed` | `repo_name`, `duration_ms` (per-repo error) |
| `github_enrichment_complete` | `repo_count`, `error_count`, `chunk_count`, `duration_ms` |
| `llm_call_complete` | `prompt_name=github_repo_enrichment`, `schema=GitHubRepoEnrichment`, `call_id`, `latency_ms` (one per repo) |
| `embed_experience_chunks_complete` | `embedded`, `total`, `duration_ms` |

#### See per-repo timing

```logql
{job="tailord-backend"} | json | correlation_id = "<correlation_id>" | event = "github_repo_enrichment_complete"
```

Each line has `repo_name`, `confidence`, and `duration_ms`. Confidence `low` means
the repo had little signal (no readme, no manifest). A high `duration_ms` here usually
means a slow LLM call, not a slow GitHub API call.

#### Check for partial enrichment failures

```logql
{job="tailord-backend"} | json | correlation_id = "<correlation_id>" | event = "github_enrichment_complete"
```

Expand the single result line — `error_count > 0` means some repos were skipped.
`chunk_count` reflects all claims that survived filtering (each skill and prose bullet
is one chunk, so a single active repo typically yields several to tens of chunks).
Individual repo failures appear as `github_repo_enrichment_failed` events with `repo_name`
and the exception traceback.

---

### User Input (Manual Claims)

Simple flow. Parse preview is optional and stateless. Persist writes chunks, embedding
runs as a background task.

#### Key log events

| Event | Notable fields |
|-------|----------------|
| `llm_call_complete` | `schema=ParsedClaims`, `latency_ms` (parse preview only — no write) |
| `embed_experience_chunks_complete` | `chunk_count`, `duration_ms` |

Note: `ParsedClaims` only fires if the user triggered the preview parse. Most users
paste short text and go straight to persist, so this log event may be absent.

---

### Gap Response / Re-scoring

The most operationally interesting experience flow. A user answering a gap question
triggers two synchronous LLM calls in a single request: one to re-score the job chunk
with the new evidence, and optionally one more to generate a partial follow-up question
if the score moved to 1.

`tailoring_id` and `user_id` are bound as contextvars at the start of the handler,
so all `llm_call_complete` events from `re_enrich_single_chunk` and `_generate_question`
carry these fields automatically — no manual propagation needed.

#### Key log events

| Event | Notable fields |
|-------|----------------|
| `gap_response_complete` | `job_chunk_id`, `new_score`, `duration_ms`, `partial_question_generated` |
| `re_enrich_single_chunk_complete` | `chunk_id`, `old_score`, `new_score` |
| `llm_call_complete` | `prompt_name=chunk_match_vector_single` or `chunk_match_single`, `schema=ChunkMatchBatch`, `call_id`, `latency_ms` — the re-scoring call |
| `llm_call_complete` | `prompt_name=partial_match_question`, `schema=GapQuestion`, `call_id`, `latency_ms` — partial question (only when score moves 0→1) |

#### See re-scoring outcome for a tailoring

```logql
{job="tailord-backend"} | json | tailoring_id = "<id>" | event = "re_enrich_single_chunk_complete"
```

Each line shows `old_score` → `new_score` for one job chunk. Score values:
- `0` = gap (no evidence)
- `1` = partial (some evidence, not strong)
- `2` = strong match

#### Gap response summary for a tailoring

```logql
{job="tailord-backend"} | json | tailoring_id = "<id>" | event = "gap_response_complete"
```

`partial_question_generated=true` means the answer moved the score to 1 and a follow-up
path-to-strong question was generated on demand.

#### LLM calls attributed to gap responses

```logql
{job="tailord-backend"} | json | tailoring_id = "<id>" | event = "llm_call_complete"
  | prompt_name =~ "chunk_match_vector_single|chunk_match_single|partial_match_question"
```

---

### Experience flows — logging coverage

| Step | Logged? | Notes |
|------|---------|-------|
| Resume text extraction | `phase_complete` ✓ | `phase=extracting`, `duration_ms` |
| Resume LLM extraction (call 1) | `phase_complete` ✓ + `llm_call_complete` ✓ | `phase=analyzing`, `prompt_name=resume_structure_extraction`, `schema=ExtractedStructure`, `call_id` |
| Resume prose generation (call 2) | `llm_call_complete` ✓ | `prompt_name=profile_prose_generation`, `schema=ProfileIdentity`, `call_id` (within same analyzing phase) |
| Resume chunking | `resume_chunks_extracted` ✓ | `chunk_count`, `duration_ms` |
| Processing end-to-end | `processing_complete` ✓ | `total_duration_ms`, `phase_durations` |
| Experience embedding (resume/user_input) | `embed_experience_chunks_complete` ✓ | `embedded`, `total`, `duration_ms` |
| GitHub per-repo enrichment | `github_repo_enrichment_complete` ✓ | `repo_name`, `confidence`, `duration_ms` |
| GitHub per-repo failure | `github_repo_enrichment_failed` ✓ | `repo_name`, traceback |
| GitHub enrichment summary | `github_enrichment_complete` ✓ | `repo_count`, `error_count`, `chunk_count`, `duration_ms` |
| GitHub LLM call per repo | `llm_call_complete` ✓ | `prompt_name=github_repo_enrichment`, `schema=GitHubRepoEnrichment`, `call_id` (`user_id` auto-carried via contextvar) |
| GitHub embedding | `embed_experience_chunks_complete` ✓ | |
| User input parse (preview) | `llm_call_complete` ✓ | `prompt_name=user_input_parsing`, `schema=ParsedClaims`, `call_id` (only if triggered) |
| Gap response chunk upsert | *(no structured event — pure DB write)* | |
| Gap response end-to-end | `gap_response_complete` ✓ | `job_chunk_id`, `new_score`, `duration_ms` |
| Gap response re-scoring LLM | `llm_call_complete` ✓ | `prompt_name=chunk_match_vector_single` or `chunk_match_single`, `schema=ChunkMatchBatch`, `call_id` (`tailoring_id` + `user_id` auto-carried via contextvar) |
| Gap response re-score outcome | `re_enrich_single_chunk_complete` ✓ | `old_score`, `new_score` |
| Partial question on-demand | `llm_call_complete` ✓ | `prompt_name=partial_match_question`, `schema=GapQuestion`, `call_id` (only when score→1) |
| Profile corrections write | *(no structured event)* | Pure DB write, no LLM |

---

## Questions from the walkthrough doc

These are questions posed in `planning/26-observability-walkthrough.md` as checkpoints.
Answers to be filled in as we work through each section.

### Section 1 — Logs

- Why do we clear contextvars at the start of each request rather than just overwriting?
- What happens to logs from a third-party library that uses `logging.getLogger` rather
  than `structlog.get_logger`? (Hint: look at `foreign_pre_chain` in `logging.py`.)
- Why does the background task need to re-bind context explicitly?

### Section 2 — Metrics

- What does the `_bucket`, `_count`, and `_sum` suffix mean on a histogram metric?
- Why does Prometheus pull metrics rather than having the app push them?
- Why do we use `rate()` rather than the raw counter value in dashboards?

### Section 3 — The Local LGTM Stack

- What is Promtail doing exactly? Trace the path from a `logger.info(...)` call in
  Python to a log line appearing in Loki.
- What would break if you changed the Grafana container name in docker-compose?

### Section 4 — Grafana Dashboards

- What is LogQL? How does `{job="tailord-backend"} | json | tailoring_id = "abc"` work?
- Why does Dashboard 05 use a PostgreSQL datasource instead of Prometheus or Loki?

### Section 5 — Distributed Tracing

- What is the W3C `traceparent` header format?
- What happens to the span tree if `carrier` is an empty dict (no parent context)?
- Why does `tailoring.phase.extract_job` appear as a child of the root background task
  span but not as a child of `POST /tailorings`?

### Section 7 — Alerting

- Why is `no-healthy-replicas` severity 0 but `container-restart` is severity 1?
  Shouldn't a restart be worse?
- What is the difference between evaluation frequency (`PT5M`) and window duration
  (`PT15M`)?
