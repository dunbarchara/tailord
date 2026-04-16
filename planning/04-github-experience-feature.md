# GitHub Experience Feature

*Planning document for the GitHub Experience epic. Covers philosophy, design decisions, and the phased implementation roadmap. Last updated: 2026-04-14.*

---

## What We're Building

Tailord can already ingest a resume and extract structured experience from it. GitHub extends that — it gives us **evidence**. A tailoring that says "proficient in TypeScript" is weak. One that says "maintained a 40k-line TypeScript codebase with React, PostgreSQL, and Docker" and can cite a specific repo is strong.

The GitHub Experience feature crawls a user's public GitHub presence, selects the repositories they designate as representative of their work, extracts structured signals from each (tech stack, README intent, dependency graph, project domain), and stores these as per-repo summaries that feed into tailoring generation alongside the resume.

The core value proposition: **sourced, specific evidence over vague claims.**

---

## Philosophy

### Public-first, privacy by design

Tailord's model is that users control what represents them. GitHub fits naturally into this: a user's public repositories are already public — we're summarizing what's already out there, not extracting private information. This means:

- We only operate on **public repositories**
- The user **elects which repos** to include as signals (not auto-selected)
- We acknowledge upfront that in multi-contributor repos, we treat the codebase as representative of the user's work (with a clear acknowledgement step in the UI)
- No private repo access, no GitHub login required in Phase 1

This design sidesteps most privacy concerns and keeps the LLM context clean: the model only ever sees what the user has chosen to surface.

### Signals over code

We are not static analysis tools. We don't need to read every file in a repository to reason about it. The signal-to-noise ratio of raw code is terrible — a 50,000-file monorepo has maybe five files worth reading.

The right sources of signal are:
- **Repo metadata** — language stats (byte-weighted), stars, topics, last active
- **Dependency manifests** — `package.json`, `pyproject.toml`, `go.mod` — the single most information-dense file in any modern project
- **README** — the first 2,000 characters; tells us "what" and "why" in the developer's own words
- **Repo topics** — free GitHub tags often include `fastapi`, `machine-learning`, `terraform`, etc.
- **Dockerfile / workflow files** — signals deployment practices and CI discipline

We do **not** read source code files for the lightweight scan. The dependency manifest and README together give us 90% of what we need.

### Noise reduction first

Not every public repository is meaningful signal. Before enriching anything, we filter:

- **Forks** — excluded unless the user has significant commits (tracked in metadata)
- **Archived repos** — excluded
- **Inactive repos** — no pushes in 2+ years are deprioritized (configurable)
- **Boilerplate repos** — single-file repos, `create-react-app` defaults, tutorial clones; detectable by shallow structure

The user sees the filtered list and makes the final call on what's included.

### Chunks, not summaries

Each meaningful signal from a repo is stored as its own structured unit — not collapsed into a single freeform summary. This means:
- `detected_stack` — specific frameworks and tools (not just language)
- `readme_summary` — 2–3 sentence synthesis of what the project does and why
- `project_domain` — inferred business/product domain (e.g. "developer tooling", "data pipeline", "e-commerce")
- `confidence` — how confident the extraction was (low confidence = sparse README + no manifest)

Keeping these structured enables the tailoring generator to selectively pull the right evidence for the right job requirement, rather than dumping an unstructured blob into the prompt.

---

## Rate Limits & Authentication Strategy

### Phase 1 — GitHub App Installation Token

Unauthenticated GitHub API calls are limited to **60 requests/hour per IP**. At 10–15 calls per repo, two concurrent users scanning 5 repos each will hit the ceiling immediately. This is not viable for a live webapp.

A Personal Access Token (PAT) is not the right solution here either. A PAT is tied to an individual GitHub account — every API request would be logged as that person, and the rate limit bucket is shared with their personal GitHub usage. This is the wrong architecture for a platform.

**Solution: Register Tailord as a GitHub App with an Installation Access Token.**

The GitHub App is an independent actor (Tailord, not Charles). Authentication flow:

1. Tailord signs a short-lived JWT using its App ID + RSA private key (RS256)
2. Exchanges that JWT for an Installation Access Token via `POST /app/installations/{id}/access_tokens`
3. Uses the Installation Access Token for all API calls (valid 1 hour; cached and refreshed automatically)

