# LLM Flows Reference

All LLM calls in the Tailord pipeline. Use this as a map when debugging generation issues, estimating cost, or understanding what fires when.

---

## 1. All Prompts Inventory

| File | Temperature | Purpose | Caller |
|------|-------------|---------|--------|
| `prompts/profile_extraction.py` | 0.1 | Parse resume text → `ExtractedProfile` JSON | `experience_processor.py` |
| `prompts/github_enrichment.py` | 0.1 | Summarise one GitHub repo → structured signals | `experience_processor.py` (per repo) |
| `prompts/user_input_parse.py` | 0.1 | Extract atomic claims from free-text user input | `experience_processor.py` |
| `prompts/job_extraction.py` | 0.2 | Scraped job page → structured `ExtractedJob` JSON | `job_extractor.py` |
| `prompts/requirement_matching.py` | 0.1 | Score candidate against named job requirements (STRONG / PARTIAL) | `requirement_matcher.py` |
| `prompts/chunk_matching.py` | 0.1 | Score individual job chunks against candidate profile | `chunk_matcher.py` |
| `prompts/tailoring.py` | 0.3 | Generate the full tailoring document from ranked matches | `tailoring_generator.py` |
| `prompts/gap_analysis.py` | 0.3 | Identify unmet requirements → targeted follow-up questions | `gap_analyzer.py` (per gap) |

---

## 2. Chunk Architecture

There are two separate chunk tables with different purposes and lifecycles. Understanding this distinction is essential for understanding how the pipeline actually works.

### ExperienceChunk — candidate-side

**Table:** `experience_chunks`
**Created by:** `experience_chunker.py` (deterministic, no LLM)
**When:** After each experience processing event (resume parse, GitHub enrichment, user input submission, gap response)
**What:** Atomic claims derived from `Experience.extracted_profile` JSON

Chunking strategy per source:
- **resume** (`source_type="resume"`): 1 chunk per work experience bullet, per skill (technical + soft), per project description, per education entry, per certification — grouped by `group_key` (e.g. `"Acme | Software Engineer"`)
- **github** (`source_type="github"`): 1 chunk per repo readme_summary + 1 chunk per detected_stack item, `source_ref=repo_name`, `group_key=repo_name`
- **user_input** (`source_type="user_input"`): 1 chunk per atomic claim extracted from free text
- **gap_response** (`source_type="gap_response"`): 1 chunk per gap answer; never deleted by source events (only by full experience cascade); carries `chunk_metadata={question, job_chunk_id, tailoring_id}`

All ExperienceChunk rows get a 1536-dim embedding after creation (via `experience_embedder.py`). The embedding encodes the `content` field using `text-embedding-3-small`.

**Primary use:** Vector retrieval in `MATCHING_MODE=vector` — the only LLM call that reads ExperienceChunk rows directly.

### JobChunk — job-side

**Table:** `job_chunks`
**Created by:** `chunk_extractor.py` (deterministic, no LLM)
**When:** During `enrich_job_chunks()` background task
**What:** The job posting markdown split into typed chunks

Chunking strategy: regex-based markdown parser — `header` (section names), `bullet` (list items), `paragraph` (prose blocks ≥ 20 chars). Each chunk carries its `section` (the most recent header content above it) and `position` (ordinal).

After scoring, each JobChunk row stores: `match_score`, `match_rationale`, `advocacy_blurb`, `experience_sources`, `should_render`, `enriched_at`, and (in vector mode) its own embedding.

**Primary use:** Chunk matching LLM scoring; displayed in the analysis view and posting view.

---

## 3. What Actually Feeds LLM Prompts

> **Important:** The "everything is chunks → downstream LLM calls use filtered chunks" model describes the intended direction, but the current pipeline is hybrid. Here is what actually feeds each LLM call today.

### `_format_sourced_profile()` — the shared prose renderer

Most LLM calls receive the candidate profile as prose rendered by `tailoring_generator._format_sourced_profile()`. This reads directly from `Experience.extracted_profile` (the raw JSON) and formats it into labeled blocks:

```
[CANDIDATE]
Name: ...
Pronouns: ...

[COMPUTED SIGNALS — treat as ground truth]
Total professional experience: 5.2 years
Roles (chronological): ...

[Source: Resume]
Technical skills: Python, React, ...
Work Experience:
  Software Engineer @ Acme (01/2021 - 03/2024)
  - Built REST APIs in Node.js
  ...

[Source: GitHub]
Repos (3):
  my-project [web app]
    Summary: ...
    Stack: React, TypeScript
  ...

[Source: Direct Input]
...
```

This is **not** derived from ExperienceChunk rows — it is rendered fresh from the stored JSON each time. ExperienceChunk rows are a parallel representation used for vector retrieval and display.

### What each LLM call receives

| LLM Call | Profile input | Chunk rows used? |
|----------|--------------|-----------------|
| `requirement_matching` | `_format_sourced_profile()` prose | No |
| `chunk_matching` (llm mode) | `_format_sourced_profile()` prose | No — full profile sent |
| `chunk_matching` (vector mode) | Grouped context block from top-K `ExperienceChunk` rows | **Yes** — the only call that reads ExperienceChunk rows |
| `tailoring` | `_format_sourced_profile()` prose + ranked matches block | No |
| `gap_analysis` | `_format_sourced_profile()` prose | No |

