# Two-Week Work Plan

*Feb–Mar 2026 | Solo developer sprint*

---

## Guiding Principles for This Sprint

1. **Ship complete features, not half-features.** The GitHub input being UI-only is worse than it not existing. Everything in this sprint should go end-to-end.
2. **Prioritize what makes the product shareable.** Right now it's private-only. A shareable tailoring URL or Notion integration changes the product's reach.
3. **Each day's work should be demonstrable.** If you can't show it to someone at the end of the day, the task was too big.
4. **Portfolio signal matters.** Given the employment context, the Notion integration is week 2's priority over anything else — it's a direct signal for the companies you're targeting.

---

## Week 1: Complete the Core Product

The goal of week 1 is to eliminate every "this feature is half-built" area. By Friday, every visible feature in the UI should actually work.

---

### Day 1 — GitHub Integration (Backend)

**Goal:** When a user provides a GitHub username, fetch their repositories and merge them into the candidate profile.

**Tasks:**
- Add `GET /github/{username}/repos` endpoint to FastAPI that fetches public repos from the GitHub REST API (no auth token needed for public repos)
  - Pull: repo name, description, primary language, star count, last pushed
  - Filter out forks, archived repos, and anything with 0 stars + no description (noise)
  - Return top 10 by recency or stars
- Extend `extract_profile()` in `resume_processor.py` to accept an optional `repos` param
  - The existing `extract_profile` function in `mvp_llm.py` already has a `repos` param — it's just never populated
- Add a `/resume/github` POST endpoint: accepts `github_username`, fetches repos, re-runs profile extraction with resume text + repos combined, updates the Resume record

**Why now:** The data enrichment story depends on this. A Tailoring generated with GitHub context is measurably better — the LLM can reference specific repos.

---

### Day 2 — GitHub Integration (Frontend) + Additional Context

**Goal:** The GitHub and additional context inputs actually save and affect the profile.

**Tasks:**
- Wire the GitHub URL field in `ExperienceManager` to call the new `/api/resume/github` endpoint
  - Show a processing state (similar to resume upload poll loop)
  - Update the displayed profile summary when complete
- Wire the "Additional Context" textarea to `POST /resume/additional-context` (new endpoint)
  - This appends a block of free text to the resume text before re-running extraction
  - Simple: store in the Resume record as `additional_context` column, include in extraction prompt
- Add database migration: `additional_context TEXT` column on `resumes` table
- Visual feedback: after saving GitHub or additional context, show "Profile updated" toast

**Why now:** This completes the experience section. Once done, the entire left side of the product vision (experience capture) is finished.

---

### Day 3 — Tailoring Regeneration + Delete

**Goal:** A tailoring is not a dead end. Users can regenerate it and delete ones they don't want.

**Tasks:**
- Add `POST /tailorings/{id}/regenerate` backend endpoint
  - Re-runs `generate_tailoring()` with the same `job_id` and current user resume
  - Creates a new Tailoring record (keeps the old one for history) — or optionally replaces it (simpler)
  - Decision: replace is simpler for MVP; keep history is more correct. **Go with replace for now.**
- Add `DELETE /tailorings/{id}` backend endpoint
  - Deletes the Tailoring and Job records for that tailoring
- Add frontend API routes for both
- In `TailoringDetail`: add "Regenerate" button with confirmation (it overwrites)
  - Show loading state — regeneration takes 15–25 sec
  - On complete, reload the tailoring content
- In the Sidebar tailoring list: add a delete action (small trash icon, confirm dialog)

**Why now:** Without regeneration, every bad output is a permanent failure. This is basic product completeness.

---

### Day 4 — Shareable Tailoring URLs

**Goal:** A tailoring can be made public and shared via a URL that doesn't require login.

**Tasks:**
- Add `is_public` boolean + `public_slug` (short unique string) columns to `tailorings` table
  - Generate slug from `{company-slug}-{title-slug}-{random-4chars}` — readable and unique
- Add backend endpoint: `GET /tailorings/public/{slug}` — no auth required, returns tailoring data
- Add "Share" button in `TailoringDetail`:
  - First click: prompts "Make this tailoring public?" (confirm)
  - Enables public access, shows shareable URL, copy-to-clipboard
  - Toggle to make private again