Properties:
- All calls are made by the **Tailord application** as an independent identity — not tied to any individual
- Limit: **5,000 requests/hour** (scales to 12,500 for large installations)
- No user OAuth required — no "Log in with GitHub" friction for end users
- User provides just their GitHub username; Tailord fetches the rest
- Estimated capacity: ~65 concurrent users/hour at 5 repos each
- Private key lives in Azure Key Vault — never in the codebase

The GitHub App requests **read-only access to repository contents and metadata only**. This is clearly disclosed to users.

### Phase 2 — User Access Tokens (when scaling)

When the shared 5,000 request budget becomes a bottleneck, we shift to per-user tokens:

- User authorizes "Tailord GitHub App" (a brief OAuth step — not "Log in with GitHub")
- Each user gets their own 5,000-request bucket
- Capacity becomes effectively **per-user**, not shared across the platform
- Still scoped to public repos only — we keep the privacy promise

The scope language at authorization time: *"Tailord requests read-only access to your public repositories. We cannot see private code or make changes to your account."*

This transition requires minimal backend change — the token source changes, the API calls don't.

### Caching

Popular open-source repos (e.g. `fastapi`, `react`) should never be re-fetched. Before hitting the GitHub API, check if we already have an enriched record for `{owner}/{repo}` with a `last_pushed_at` that matches the repo metadata. Serve from cache if present. This alone reduces API usage significantly during testing and for power users who update their GitHub selection frequently.

---

## Lightweight Scan Architecture

### What we fetch (per repo)

| Source | API Call | Signal |
|--------|----------|--------|
| Repo metadata | `GET /repos/{owner}/{repo}` | Language, stars, topics, archived, pushed_at, fork status |
| Language breakdown | `GET /repos/{owner}/{repo}/languages` | Byte-weighted language distribution |
| Topics | `GET /repos/{owner}/{repo}/topics` | Developer-tagged stack descriptors |
| README | `GET /repos/{owner}/{repo}/readme` | Project intent, domain, architecture description |
| `package.json` | Contents API | JS/TS framework + dependency signal |
| `pyproject.toml` or `requirements.txt` | Contents API | Python stack signal |
| `go.mod` | Contents API | Go module signal |
| `Dockerfile` | Contents API | Containerization + deployment signal |
| First workflow file | `GET /repos/{owner}/{repo}/contents/.github/workflows` + first file | CI discipline signal |

Total: ~10–15 API calls per repo. Cap at **top 20 repos by `pushed_at`** (configurable).

### LLM enrichment pass

One LLM call per repo, after all file content is fetched:

**Input:** repo metadata + language stats + topics + README excerpt + manifest contents
**Output (structured):**
```json
{
  "readme_summary": "2–3 sentence synthesis of what the project does and why",
  "detected_stack": ["FastAPI", "SQLAlchemy", "PostgreSQL", "Docker", "GitHub Actions"],
  "project_domain": "developer tooling",
  "confidence": "high | medium | low"
}
```

Low confidence is surfaced to the user — they can decide whether to include the repo as a signal.

### DB schema

New `github_repo_details` JSON column on `experiences` — additive, backward-compatible with existing `github_repos` (which stores basic metadata from the initial GitHub scan).

Structure:
```json
{
  "enriched_at": "2026-04-14T12:00:00Z",
  "repos": [
    {
      "name": "tailord",
      "owner": "dunbarchara",
      "url": "https://github.com/dunbarchara/tailord",
      "readme_summary": "...",
      "detected_stack": ["Next.js", "FastAPI", "PostgreSQL", "Azure"],
      "project_domain": "productivity tooling",
      "confidence": "high",
      "language_breakdown": {"TypeScript": 0.62, "Python": 0.31, "HCL": 0.07},
      "topics": ["nextjs", "fastapi", "azure"],
      "stars": 12,
      "last_pushed_at": "2026-04-13"
    }
  ]
}
```

---

## User Flow

### Phase 1 UX

1. User enters GitHub username in the Experience page
2. Tailord fetches the user's public repos and displays a filtered list (forks/archived/inactive removed)
3. User selects which repos to include as signals
4. For multi-contributor repos: user sees an acknowledgement — "We'll treat this repo as representative of your engineering work"
5. User clicks "Scan" — enrichment runs as a background task
6. Progress shown via polling (same pattern as resume processing)
7. Enriched repo cards displayed: detected stack badges, README summary, confidence indicator