In **vector mode**, the context block is not the full profile. Instead, for each JobChunk being scored, the top-K most similar `ExperienceChunk` rows (by cosine distance on embeddings) are retrieved and reformatted into a grouped context block. The LLM sees a focused slice of the candidate's experience that is semantically closest to the job requirement, rather than the full profile.

---

## 4. Experience Parsing

**Trigger:** User uploads a resume, connects GitHub, or submits user input text. Processing is dispatched as a FastAPI `BackgroundTask` from `experience.py`.

### 4a. Resume / File Upload
1. File downloaded from blob storage by `experience_processor.py`
2. Text extracted (pypdf / python-docx / plain text)
3. **LLM call** → `profile_extraction.py` → returns `ExtractedProfile` JSON
4. Stored in `Experience.extracted_profile["resume"]`
5. (Deterministic) `experience_chunker.chunk_resume()` creates `ExperienceChunk` rows
6. `experience_embedder.embed_experience_chunks()` embeds all new chunks

### 4b. GitHub Enrichment
1. Basic repo list fetched from GitHub API (no LLM)
2. For each repo: README + language breakdown fetched
3. **LLM call per repo** → `github_enrichment.py` → returns `GitHubEnrichedRepo` (readme_summary, detected_stack, project_domain, confidence)
4. Stored in `Experience.github_repo_details` and merged into `Experience.extracted_profile["github"]`
5. (Deterministic) `experience_chunker.chunk_github_repo()` creates `ExperienceChunk` rows per repo
6. `experience_embedder.embed_experience_chunks()` embeds all new chunks

### 4c. User Input + Gap Responses
1. User submits free text via the experience form or answers a gap question
2. **LLM call** → `user_input_parse.py` → returns atomic professional claims
3. Stored as `ExperienceChunk` rows with `source_type = "user_input"` or `"gap_response"`
4. Chunk embedded immediately

---

## 5. Job Posting Parsing

**Trigger:** User submits a job URL in the "New Tailoring" form.

1. **Playwright scrape** (`core/scraper.py`) → raw HTML → markdown text
2. **LLM call** → `job_extraction.py` → structured `ExtractedJob` (title, company, requirements, responsibilities, etc.)
3. `Job` row created with `extracted_job` JSON (keyed fields) and the raw markdown preserved
4. (Deterministic) `chunk_extractor.extract_chunks()` parses the job markdown into `RawChunk` objects — no DB write yet; DB write happens in `enrich_job_chunks()`
5. Chunk scoring/matching runs next (Section 6b)

---

## 6. Tailoring Generation

**Trigger:** User clicks "Generate" or "Regenerate". Runs as a background task. Four sequential LLM sub-flows:

### 6a. Requirement Matching
- **Prompt:** `requirement_matching.py` (temp 0.1)
- **Input:** `_format_sourced_profile()` prose + named requirements from `extracted_job`
- Scores each requirement STRONG (2) / PARTIAL (1) / NOT MET (0)
- Returns `experience_sources: list[str]` per requirement (can be multiple: resume + github)
- Output feeds the tailoring prompt as a ranked match block

### 6b. Chunk Matching / Enrichment
- **Prompt:** `chunk_matching.py` (temp 0.1)
- Scores every `JobChunk` against the candidate profile
- Two modes (controlled by `MATCHING_MODE` env var):
  - `llm` (default): **input is `_format_sourced_profile()` prose** — full profile sent in batches of 3 chunks per call
  - `vector`: **input is a grouped context block of top-K `ExperienceChunk` rows** — one call per chunk (see Section 7)
- Persists scores, rationales, advocacy blurbs, and `experience_sources` to `JobChunk` rows
- Runs in a separate background task (`enrich_job_chunks`) kicked off at tailoring creation

### 6c. Tailoring Generation
- **Prompt:** `tailoring.py` (temp 0.3)
- **Input:** `_format_sourced_profile()` prose + `_format_ranked_matches()` block (from 6a output)
- Produces the full markdown tailoring document (cover letter + advocacy sections)
- `profile_snapshot` (the exact formatted profile string) is saved on the `Tailoring` row for debug reproducibility

### 6d. Gap Analysis
- **Prompt:** `gap_analysis.py` (temp 0.3)
- **Input:** `_format_sourced_profile()` prose + unmet requirements
- Runs after generation completes, in the same background task
- One LLM call per gap (requirement with score 0 or low evidence)
- Each call returns: `job_requirement`, `question_for_candidate`, `context`, `chunk_id`
- Results stored as `Tailoring.gap_analysis` JSON
- Non-fatal: if gap analysis fails, tailoring is still `ready`

---

## 7. Vector Mode Deep-Dive

When `MATCHING_MODE=vector` and an `experience_id` is available:

