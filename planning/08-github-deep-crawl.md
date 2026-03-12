# GitHub Deep Crawl — Full Work Day

## Goal

Move GitHub from a surface-level metadata source (repo name, language, stars, description, pushed_at) to a genuine experience signal by crawling meaningful content from each repo. The richer the GitHub data, the more accurately the platform can match candidates to job requirements — particularly for open-source contributions, specific frameworks/tools, and depth of technical work.

## Current State

The GitHub integration imports repo metadata via the GitHub API (`GET /users/{username}/repos`). What it does NOT do:
- Read any file content within repos
- Infer tech stack beyond the `language` field
- Understand what the repo actually does or what problems it solves
- Detect notable files (README, CLAUDE.md, package.json, requirements.txt, etc.)

This means a candidate with 30 repos demonstrating deep expertise in exactly the right stack looks identical to one with 30 empty repos. The chunk enrichment pipeline scores "open-source contributions" as Gap for everyone without manual direct input.

## Proposed Approach: Selective File Crawl

Rather than cloning repos or ingesting full codebases, crawl a targeted set of high-signal files per repo using the GitHub Contents API. This is rate-limit friendly, fast, and extracts the most context-dense content.

### Priority file targets (in order)

| File | Signal |
|---|---|
| `README.md` | Project description, tech stack, usage, motivation |
| `CLAUDE.md` | Detailed technical context, architecture, stack decisions |
| `package.json` | Exact frontend/backend dependencies and frameworks |
| `pyproject.toml` / `requirements.txt` | Python stack |
| `go.mod` | Go dependencies |
| `Cargo.toml` | Rust dependencies |
| `docker-compose.yml` / `Dockerfile` | Infrastructure/deployment approach |
| `.github/workflows/*.yml` (first match) | CI/CD, testing, deployment pipeline |

### Per-repo enrichment output

For each repo, produce a compact structured summary:
```json
{
  "name": "repo-name",
  "description": "...",
  "language": "TypeScript",
  "star_count": 12,
  "topics": ["kubernetes", "devops"],
  "readme_summary": "...",
  "detected_stack": ["React", "Next.js", "PostgreSQL", "Docker"],
  "notable_files": ["package.json", "Dockerfile", "README.md"]
}
```

The `readme_summary` and `detected_stack` fields are LLM-generated from the crawled file contents.

## Architecture Considerations

### GitHub API rate limits
- Authenticated: 5,000 requests/hour per token
- Each repo crawl = 1 request per file checked + 1 for the Contents listing
- For a user with 30 repos checking 5 files each: ~180 requests — well within limits
- Use the user's GitHub username (already stored) — no OAuth token needed for public repos

### What to crawl
- Only public repos
- Skip archived repos (configurable)
- Skip repos with no commits in the last 2 years (configurable staleness threshold)
- Cap at top N repos by pushed_at (e.g. top 20 most recently active)

### LLM pass
After crawling, a single LLM call per repo (or batched) extracts:
- A 2–3 sentence plain-language description of what the repo does
- The tech stack (specific frameworks and tools, not just language)
- Any notable engineering patterns (CI/CD, testing, infrastructure, etc.)

This can run as a background task, same pattern as `enrich_job_chunks`.

### Storage
Extend the `experiences` table or add a `github_repo_details` JSON column containing the enriched per-repo data. Keep backward-compatible with the existing `github_repos` field (repo metadata list).

## Impact on Matching

With enriched GitHub data:
- "Open-source contributions" chunks score based on actual repo content, not absence of data
- Framework-specific requirements (React, FastAPI, Terraform) can be matched against detected stacks
- The candidate fact sheet can include "GitHub stack signals" as a distinct block alongside resume skills
- Users get a more accurate picture of how their GitHub presence reads to the platform

## Future: Contributor Analysis

Beyond own repos, crawling contribution history to other repos (PRs merged, issues closed) would surface genuine open-source collaboration signal. Lower priority — requires more GitHub API surface area and storage, but worth noting as a follow-on.

## Estimated Work

- GitHub Contents API integration + file crawl: 2–3 hours
- LLM enrichment pass (per-repo summary + stack detection): 2 hours
- DB schema + Alembic migration: 30 min
- Frontend: surface enriched repo data in ParsedProfile GitHub tab: 1–2 hours
- Testing across diverse repo types: 1 hour
