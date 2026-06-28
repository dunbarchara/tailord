# 43 — Repository Selector UX for Active Developers

## Problem

Active developers connect 50–200+ repos. A flat checklist is overwhelming and surfaces no signal about which repos represent real work. The current implementation shows all repos in two sections (Enabled / Available) with no prioritisation, search, or bulk tooling.

## Design Direction

### Tri-tier layout

Rather than an alphabetical flat list, surface value first:

1. **Recommended** (top) — pinned repos, most-starred, and most recently pushed. Pre-surfaces their most likely candidates. Source: GitHub API (`/user/repos?sort=pushed`, `/users/{user}/repos` with star count, pinned repos via GraphQL).
2. **All repositories** (middle) — searchable, scrollable remainder.
3. **Organizations** (toggle/dropdown) — active devs often work inside company or community orgs. Needs a switch between "Personal" and each connected org. Requires `read:org` scope or org-level App installation.

### High-density repo rows

Each row should be scannable without opening anything:

- Repo name + public/private badge + primary language colour dot
- Stars, forks, last commit date — lets user instantly spot dead tutorial repos from 2021
- Prominent toggle on the far right

### Power-user efficiency

- **Quick filters**: [All] [Public] [Private] [Sources] [Forks] — instant, no round trip
- **Forks hidden by default** — devs fork dozens of repos just to submit one PR; they almost never want to track those
- **Global search bar** — sticky, filters by name or language as they type
- **Bulk actions** — "Select all visible" paired with filters (e.g. filter TypeScript → Select All → Enable)

### Enabled state persistence in UI

- Enabled rows get a subtle background tint so they're identifiable while scrolling
- "Show only enabled" global toggle at the top — lets the user audit their tracked portfolio without wading through 150 sandbox repos

## API / Data Considerations

- Current `source_data.repos` list is populated by `GET /installation/repositories` (repos the App was granted access to). This is already filtered.
- To support the "Recommended" tier, we need additional metadata per repo: `stargazers_count`, `fork`, `pushed_at`, pinned status.
  - `stargazers_count`, `fork`, `pushed_at` are already present in the raw GitHub repo object — we just need to persist them in `source_data.repos` instead of discarding them during the filter step in `scan_repos_for_installation` / `github_refresh_repos`.
  - Pinned repos require a GitHub GraphQL call (`pinnedItems` on the viewer) — separate fetch, low priority.
- Org support requires either a separate org-level App installation or the `read:org` scope — deferred, but the selector UI should have a placeholder org switcher from the start.

## Implementation Notes

- The current `GitHubConnected` component in `SourcesManager.tsx` is already structured (Enabled / Available sections). The tri-tier and filter layer is a UI enhancement on top of that foundation.
- Recommended tier can be derived client-side from the existing `repos` array using `stargazers_count` + `pushed_at` — no new backend endpoint needed initially.
- Forks are already filtered out server-side in the scanner. If we want to show them as an optional filter, we'd need to persist them in `source_data.repos` with a `fork: true` flag and skip the client-side filter.
- Search is purely client-side; no pagination needed until repo counts exceed ~200.

## Open Questions

- Do we want to show forked repos at all (with a filter to unhide them), or keep the current behaviour of silently dropping them?
- Org support scope: is this a near-term requirement or can it wait until a user requests it?
- Pinned repos via GraphQL — worth adding the extra API call to power the Recommended tier, or use stars + recency as a proxy?
