# Public Experience Search

## What it is

An opt-in searchable index of a user's experience claims surfaced on their public profile (`/u/[slug]`). Visitors — recruiters, collaborators, hiring managers — can type a keyword and get back the specific bullets, skills, and projects that match, without reading the entire profile. Think of it as a deep portfolio search: "show me everything this person has done with Kubernetes" rather than "here is their resume."

This is the logical extension of Tailord as a continuous experience repository. The resume export and tailoring features generate point-in-time outputs for specific jobs; the public experience search lets the repository itself be navigable.

---

## Privacy model

Privacy must be opt-in at every layer and the user must understand what they are exposing.

**Gate 1 — Profile visibility**: already exists. `UserProfile.profile_public = true` is required. No search is possible on a private profile.

**Gate 2 — Claims search opt-in**: a separate boolean, e.g. `UserProfile.claims_search_public`. Toggled in Settings. Defaults to `false` even when `profile_public = true`. This prevents existing public profiles from suddenly becoming searchable on deploy.

**Why two gates**: a user may want a public profile (others can read their summary, tailorings, etc.) but not want their raw claim content indexed and searchable. Separating the gates respects that.

**Claim-level visibility** (future): per-claim `public` flag to exclude specific bullets (e.g. confidential client work, NDA'd projects, personal notes). Phase 1 exposes all `status="active"` claims for opted-in users — no per-claim exclusions. Phase 2 adds a `claims_public` boolean column on `ExperienceClaim` (default `true`) so users can hide individual claims without archiving them.

**What's exposed**: claim `content` only. No internal IDs, no `provenance_metadata`, no gap-response labels, no `source_ref` beyond what the user already shows publicly. The source type badge (`[resume]`, `[github: repo]`) is fine since the user has already opted in.

**Rate limiting**: unauthenticated search should be rate-limited by IP to prevent scraping the entire claim corpus. Suggested: 30 req/min per IP, `429` with `Retry-After`.

---

## Search implementation

### Phase 1 — String/trigram search (ship first)

PostgreSQL `pg_trgm` extension (`CREATE EXTENSION IF NOT EXISTS pg_trgm`) with a GIN index on `experience_claims.content`. Enables `ILIKE '%query%'` with index support.

```sql
-- Migration
CREATE INDEX CONCURRENTLY idx_experience_claims_content_trgm
    ON experience_claims USING GIN (content gin_trgm_ops)
    WHERE status = 'active';
```

Query: `WHERE user_id = :uid AND status = 'active' AND content ILIKE '%' || :q || '%'`

Simple, no embedding required, works with existing claim data.

### Phase 2 — Semantic search (future)

Use `ExperienceClaim.embedding` (already populated for vector-mode users). `GET /users/public/{slug}/claims?q=react+performance` embeds the query and returns top-K by cosine distance. Falls back to trigram search if embedding is null.

Semantic search dramatically improves recall ("fast API" matching "high-throughput service") but requires a call to the embedding model per search request — fine for authenticated users, should be behind a session gate or higher rate limit for unauthenticated visitors.

---

## API

```
GET /users/public/{slug}/claims?q={query}&limit=20&types=work_experience,skill,project
```

- Returns only for `profile_public = true AND claims_search_public = true`
- `types` filter optional; defaults to all claim types
- Results: `[{content, claim_type, group_name, source_type}]` — group_name is the role/project name from the associated `ExperienceGroup` for context
- No pagination in Phase 1 (cap at 50 results); add cursor pagination in Phase 2
- Returns `403` (not `404`) when profile exists but search is not enabled — prevents enumeration of whether a user exists

Next.js API route: `GET /api/users/public/[slug]/claims` — proxy via `proxyToBackend` (no auth header needed; backend enforces public gate).

---

## UI

On `/u/[slug]`, below the existing profile header and tailorings section, when `claims_search_public = true`:

```
┌──────────────────────────────────────────────────┐
│  Search experience  [________________________]   │
└──────────────────────────────────────────────────┘

Results for "kubernetes":
  Owned Infrastructure for a globally distributed service of 35+ engineers
  and 40+ microservices running on AKS (Kubernetes) clusters.
  Microsoft · Software Engineer II  [resume]

  Architected multi-tenant AKS cluster configuration using Helm + Istio for
  blue/green deployment across 3 regions.
  Tailord · Founder  [github: tailord]
```

- Debounced input (300ms), no submit button
- Result cards: claim content, role/project name as subtitle, source badge
- Empty state: "No results for '{query}'" — not "0 results found"
- No search = no results shown (not a browse-all — that would be a separate feature)
- Loading: skeleton rows during fetch

---

## Settings UI

Under `/dashboard/settings` (or `/dashboard/profile`), in the visibility section:

```
Public profile         [toggle — existing]
├── Experience search  [toggle — new, indented under public profile]
│   "Let visitors search your experience claims by keyword.
│    Only available when your profile is public."
```

The experience search toggle is disabled (greyed, tooltip) when `profile_public = false`. Enabling it shows a brief callout: "Your experience content will be searchable by anyone who visits your profile."

---

## Data model changes

| Change | Notes |
|--------|-------|
| `UserProfile.claims_search_public` (bool, default false) | New column, migration required |
| `ExperienceClaim.claims_public` (bool, default true) | Phase 2 only — per-claim opt-out |
| GIN trigram index on `experience_claims.content` | Migration; `CONCURRENTLY` so no table lock |

---

## Open questions

- **Group context in results**: should results show the group name (role/company) or just the raw claim? Showing context (Microsoft · SWE II) is more useful but reveals more. Since the user opted in, this is probably fine — but worth a settings option later ("show role context in search results").
- **Skills in search**: skills are short (`"TypeScript"`, `"Kubernetes"`), so trigram search may return too many trivial matches. Consider a minimum query length (3 chars) or skill-specific display (aggregate matching skills into a pill row rather than individual result cards).
- **Authenticated search on own profile**: the user visiting their own `/u/[slug]` while logged in should see search regardless of `claims_search_public` — useful for previewing what will be shown publicly.
- **SEO / indexing**: if `claims_search_public = true`, should we block search engine crawlers from indexing the raw claim content? The profile page already exists and is indexable. Probably no change needed — search engines don't execute JS search queries.