1. **Embed job chunk** — `embed_text(chunk.content)` via `embedding_client.py` → 1536-dim vector
2. **Cosine retrieval** — pgvector `cosine_distance` query on `ExperienceChunk.embedding`, scoped to `experience_id`, top-K results (default K=8, controlled by `VECTOR_TOP_K`). Skips rows with null embeddings.
3. **Group context** — `_build_grouped_context()` formats the top-K rows by `(group_key, date_range, source_type)` so the LLM sees coherent work-experience entries, not isolated bullets. Gap response / additional experience chunks are grouped under "Candidate Notes".
4. **Single LLM call** → `USER_TEMPLATE_VECTOR` with the candidate header + job requirement + grouped context
5. The job chunk embedding is stored on the `JobChunk` row; `embed_job_chunks()` at the end skips chunks already embedded in step 1

Fallback: if `experience_id` is not provided (legacy codepath), falls back to `llm` mode automatically.

**Note:** In vector mode, the LLM only sees the experience chunks most semantically similar to the specific job requirement — typically 8 out of potentially hundreds of chunks. This focuses context but means evidence that uses different vocabulary from the requirement may not be retrieved.

---

## 8. Re-Enrichment Path (Gap Answer → Single Chunk Re-Score)

**Trigger:** User submits an answer to a gap question.

1. Answer appended to `Experience.user_input_text`
2. New `ExperienceChunk` row created with `source_type = "gap_response"`, `chunk_metadata = {question, job_chunk_id, tailoring_id}`
3. Chunk embedded immediately (if embedding service available)
4. **`re_enrich_single_chunk()`** called as background task — re-scores only the linked `JobChunk`
5. Dispatches to vector or llm mode based on `MATCHING_MODE`, same as full enrichment
6. Updates `JobChunk.match_score`, `match_rationale`, `advocacy_blurb`, `experience_sources`, `should_render`
7. Full tailoring is NOT regenerated — only the single chunk score changes

---

## 9. Embedding Infrastructure

- **Model:** `text-embedding-3-small` (default; override with `EMBEDDING_MODEL`)
- **Dimensions:** 1536 (pgvector `Vector(1536)` column on both `ExperienceChunk` and `JobChunk`)
- **Client:** `embedding_client.py` — OpenAI-compatible, separate from the chat LLM client
- **Base URL resolution:**
  1. `EMBEDDING_BASE_URL` set → use it
  2. `EMBEDDING_API_KEY` set, no `EMBEDDING_BASE_URL` → use OpenAI default
  3. Neither set → fall back to `LLM_BASE_URL` (Azure AI Foundry; managed identity in prod)
- **Invocation sites:**
  - `experience_embedder.embed_experience_chunks()` — embeds `ExperienceChunk` rows after processing; called inline from background tasks
  - `experience_embedder.embed_experience_chunks_task()` — background-task variant with its own DB session; used when the request session must not be held open
  - `experience_embedder.embed_job_chunks()` — embeds `JobChunk` rows after scoring; called at end of `enrich_job_chunks()`; skips rows already embedded in vector mode
  - `experience_embedder.re_embed_chunk()` — re-embeds a single `ExperienceChunk` when its content is updated via PATCH
  - `chunk_matcher._score_chunk_vector()` — embeds the `JobChunk` content at score time (vector mode only)

---

## 10. Background Task Chain

Full sequence from "Generate Tailoring" button click to gap questions ready:

```
POST /tailorings  (request handler, synchronous)
  │
  ├─ scrape job URL (Playwright, sync)
  ├─ extract job (LLM #1: job_extraction)
  │     input: raw job markdown
  ├─ create Job + Tailoring rows
  │
  ├─ BackgroundTask: generate_tailoring()
  │     ├─ match requirements (LLM #2: requirement_matching)
  │     │     input: _format_sourced_profile() prose + extracted_job requirements
  │     ├─ format profile snapshot (saved for debug)
  │     ├─ generate tailoring (LLM #3: tailoring)
  │     │     input: _format_sourced_profile() prose + ranked matches block
  │     ├─ tailoring.generation_status → "ready"
  │     └─ run_gap_analysis()
  │           ├─ per gap: (LLM #4+: gap_analysis)
  │           │     input: _format_sourced_profile() prose + unmet requirement
  │           └─ tailoring.gap_analysis_status → "complete"
  │
  └─ BackgroundTask: enrich_job_chunks()
        ├─ extract_chunks() — parse job markdown → RawChunk list (deterministic)
        ├─ [llm mode]  score chunks (LLM #5+: chunk_matching, batched 3/call)
        │     input: _format_sourced_profile() prose + chunk batch
        ├─ [vector mode] per chunk: embed → retrieve top-K ExperienceChunks → (LLM #5+: chunk_matching, 1/call)
        │     input: grouped context block of top-K ExperienceChunk rows
        ├─ persist JobChunk rows with scores + experience_sources
        ├─ embed_job_chunks() (embedding calls, non-LLM; skips vector-mode chunks already embedded)
        └─ tailoring.enrichment_status → "complete"
```

The two background tasks (`generate_tailoring` and `enrich_job_chunks`) run concurrently. The tailoring document and gap questions are typically ready before chunk enrichment completes. The frontend polls both `generation_status` and `enrichment_status` independently.
