# Surface 02 — GitHub Scan

**`source_type`:** `github`
**Status:** Live (basic scan); deeper 6-pillar scan is planned
**Acquisition:** GitHub OAuth → API scan → LLM extraction per repo

---

## 1. What It Captures

GitHub scan derives professional claims from a user's public (and optionally private) repositories. The current pipeline reads repo metadata (name, language, stars, description, README summary) and produces:

- **Project chunks**: one per repo — an LLM-generated description of what the repo does and why it matters
- **Skill chunks**: one per detected stack item (language, framework, tool)

The planned deep crawl extends this to:

- Architecture signals (directory structure, module boundaries)
- Observability and reliability practices (logging patterns, error handling, health checks)
- Security practices (auth patterns, dependency management)
- DX and CI/CD (test coverage, pipeline definitions, deployment config)
- Usability signals (API design, documentation quality)

These map to a **6-pillar scan**: Observability, Security, Reliability, DX/CD, Architecture, Usability.

---

## 2. Metadata to Store

| Field | Value |
|---|---|
| `source_type` | `github` |
| `source_ref` | `repo_name` (e.g., `"tailord"`) — enables per-repo delete |
| `claim_type` | `project` for the repo description chunk; `skill` for stack items |
| `group_key` | `repo_name` — groups project + skill chunks under the same repo heading |
| `date_range` | null for current implementation; planned: repo active date range from commit history |
| `technologies` | Detected stack items (mirrors `skill` chunks for the same repo) |
| `confidence` | `low` for stack inferred from README/file extensions; `medium` for claims supported by README content |
| `chunk_metadata` | `{llm_model: "...", extraction_date: "...", scanned_at: "..."}` |
| `source_urls` | `[repo_url]` — repo root URL; see Source URL Strategy below |

The `scanned_at` timestamp on the connector record enables refresh cadence tracking. Repos are not re-scanned on every app load — re-scan is triggered on user request or when `scanned_at` is stale (> 30 days).

---

## 3. Source URL Strategy

GitHub deep file links go stale as the repo evolves (files move, rename, delete). The recommended approach:

- **Primary**: store the repo root URL as `source_urls[0]` — e.g., `https://github.com/username/repo`
- **Semantic about blurb**: store the repo description or LLM-generated summary in `chunk_metadata.about` — this is a durable, human-readable summary that lets a reviewer understand the repo without following a link
- **Deep file links**: store at scan time in `chunk_metadata.scan_evidence` as best-effort — e.g., specific file paths that support a claim. Treat these as informational, not canonical. If the file moves, the blurb remains accurate.

Do not store volatile deep file paths (e.g., line-anchored links to specific functions) as the primary `source_url`. They will rot quickly. The repo root + semantic blurb is the durable fallback.

---

## 4. Sensitivity Filters

GitHub repos are public by design (or explicitly authorized by the user for private repos). Standard filters:

- Strip contact info if present in README (rare but possible)
- Do not extract internal company names from commit messages (the scan operates on repos, not commit history)
- For private repos: apply the same scrub pass as plugin sources — flag company-identifying internal codenames before showing the review card

Current implementation scans only public repos. Private repo access would require elevated OAuth scope and the review gate described in the plugin docs.

---

## 5. Processing Pipeline

```
1. User connects GitHub via OAuth → access token stored on Experience record
2. POST /experience/github → triggers enrichment background task
3. Background:
   a. Fetch user's repos from GitHub API (filtered by language, stars threshold)
   b. For each repo:
      - Fetch metadata: name, description, language, stars, topics
      - Fetch README content (GET /repos/{owner}/{repo}/readme → base64 decode)
      - Fetch dependency manifests if available (pyproject.toml, package.json, Dockerfile, etc.)
      - Fetch CI/CD config presence (presence of .github/workflows/, .circleci/, etc.)
   c. LLM extraction per repo: PREnrichment model → project description + detected_stack
   d. Create ExperienceChunks: 1 project chunk + N skill chunks per repo
   e. Embed all new chunks (background task)
4. Store github_repos JSON on Experience record (raw scan metadata for future re-processing)
5. Update Experience.extracted_profile["github"] with summary
```

**Existing vs. new chunks**: on re-scan, delete all chunks with `source_type="github"` AND `source_ref=repo_name` before creating new ones (per-repo flush). This avoids duplication on re-scan while preserving chunks from repos that weren't touched.

---

## 6. Dedup and Atomic Decomposition

**Cross-repo skill signals**: if the same technology appears in 5 repos, the current pipeline produces 5 separate `skill` chunks each with `source_ref` pointing to a different repo. These are semantically near-identical.

**Design decision (open):** One skill chunk per canonical technology, or one per repo?

Arguments for one per repo:
- Preserves provenance — shows the user used React in Project A and Project B
- Source deletion (disconnect repo A) only removes that repo's chunk, not all React evidence

Arguments for one per technology:
- Retrieval doesn't benefit from 5 identical "React" chunks — dilutes cosine results
- UI is cleaner for the user

**Recommended approach:** keep one chunk per repo (preserve provenance), but flag cross-repo skill near-duplicates in the periodic compaction pass for user review. Do not auto-merge at ingest. Let the dedup review surface handle consolidation if the user wants it.

---

## 7. Human Approval Gate

None for the current public-repo scan. The user explicitly clicks "Add GitHub" and authorizes the connection — that is their approval of the scan.

For private repos (planned): require a review card before ingestion, showing the extracted claims and the source repo. The user approves before chunks persist.

---

## 8. Backend Entry Points

**Connect GitHub:**
```
POST /experience/github
Request:  { github_username: string }
Response: ExperienceRecord (updated with github_username, triggers background scan)
```

**List repos for selection:**
```
GET /experience/github/{username}/repos
Response: [{ name, description, language, stars, topics }]
```

**Disconnect GitHub:**
```
DELETE /experience/github
Response: ExperienceRecord (github chunks deleted, github_username cleared)
```

---

## 9. Open Questions

1. **Cross-repo skill consolidation**: one skill chunk per technology or per repo? See Dedup section above.

2. **Refresh cadence**: auto-trigger re-scan when the user opens My Experience and `last_synced_at` > 30 days? Or always on-demand? On-demand preferred for v1 (lower infra cost, transparent to user).

3. **Private repo support**: if added, what OAuth scopes are required and how does the review gate integrate into the existing experience page?

4. **6-pillar scan depth**: which pillars are worth the LLM cost per repo? Observability and Reliability signals require deeper file reading than metadata alone. What is the minimum file set that covers 80% of signal quality?

5. **Commit history signals**: should scan include commit frequency, contributors count, or PR merge history? These are engagement signals but risk misrepresenting solo projects vs. team projects.