### What "Deep Scan" means (future)

The lightweight scan deliberately avoids commit history and per-contributor attribution. A future "Deep Scan" tier would:
- Fetch commit history filtered by username
- Analyze PR descriptions and associated diffs
- Source specific contributions ("Implemented the caching layer" from a real PR)
- Provide actual attribution evidence in multi-contributor repos

Deep Scan is a paid feature in the product model — it requires more API calls, LLM time, and storage. The lightweight scan is sufficient for MVP.

---

## Implementation Plan

### Day 6 — Backend + Frontend ✅

- [x] Register "Tailord Local" GitHub App; `.pem` stored outside repo; App ID, Installation ID, key path in `backend/.env`
- [x] `GitHubClient` — JWT (RS256) → Installation Token exchange; process-wide singleton; `get_user_repos()`, `get_languages()`, `get_topics()`, `get_readme()`, `get_manifests()`, `get_first_workflow()`
- [x] Repo filter: exclude forks, archived, inactive > 2 years; cap at top 20 by `pushed_at`
- [x] `github_enrichment.py` prompt + structured output (`readme_summary`, `detected_stack`, `project_domain`, `confidence`)
- [x] `github_enricher.py` — background enrichment pipeline; accepts `repo_names` filter for selective enrichment; logs request count and errors
- [x] `POST /experience/github` — accepts `selected_repo_names`, filters stored repos, triggers enrichment as `BackgroundTask`; all GitHub calls use `GitHubClient` (authenticated); `mvp_github.py` deleted
- [x] `github_repo_details` JSON column on `experiences` + Alembic migration `d1e2f3a4b5c6`
- [x] Two-step connect UI in `ExperienceManager`: (1) username → "Fetch Repos"; (2) checkbox list → "Connect (N repos)"
- [x] `ParsedProfile` GitHub tab — enriched cards (summary, stack, domain, languages, topics, confidence) when enrichment complete; "pending" fallback otherwise
- [x] `GET /api/experience/github/[username]/repos` Next.js dynamic route added (was missing)
- [x] `GitHubEnrichedRepo`, `GitHubRepoDetails` types added to `frontend/src/types/index.ts`
- [x] Verified end-to-end with local LLM: single-repo selection → enrichment → enriched data visible in profile tab

### Day 7 — Race Condition Fix + Homepage

- [ ] Race condition fix: `POST /experience/github` must not overwrite `status = processing`
- [ ] `experience_processor.py` — targeted column updates to avoid clobbering concurrent GitHub writes
- [ ] Homepage `ProductPreview` — replace mockup with real screenshot
- [ ] "Re-scan GitHub" button for stale `github_repo_details`

---

## What We Are Not Building (Yet)

| Item | Reason |
|------|--------|
| Commit history analysis | Deep Scan tier — more API calls, per-contributor attribution logic, higher LLM cost |
| Private repo access | Adds OAuth complexity and privacy surface; public-only is the right MVP scope |
| Vector embeddings of repo content | Needs evidence extraction architecture first; pgvector is a future milestone |
| Per-PR diff analysis | Part of Deep Scan; current chunk scoring doesn't yet consume evidence at that granularity |
| Repo freshness webhooks | Nice-to-have; caching + user-triggered re-scan is sufficient for now |
| GitHub org scanning | User's personal repos are the signal; org repos raise attribution questions |

---

## Open Questions

1. **Acknowledgement UX for multi-contributor repos:** How explicit should this be? A checkbox per repo, or a single acknowledgement at the start of the scan flow?

2. **Confidence threshold:** Should we exclude "low confidence" repos from tailoring generation automatically, or let the user decide?

3. **Re-scan trigger:** Should the system automatically re-scan if a repo was last enriched more than N days ago? Or always user-triggered?

4. **GitHub App installation friction:** The GitHub App installation flow requires the user to visit GitHub and click "Install." How do we minimize drop-off at this step? (Phase 2 concern, but worth designing around early.)

---

## GitHub Apps

**Tailord Local**

*Internal development/testing instance for Tailord. If you are a public user, please visit tailord.app for the production version.*

Developmental version of the Tailord enrichment engine. Used for identifying technical skills and project domains from public repository metadata to support automated candidacy arguments.