- Add frontend public route: `/t/{slug}` — renders the tailoring without requiring login
  - Clean, print-friendly layout — just the header and document
  - Shows "Generated with Tailord" link at the bottom (passive marketing)

**Why now:** Shareable URLs unlock multiple things at once — you can share your own work, users can share their tailorings with hiring managers, and it creates organic discovery.

---

### Day 5 — Polish, Error States, Loading States

**Goal:** The product feels complete, not like a prototype. No dead ends, no blank screens.

**Tasks:**
- Review every async operation and ensure proper loading states exist
- Review every error path:
  - Scrape failure (URL unreachable, blocked by Cloudflare) → clear user message
  - LLM JSON parse failure → clear user message, suggest retry
  - Resume processing failure → show error state in experience section, offer re-upload
- Add a processing timeout on tailoring creation (currently no timeout — can hang forever)
  - Set a 90-second timeout on the Playwright + LLM calls combined
  - Return 408/504 with a clear message if exceeded
- Improve the empty state: when no tailorings exist, show a mini onboarding flow
  - Step 1: "Upload your resume" with a link to `/dashboard/experience`
  - Step 2: "Paste a job URL" — links to `/dashboard/tailorings/new`
  - Step indicator showing where they are
- Audit the tailoring list in the sidebar: ensure title + company always show (fallback to URL if missing)

---

## Week 2: Notion Integration + Strategic Feature

Week 2's goal is to build the one feature that most clearly demonstrates product sophistication and directly signals relevant skills for the companies you want to work at.

---

### Day 6 — Notion OAuth Setup + Settings Page

**Goal:** Users can connect their Notion workspace to Tailord.

