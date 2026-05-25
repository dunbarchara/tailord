# Surface 04 — Codebase Offline Scan

**`source_type`:** `codebase_scan`
**Status:** Planned
**Acquisition:** CLI tool runs locally → user reviews generated signals doc → uploads structured JSON payload

---

## 1. What It Captures

The GitHub Scan (surface 02) reads repos via the GitHub API — it can see what GitHub exposes: metadata, README, topics, file trees. It cannot see the actual code, local repos that aren't on GitHub, or proprietary codebases that will never be pushed to a public host.

The Codebase Offline Scan fills that gap. A CLI tool runs locally against any directory on the user's machine, reads what it needs without sending code to a server, and produces a structured signals document. The user reviews and redacts that document before uploading it to Tailord.

This surface is particularly valuable for:
- Work done at employers with strict code confidentiality requirements
- Local experiments and side projects not yet committed to GitHub
- Monorepos where the GitHub summary doesn't capture the full scope of contribution
- Legacy codebases where the user has deep expertise but the repo itself is private and unmaintained

---

## 2. What the CLI Scans

The CLI tool reads locally — never sends source code to Tailord or any external service during the scan phase. It produces a signals document from:

| Input | Signal extracted |
|---|---|
| File tree structure | Domain areas (frontend, backend, infra, ML) |
| Dependency manifests (`pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`, etc.) | Technology stack, libraries used |
| Dockerfile, `docker-compose.yml` | Containerization, deployment patterns |
| CI/CD definitions (`.github/workflows/`, `.circleci/`, `Jenkinsfile`) | Automation practices, deployment pipeline |
| Test files and directories | Testing practices, coverage culture |
| Config files (`nginx.conf`, `terraform/`, `k8s/`) | Infrastructure and operations patterns |
| `README.md` if present | Project description, stated goals |