**Tasks:**
- Register Tailord as a Notion OAuth app at [notion.so/my-integrations](https://www.notion.so/my-integrations)
  - Callback URL: `{NEXTAUTH_URL}/api/auth/notion/callback`
- Add Notion OAuth flow:
  - New NextAuth provider OR a standalone OAuth handler (simpler: standalone)
  - `/api/auth/notion` — redirects to Notion OAuth
  - `/api/auth/notion/callback` — exchanges code for access token, stores in DB
- Add `notion_access_token TEXT` + `notion_bot_id TEXT` columns to `users` table
- In `SettingsPanel`: add "Connected Apps" section
  - "Connect Notion" button → initiates OAuth
  - Shows connected state (workspace name) once linked
  - "Disconnect" button

**Note on Notion OAuth:** Notion uses OAuth 2.0. The access token is scoped to the pages/databases the user explicitly shares with your integration. This is actually a cleaner model than full workspace access.

---

### Day 7 — Notion Page Creation

**Goal:** A user can export any tailoring directly to a Notion page with one click.

**Tasks:**
- Add `POST /tailorings/{id}/export/notion` backend endpoint:
  - Requires user to have a Notion access token
  - Uses Notion API `POST /v1/pages` to create a new page
  - Parent: a page/database the user selects (or a default "Tailord Exports" page created automatically)
  - Content: parse the generated Markdown → Notion block format
    - `#` headings → `heading_1` blocks
    - `##` headings → `heading_2` blocks
    - Paragraphs → `paragraph` blocks
    - `*italic*` / `**bold**` → inline annotations
    - Bullet lists → `bulleted_list_item` blocks
  - Return the created page URL
- Frontend: "Export to Notion" button in `TailoringDetail`
  - If Notion not connected: prompt to connect (link to settings)
  - If connected: click → loading → opens created Notion page in new tab
  - Show success toast with link

**Markdown → Notion blocks is the hard part.** The Notion API doesn't accept markdown directly. You'll need a conversion function. There are open-source libraries (`md-to-notion`, `martian`) but given the project constraint of minimal dependencies, consider writing a targeted converter for just the headings/paragraphs/bullets/bold/italic that the tailoring template produces — it's a finite set of elements.

---

### Day 8 — Notion Parent Page Selection + Polish

**Goal:** The Notion integration feels polished, not janky.

**Tasks:**
- After Notion OAuth, fetch the user's accessible pages via `GET /v1/search`
  - Filter to pages only (not databases)
  - Store a default export location preference in the user record
- In Settings: "Notion Export Location" — a dropdown of their accessible pages
  - Saves their preferred parent page for future exports
- Add a `notion_page_url TEXT` column to `tailorings` table
  - Once exported, show the Notion page URL permanently in the tailoring detail
  - "View in Notion" button alongside "Copy" and "View Posting"
- Handle token expiry: Notion tokens don't expire, but if the user revokes access, handle the 401 gracefully with a prompt to reconnect

---

### Day 9 — Public Profile / Tailoring Portfolio Page

**Goal:** Each user has a public portfolio page that lists their public tailorings.

**Tasks:**
- Add `/u/{username_slug}` frontend route — public, no auth required
  - Derive username slug from Google display name on first login, stored on User
  - Shows: user name, avatar (from Google), list of public tailorings (role + company)
  - Each tailoring links to `/t/{slug}`
- This is a lightweight but impactful addition: it gives users a URL they can put in a bio or LinkedIn
- Add `username_slug` column to `users` table with unique constraint
  - Auto-generate on user creation from name (e.g., "Chara Dunbar" → "chara-dunbar")
  - If collision, append a number
- In Settings: allow the user to see and copy their public profile URL

**Why this matters for the employment search:** A user's Tailord portfolio page shows *targeted, role-specific documents* — not a generic resume. Sharing `tailord.app/u/chara-dunbar` in an application is itself a signal of craft and product thinking.

---

### Day 10 — Documentation, Portfolio Write-Up, Cleanup

**Goal:** The project is polished enough to reference directly in applications. Legacy code is removed.

**Tasks:**
- Remove dead backend endpoints: `/parse`, `/generate` (the legacy match endpoint), `/job` (job.py — functionality now lives in tailorings.py)
- Remove dead frontend routes if any remain
- Write a clear, concise `README.md` at the repo root:
  - What Tailord is (one paragraph)
  - How to run it locally (dev commands from CLAUDE.md)
  - Architecture overview (brief)
  - Screenshots of the main UI states
- Update `CLAUDE.md` to reflect any new routes/files added this sprint
- Take 3–4 good screenshots of the product for portfolio use
- Write a 3-paragraph product case study (can go in README or a separate `/planning/portfolio-write-up.md`):
  - The problem it solves
  - Key technical decisions and why
  - What you'd do next

---

## Day-by-Day Summary

| Day | Focus | Output |
|-----|-------|--------|
| 1 | GitHub backend | `/resume/github` endpoint, repo fetching |
| 2 | GitHub + context frontend | Experience section fully functional |
| 3 | Regenerate + Delete | Tailoring lifecycle complete |
| 4 | Sharing | Public tailoring URLs at `/t/{slug}` |
| 5 | Polish | Error states, loading states, onboarding flow |
| 6 | Notion OAuth | Connect/disconnect Notion from Settings |
| 7 | Notion export | One-click export, Markdown→Notion blocks |
| 8 | Notion polish | Parent page selection, stored export URL |
| 9 | Public portfolio | `/u/{slug}` page with public tailorings |
| 10 | Documentation + cleanup | README, remove legacy code, screenshots |

---

## What to Cut If Time Is Short

If any day runs long, cut in this order (least to most impactful to cut):

1. Additional context textarea backend (Day 2) — cut this, it's the lowest signal feature
2. Public portfolio page (Day 9) — nice to have, not essential
3. Notion parent page selection (Day 8) — auto-create a default "Tailord Exports" page instead
4. Tailoring delete (Day 3) — keep regeneration, cut delete
5. Never cut: GitHub backend (Day 1), Notion export (Day 7), shareable URLs (Day 4)

---

## What Not to Build in This Sprint

- PDF export — too much scope for the value it adds; Notion export is better
- Team/sharing features — solo user tool for now
- A mobile app — the web product needs to be complete first
- Pricing / paywall — premature for portfolio purposes
- Re-engineering the LLM pipeline — the current one works; don't over-optimize