The CLI does **not** read:
- File contents beyond manifests, config files, and README (no `.py`, `.ts`, `.go`, source files)
- `.env` files or any file with credentials patterns in the name
- Files in `.gitignore` (respects the project's own exclusion rules)

This design keeps the scan fast, privacy-safe, and reviewable — the signals doc contains metadata signals only, not code.

---

## 3. Metadata to Store

| Field | Value |
|---|---|
| `source_type` | `codebase_scan` |
| `source_ref` | `repo_remote_url` if detectable from `.git/config`; otherwise a user-supplied project name |
| `claim_type` | `project` for project-level claims; `skill` for stack items |
| `group_key` | Project name (from README h1, directory name, or user-supplied label) |
| `date_range` | From git log if available: first commit date to last commit date |
| `technologies` | Detected from dependency manifests and config files |
| `confidence` | `medium` for project description claims; `low` for stack inferred from file tree alone |
| `chunk_metadata` | `{scan_date: "...", project_path: "...", git_remote: "...", llm_model: "..."}` |
| `source_urls` | null (local scan has no remote URL unless git remote is detected) |

If a git remote URL is detected and matches a repo already connected via GitHub OAuth, `source_ref` should use the same repo name to enable dedup against existing GitHub scan chunks.

---

## 4. Sensitivity Filters

The CLI applies filters before generating the signals document:
- Strip any file paths that match patterns for secrets (`.env`, `secrets.yml`, `credentials.json`)
- Strip internal hostname patterns from config files if detectable (e.g., `*.internal`, `*.corp`)
- Flag company-identifying project names — the CLI prompts the user: "This project appears to be named after an employer or client. Include the name in the signals doc?"

The user sees the full signals document before upload. They can redact any section before submitting.

The upload endpoint receives only the reviewed and approved signals document — never raw code.

---

## 5. Processing Pipeline

```
1. User installs CLI: npm install -g @tailord/cli (or brew, or pip)
2. CLI: tailord scan ./path/to/project --output signals.json
   a. Walk file tree (respecting .gitignore)
   b. Read dependency manifests, config files, Dockerfile, CI definitions, README
   c. Extract: detected_stack, ci_providers, infrastructure_patterns, test_coverage_signal, project_description_candidate
   d. Read git log if available: first_commit_date, last_commit_date, commit_authors (count only, no names)
   e. Apply sensitivity filter (flag secrets patterns, internal hostnames)
   f. Write signals.json
3. CLI: tailord scan --preview signals.json (optional — renders as human-readable summary)
4. User reviews signals.json, redacts anything sensitive
5. CLI: tailord upload signals.json --api-key <personal_api_key>
   OR: user uploads via My Experience → "Upload codebase scan" button
6. POST /experience/codebase-scan (see endpoint below)
7. Backend: LLM extraction pass on the signals doc → ExperienceChunks
8. Review gate: chunks queued for user confirmation before persisting
9. User approves, edits, or rejects in the review card UI
10. Approved chunks embedded and ingested
```

The review gate (step 8–9) is mandatory because the LLM has less rich context than a resume — the signals doc is structured metadata, not natural language experience descriptions. The user should verify the LLM's interpretation before it enters the repository.

---

## 6. GitHub Deduplication

If the project being scanned is also connected via GitHub OAuth (same repo), chunks from both sources will cover overlapping material. Dedup strategy:

- **Match key**: `source_ref` — if the codebase scan's `source_ref` matches the GitHub repo name, treat them as the same entity
- At ingest, check for existing GitHub chunks with matching `source_ref`
- Surface overlapping chunks in the review gate with a notice: "This looks similar to your existing GitHub data for this repo. Keep both, merge, or skip?"
- Never silently merge — route to the dedup review queue

The design goal: the user should not have duplicate chunks for the same repo from two sources. But they might have legitimate reasons to keep both (e.g., the offline scan captured deeper stack detail that the GitHub API didn't see).

---

## 7. Human Approval Gate

**Required.** Two stages:

1. **CLI review** (pre-upload): the user reads and optionally edits the signals document before it leaves their machine. This is the privacy gate.

2. **Ingestion review** (post-upload): the backend's LLM extraction produces candidate chunks, which are queued in the ConnectorEvent review flow. The user approves before chunks persist.

This two-stage review is appropriate because the offline scan may touch sensitive internal codebases. The user needs explicit control at both stages.

---

## 8. Backend Entry Points

**Upload and process (planned):**
```
POST /experience/codebase-scan
Request:  {
  project_name: string,
  git_remote_url?: string,
  detected_stack: string[],
  ci_providers: string[],
  infrastructure_patterns: string[],
  test_coverage_signal: "none" | "present" | "extensive",
  project_description_candidate?: string,
  date_range?: { first_commit: string, last_commit: string },
  readme_excerpt?: string  (first 500 chars of README)
}
Response: { event_id: UUID, review_url: string }
```

**No SSE stream** — the upload is fast (no file processing). Background task runs LLM extraction and creates the ConnectorEvent. User polls or navigates to `review_url`.

---

## 9. Open Questions

1. **CLI distribution**: npm, pip, brew, or binary download? npm has lowest friction for the target user (developers). pip reaches Python-heavy users. Binary download is universal but harder to update.

2. **Auth in CLI**: personal API key passed as `--api-key` flag or stored in `~/.tailord/config`. Key should be a dedicated "CLI token" not the main API key — allows revocation without affecting the main integration.

3. **Repo README depth**: should the CLI read the full README or only the first N characters? Full README is richer but may contain sensitive internal project details.

4. **Commit author count**: the CLI can report how many distinct authors have committed to a repo — this is a collaboration signal ("led a 5-person team") without exposing colleague names. Include?

5. **Re-scan behavior**: if the user scans the same repo twice, how are the two sets of signals reconciled? Same dedup logic as any other source, keyed on `source_ref`. A full re-scan should be treated as a new event in the review queue, not an automatic replacement.
