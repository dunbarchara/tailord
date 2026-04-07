# Adjusted Sprint Plan — 6 Days to Ship-Ready

*Replaces the remaining days in `02-two-week-plan.md` (Days 8.5–12).*

Two phases, clear split:

- **Days A1–A3 — User-facing:** ship everything a real user or hiring manager would see or experience
- **Days P1–P3 — Platform:** harden the foundation once the product surface is stable

---

## Phase 1 — User-Facing (Days A1–A3)

### Day A1 — Streaming + Perceived Performance ✅

**Goal:** The tailoring generation flow feels fast. Users start reading their document within seconds, not after a 60–90 second blank wait.

**Why first:** This is the single highest-leverage UX change available. Wall-clock time is hard to eliminate across four sequential LLM + scrape operations, but perceived time can drop dramatically. Every other user-facing feature lands better if the baseline generation experience doesn't feel broken.

**Approach taken:** Phase list with elapsed timers (Claude Code style) + early redirect, rather than token streaming. Token streaming added backend complexity without meaningful UX gain given the ~10s generation window.

#### 1. SSE stream — scraping + extracting only (early redirect)
- [x] `POST /tailorings` and `POST /tailorings/{id}/regenerate` return `StreamingResponse` (SSE)
- [x] Emit `event: stage` / `data: scraping` and `event: stage` / `data: extracting` as each phase begins
- [x] On extraction complete: create `Job` + `Tailoring` records with `generation_status="generating"`, emit `event: ready` with tailoring ID
- [x] Matching + generation run in a `BackgroundTasks` task (`_finalize_tailoring`), updating `generation_stage` and `generation_started_at` in DB
- [x] Added `generation_status`, `generation_stage`, `generation_error`, `generation_started_at` columns to `Tailoring` + Alembic migration

#### 2. Frontend — phase list + early redirect
- [x] `NewTailoringForm`: phase list with per-phase elapsed timers (scraping, extracting); redirect to `/dashboard/tailorings/{id}` on `event: ready`
- [x] `TailoringDetail`: polls `GET /tailorings/{id}` every 2s while `generation_status === 'generating'`; shows matching/writing phase list with server-side elapsed computed from `generation_started_at`
- [x] 1s tick effect forces elapsed re-renders during background generation
- [x] `JobPosting` tab: contextual loading message when `generationReady === false` or `enrichment_status` is pending/processing

---

### Day A2 — Public Profile Page

**Goal:** Each user has a public portfolio URL they can drop in a bio or application.

**Why second:** The sharing infrastructure (`/t/{slug}`) is already live. The profile page is a lightweight addition that meaningfully expands the product's reach — one URL that surfaces all of a user's public work in context.

#### 1. Data model
- [x] Add `username_slug` column to `users` table (unique, nullable)
  - Auto-generate on user creation from display name (`"Chara Dunbar"` → `"chara-dunbar"`); append number on collision
  - Migration: backfill existing users
- [x] Alembic migration

#### 2. Backend
- [x] `GET /users/public/{username_slug}` endpoint — gated behind `profile_public=True`
  - Returns: `name`, `avatar_url`, `username_slug`, `github_username`, `profile` (extracted resume)
  - Tailorings intentionally excluded — see "Future: Tailorings on profile page" note above
- [x] `profile_public` bool on User (default False) + migration `d7e8f9a0b1c2`
- [x] Extended `ExtractedProfile` schema with `phone`, `location`, `headline`, `title`, `work_experience.location`, `education.location`
- [x] Added `title` field: 2–5 word role (e.g. "Software Engineer"), distinct from `headline`
- [x] Updated LLM extraction prompt to extract all new fields; LLM now generates a summary if none is present in the resume
- [x] `github_username` included in public profile response from `experience.github_username`

#### 3. Frontend
- [x] `/u/[slug]` route — two-pane layout (sticky sidebar + scrollable content), renders summary, work experience, education, skills, certifications, projects, contact
- [x] `/dashboard/profile` — private preview of the public profile with sticky visibility banner (Public/Private status, link to live URL, link to visibility settings)
- [x] Shared `ProfileSidebar` component: name, title, headline, location, social links (LinkedIn, GitHub), animated scroll-based nav (scroll-position threshold with first/last section clamping), back-to-top button
- [x] Section headers: icon + label + divider line; skill group sub-labels (Technical, Soft Skills, Certifications)
- [x] OG and Twitter card meta tags on `/u/[slug]` (`generateMetadata`); description priority: headline → summary excerpt → fallback
- [x] Settings: `profile_public` toggle (Public/Private); profile URL with copy button only shown when enabled
- [x] Link from `/t/{slug}` back to author's profile page
- [x] "Profile" nav item added to dashboard sidebar

#### Future: Tailorings on profile page
Tailorings were intentionally removed from the public profile. The philosophy: the profile surfaces *who you are and what you're capable of*, not your active job search. Showing all targeted companies/roles to any recruiter who visits is a liability for the candidate — it exposes competitive intelligence, signals desperation, and undercuts negotiating position.

When we revisit this, the right model is a **third toggle** per tailoring: `show_on_profile` (distinct from `letter_public` / `posting_public`). This keeps individual sharing opt-in separate from portfolio showcasing, and lets the candidate curate exactly which tailorings (if any) appear on their profile. Left sidebar placement would be preferred over right panel, so they appear above the fold regardless of scroll position.

---

### Day A3 — Polish, Cleanup + Documentation

**Goal:** The product is clean, self-explanatory, and reference-ready.

**Why third:** Before locking in the platform (testing, staging, security), the surface needs to be stable. Dead code makes tests harder to write, and a clear README makes security review faster.

#### 1. Dead code removal
- [ ] Remove legacy backend endpoints: `/parse`, `/generate` (old match endpoint), `/job` (`job.py` — superseded by `tailorings.py`)
- [ ] Remove any dead frontend routes
- [x] Audit `CLAUDE.md` — update file paths and routing table to reflect current state

#### 2. README
- [x] Write `README.md` at repo root (what Tailord is, architecture, local dev, env vars, key concepts, deployment)

#### 3. Portfolio write-up
- [ ] `planning/12-portfolio-writeup.md`:
  - The problem it solves
  - Key technical decisions and why (dual pipeline, streaming, Notion integration, chunk scoring)
  - What I'd do next

#### 4. Minor UX cleanup (opportunistic — only if clearly needed)
- [x] Settings: Notion disconnect error surfaced inline
- [x] Bullets: LLM prompt rule + `_clean_profile()` post-processing strips leading bullet chars at source; frontend band-aid removed
- [x] Bug: GitHub data preserved when resume added after GitHub (`extracted_profile` spread fix)
- [x] Bug: Source-aware remove/replace resume logic — `_has_non_resume_sources()` + `_clear_resume_fields()` helpers
- [x] Bug: `title` field added to `ProfileUpdate` Pydantic model

#### 5. URL structure + username settings
- [x] Tailoring public URL restructured: `/t/{slug}` → `/u/{userSlug}/{tailoringSlug}`
  - `Tailoring.public_slug` global unique constraint dropped; composite unique `(user_id, public_slug)` added
  - Alembic migration `e1f2a3b4c5d6`
  - Backend endpoint `GET /tailorings/public/{slug}` → `GET /tailorings/public/{username_slug}/{tailoring_slug}` (validates user ownership)
  - `GET /tailorings/{id}` response now includes `author_username_slug`
  - Frontend: `/u/[slug]/[tailoringSlug]/` page created; `/t/[slug]/` deleted; API proxy routes updated
  - `TailoringDetail.tsx` share URL updated to `/u/{author_username_slug}/{public_slug}`
- [x] User-settable username in Settings
  - Backend: `username_slug` added to `UserUpdate` with format validation (3–30 chars, `[a-z0-9-]`, no leading/trailing hyphen) + reserved words check + uniqueness enforcement (409 on conflict)
  - Backend: `GET /users/check-username/{slug}` endpoint for availability check
  - Frontend: username section in Settings with debounced availability check, format validation, link-breaking warning, save via `PATCH /api/users`

---

### Day A4 — My Experience Improvements

**Goal:** The experience processing flow feels responsive, and users have control over how their profile is interpreted.

**Why fourth:** The experience pipeline is the foundation everything else builds on — bad or incomplete parsing silently degrades every tailoring. Giving users visibility and edit access turns a black box into something they trust. The timer work is also a direct extension of the perceived-performance pattern established in A1.

#### 1. Processing progress indicator
- [x] Replace the static "Processing…" state in the Experience page with a phase list + elapsed timers (same pattern as tailoring generation)
- [x] Backend: `POST /experience/process` now returns SSE `StreamingResponse` — phases: `extracting` (text extraction), `analyzing` (LLM profile extraction), `ready`
- [x] Frontend: reads SSE stream directly from POST response; shows phase list with per-phase elapsed timers; transitions to parsed view on `ready`; falls back to polling on page reload if SSE gone

#### 2. Parsed profile review and editing
- [x] `EditableResumeProfile` component: editable fields for all resume sections (personal info, work experience with bullets, skills, certifications, education)
- [x] `PATCH /experience/profile` backend endpoint: merges partial update into `extracted_profile.resume`, updates `processed_at`
- [x] Edit/Cancel/Save pattern — explicit save, no auto-save; "Edit" button in Parsed Profile section header
- [x] After saving: "Profile updated — you may want to regenerate tailorings" banner with link to tailorings list

---

### Day A5 — Miscellaneous UX

**Goal:** Targeted user experience improvements directed session by session.

- [x] Settings: Replace profile visibility button with a `Switch` component (state clearly visible at a glance; consistent with tailoring share popover). Confirmation dialog required when enabling public — instant when disabling.
- [x] Settings: Account deletion — "Danger zone" section with confirmation dialog; checkbox acknowledgment required; deletes storage file + tailorings + jobs + experience + user in FK-safe order; signs out and redirects to `/` on success.
- [x] Settings: Custom pronouns — preset chips (she/her, he/him, they/them) + custom free-text option. Pronouns injected into all LLM prompts via `_format_sourced_profile()` as a `[CANDIDATE]` block — single injection point covering tailoring generation, requirement matching, and chunk scoring. Tailoring system prompt updated with explicit pronoun rule; defaults to gender-neutral language if unset.
- [x] Homepage redesign v1 — replaced flat Hero + FeaturesTailord with five discrete section components (HeroSection, ProductPreview, HowItWorks, DifferentiatorSection, ClosingCTA). New headline ("You have the experience. We'll show you how to prove it."), single CTA, stylized product mockup showing Strong/Partial/Gap scoring, differentiator block. See `planning/13-homepage-redesign.md` for iteration plan.
- [x] Job Posting view: personal advocacy blurbs per chunk. `ChunkMatchResult` gains `advocacy_blurb` (populated by LLM for score ≥ 1 using candidate name/pronouns from `[CANDIDATE]` block; null for gaps/n/a). Public/recruiter view renders `advocacy_blurb`; internal Analysis tab surfaces both fields labelled. Migration `a3b4c5d6e7f8` adds column to `job_chunks`.
  - Rationale and advocacy convey the same core argument with different register and audience: rationale is analytical (explains the score, written for internal review); advocacy is advocating (same evidence, written in the candidate's voice for a recruiter).
  - Advocacy respects the score — a partial match reads like a partial. Honest representation of proximity is a platform value: a candid partial makes the strong matches more credible.
  - Advocacy must anchor to specific evidence (role, project, technology, outcome) — generic platitudes without specifics are prohibited by the prompt.

---

### Day A6 — Frontend Rework

**Goal:** Bring the visual design language up to a production-quality standard, closely matching Mintlify's cream + charcoal + sparse green aesthetic.

**Why its own day:** The homepage and dashboard UI were functional but visually underdeveloped — no accent color, flat surfaces, generic typography scale. A polished frontend is essential for the platform to feel credible to real users and recruiters receiving shared tailorings.

#### 1. Homepage redesign v1 ✅
- [x] Replaced flat `Hero` + `FeaturesTailord` components with five discrete section components under `src/components/home/`: `HeroSection`, `ProductPreview`, `HowItWorks`, `DifferentiatorSection`, `ClosingCTA`
- [x] New headline: *"You have the experience. We'll show you how to prove it."*
- [x] Single CTA ("Start your first tailoring") — removed competing secondary CTA
- [x] Subtext rewritten to name the actual output (requirement-by-requirement scoring)
- [x] Step 3 of How It Works rewritten: "See exactly where you fit" replaces vague "Get a clear match narrative"
- [x] Differentiator block: "Built to advocate. Not to inflate." — anti-keyword-stuffing positioning
- [x] Deleted dead code: `Hero.tsx`, `Features.tsx`, `FeaturesTailord.tsx`
- [x] Planning doc `13-homepage-redesign.md` created as living iteration log

#### 2. Accent color system ✅
- [x] Introduced `--color-hp-accent` token family (accent, hover, text, subtle) isolated to the homepage — dashboard unaffected
- [x] `.btn-hp-accent` CSS class for hover-via-CSS (no JS event handlers; keeps section components as server components)
- [x] `ColorSwitcher` component built for preview (Charcoal, Dusty Rose, Muted Green, Slate Blue) — then removed once direction confirmed
- [x] Committed to Mintlify-matched emerald green (`#16A34A` / `#15803D` hover / `#EDFAF3` subtle) pending DevTools confirmation of exact values

#### 3. Accent touchpoints across homepage ✅
- [x] Hero: second headline line renders in accent; radial gradient glow behind hero uses accent-subtle
- [x] ProductPreview: card header background uses accent-subtle; section label in accent
- [x] HowItWorks: step numbers (01, 02, 03) in accent at low opacity — decorative
- [x] DifferentiatorSection: border-left on each point in accent
- [x] ClosingCTA: full section background in accent-subtle; button in accent

#### 4. Design language analysis ✅
- [x] Mintlify homepage fetched and analyzed; gap analysis documented
- [x] Planning docs created: `14-claude-ai-workflows.md`, `15-mintlify-design-match.md`
- [x] Key findings: no brand accent color was the highest-leverage gap; warm neutral palette already close; sparse accent application is the critical implementation constraint

#### 5. Design token + font confirmation ✅
- [x] Gathered Mintlify DevTools CSS variables (`:root` block) — confirmed exact surface, border, and text values
- [x] `--color-surface-base` updated to `#FAFAF9` (exact Mintlify match: `component-sidebar-bg: 250 250 249`)
- [x] `--color-text-tertiary` updated to `#78716C` (exact Mintlify match: `foreground-gray-muted: 120 113 108`)
- [x] Inter confirmed as Mintlify's typeface — added via `next/font/google` with `--font-inter` CSS variable
- [x] Dashboard layout uses system-ui font stack (Mintlify pattern); brand header text specifically uses Inter

#### 6. Dashboard sidebar rework ✅
Full Mintlify sidebar design clone replacing the old `Sidebar.tsx`. See `15-mintlify-design-match.md` for reference analysis.

- [x] Layout: `#FAFAF9` bg, `border-r border-border-subtle`, `h-8` nav items, `rounded-[10px]`, `gap-2` icon/text, `px-2` padding — exact Mintlify geometry
- [x] Custom SVG icons extracted from Mintlify HTML (18×18 viewBox, `stroke="currentColor"`, strokeWidth 1.5): Home, Editor, Workflows, Search, Collapse; Lucide Globe (My Profile) and Plus (New Tailoring) with matching strokeWidth
- [x] Active state: `text-brand-accent` green text + `hover:bg-green-600/5` (`rgba(22,163,74,0.05)` — exact Mintlify hover value) + persistent `bg-black/[0.06]` background to distinguish selected item at rest
- [x] Collapsible sidebar: `transition-[width] duration-200` CSS transition, `60px` collapsed / `240px` expanded; inner div fixed-width prevents content reflow during animation
- [x] Collapsed state: icons-only with `title` tooltips; section header replaced by subtle `h-7` divider; search bar becomes icon-only button that expands sidebar on click and auto-focuses input (200ms delay matches transition)
- [x] Responsive auto-collapse: `window.matchMedia('(max-width: 1023px)')` listener drives `smallScreen` state; `isCollapsed = collapsed || smallScreen`; expand actions (search, `···`, collapse toggle) call `handleExpand()` which clears both states; correctly triggers full collapsed rendering (not just visual clipping)
- [x] Tailorings section: scrollable list with fade-out gradient overlay (`from-surface-base`); `IconWorkflows` icon per item; title + company subtext; "Generating..." fallback when in-progress; hover-reveal trash icon with confirm dialog; search/filter by title or company; `···` expand button in collapsed view
- [x] Active item derived from `usePathname()` — correct on load, refresh, and navigation; no manual state tracking
- [x] Account popover: `DropdownMenu` (Radix portal — not clipped by `overflow-hidden`), `side="top"`; preferred display name fetched from `/api/users` with `preferred-name-changed` event listener; Settings link, dark/light mode toggle via `useTheme()`, red Sign Out
- [x] All hardcoded Mintlify hex values migrated to design tokens (`text-text-primary/secondary/tertiary/disabled`, `bg-surface-base/elevated`, `border-border-subtle`) — sidebar fully respects dark mode
- [x] Fixed `<Link><button>` invalid HTML nesting — nav items are plain styled `<Link>` elements
- [x] Old `Sidebar.tsx` deleted; `SidebarMintlify.tsx` renamed to `Sidebar.tsx` with export renamed to `Sidebar`

#### 7. Dashboard page overhauls ✅

All authenticated dashboard pages redesigned to share a unified Mintlify-matched design language.

**Shared shell pattern** applied to all pages:
- `h-full flex flex-col bg-surface-elevated` outer shell
- `h-12 px-6` topbar with `border-b border-border-subtle`, `font-medium` (500) title — matching `typography-caption-l-medium`
- `flex-1 overflow-y-auto min-h-0` scrollable content area (nested scroll pattern prevents iOS rubber-band pulling the topbar)
- Content max-width `max-w-6xl mx-auto px-6 lg:px-16 pt-12 pb-24`
- Section layout: `divide-y divide-zinc-950/5 dark:divide-white/5 [&>*:first-child]:pt-0`; each section uses `py-8 grid grid-cols-1 lg:grid-cols-8 gap-x-12` (col-span-3 label/description left, col-span-5 controls right) — exact Mintlify Settings/General pattern

**Shared button + input styles** (defined as constants, consistent across all pages):
- `saveBtnCls`: `bg-zinc-950 dark:bg-white text-white dark:text-zinc-950` (primary)
- `outlineBtnCls`: `border border-border-default bg-surface-elevated text-text-secondary hover:...`
- `inputCls`: `rounded-xl border border-border-default bg-surface-elevated px-3 py-2 text-sm hover:border-border-strong focus:border-border-focus focus:ring-2 focus:ring-brand-accent/10`
- `textBtnCls`: `h-8 px-2.5 rounded-[10px] bg-surface-elevated border border-border-default text-text-secondary hover:bg-surface-overlay`
- **Typography fix:** section headers use no explicit font-weight (`font-weight: inherit` from Tailwind preflight = 400); topbars use `font-medium` (500) — matches Mintlify's bare `<h1 class="text-foreground-gray">` rendering

**New Tailoring page** (`NewTailoringForm.tsx`):
- [x] Redesigned with shared shell pattern — `h-12` topbar "New Tailoring", nested scroll
- [x] Single `SettingRow` section: left side "Create Tailoring" (regular weight), right side URL input + phase list + submit
- [x] Mintlify `inputCls` with `pl-9` icon prefix (Link2 icon); primary submit button
- [x] Removed shadcn `Input`, `Button`, `Card` — all replaced with design-token-based primitives

**Settings page** (`SettingsPanel.tsx`):
- [x] Topbar `font-semibold` → `font-medium` to match other pages

**My Profile page** (`/dashboard/profile/page.tsx`):
- [x] Topbar redesigned: `grid grid-cols-[1fr_auto_1fr]` layout, `h-12 px-6 font-medium`, `border-b`
- [x] Share-style popover on right (matches TailoringDetail): Globe/Lock + "Profile" + ChevronDown trigger
- [x] Popover sections: header → URL row (full `origin/u/slug`, copy + external link buttons) → visibility Switch → Settings link
- [x] `window.location.origin` used instead of hardcoded `tailord.app` — correct in local dev (`http://localhost:3000`) and production
- [x] PATCH `/api/users` on Switch toggle with `togglingVisibility` loading state

**My Experience page** (`ExperienceManager.tsx`):
- [x] Full redesign with shared shell pattern: `h-12` topbar "My Experience", three `SettingRow` sections within `divide-y`
- [x] Resume section: idle = dashed drop zone `rounded-2xl border-2 border-dashed`; connected = `CardBox` + `SourceRow` (icon box + name + badge + remove button)
- [x] GitHub section: connected = `CardBox` + `SourceRow` with "Connected" badge + "Change" / "×" buttons; not connected = `CardBox` + form with icon-prefixed input. `githubEditing` boolean state added to fix Change button (was checking `record.github_username` instead of edit state)
- [x] Additional Context section: `textareaCls` textarea + Save button + "Saved" status indicator
- [x] Parsed Profile: full-width section below `border-t border-border-subtle`; Edit / EditableResumeProfile pattern preserved
- [x] `CardBox` local component: `rounded-2xl bg-surface-base p-4`; `SourceRow` / `IconBox` patterns for integration rows
- [x] Bug fix: invalid GitHub username (404) previously saved as connected. Backend `fetch_repos` now raises `ValueError` on 404; `set_github` endpoint catches as `HTTPException(422)`. Frontend already handled `!res.ok` correctly.

**Dashboard Home** (`DashboardHome.tsx` — new unified component):
- [x] Replaces separate `RecentTailorings` + `EmptyState` components; shell matches other pages (`bg-surface-elevated`, nested scroll) but has no topbar — time-aware greeting IS the visual header (matches Mintlify Home pattern)
- [x] Greeting: `"Good morning/afternoon/evening, [firstName]"` — time-aware, `suppressHydrationWarning`, display name resolved server-side
- [x] Display name fetch: `fetchDisplayName()` called in `page.tsx` server component alongside `fetchTailorings()` using `Promise.all` — preferred name (from `/users/me`) resolved at SSR time with fallback to session Google name. No client-side fetch = no name flicker on load. `preferred-name-changed` event listener in `DashboardHome` handles live updates from Settings.
- [x] Empty state: `IconWorkflows` icon (neutral grey, matching sidebar), Add Experience + New Tailoring CTAs
- [x] Tailorings table: `rounded-2xl overflow-hidden border border-border-subtle`, `bg-surface-base` thead, `bg-surface-elevated` rows with `hover:bg-surface-base`. Columns: Role+Company (IconWorkflows icon in `bg-surface-overlay` neutral box — no green accent, consistent with unselected sidebar items), Status badge, Visibility badge (hidden on mobile), Created (relative date + hover chevron)
- [x] `StatusBadge`: ready=green, generating=amber+spinner, error=red, pending=grey (matches `GenerationStatus` type)
- [x] `VisibilityBadge`: `is_public` → Globe green "Public"; else Lock muted "Private"
- [x] Row click: `router.push(/dashboard/tailorings/${t.id})`
- [x] New Tailoring primary button placed next to "Your Tailorings / N tailorings generated" section header (not the greeting row)

#### 8. Analysis tab redesign + TailoringDetail overhaul ✅

**Analysis tab** reworked from an admin debug tool into a candidate-facing "Fit Analysis" view. Architecture documented in `16-tailoring-detail-architecture.md`.

- [x] **`?debug=1` debug tab** — loading a tailoring with `?debug=1` adds a fourth "Debug" tab (after a second `|` divider; only rendered when `isDebug`). Tab renders `DebugPanel` component. The amber "debug" pill in the toolbar remains. Production UI unaffected.
  - `DebugPanel` (`src/components/dashboard/DebugPanel.tsx`): fetches `GET /api/tailorings/{id}/debug` on mount. Sections: model badge; Chunk Analysis (reuses `MatchAnalysis`); Formatted Profile (raw text fed to LLM); Chunk Matching System Prompt; Sample User Message (first batch); Tailoring Generation System Prompt (if present); Full Debug Dump (copies all sections as one block for pasting into a review conversation). Each section has an independent copy button.
  - Backend `GET /tailorings/{id}/debug-info` returns: `model`, `formatted_profile`, `chunk_matching_system_prompt`, `sample_chunk_user_message`, `tailoring_system_prompt`. Constructs sample user message from first 3 chunks using `chunk_prompt.USER_TEMPLATE`.
- [x] **`FitAnalysis` component** (`src/components/dashboard/FitAnalysis.tsx`): flat list in original posting order (no section grouping); header bar with company + role + Strong/Partial/Gap dot-counts; context blurb row with Info icon; `MatchCard` per chunk with vertical colored bar (`w-1 self-stretch rounded-full`), score dot + label, requirement text, advocacy blurb (Strong/Partial only), source tag. Styling matches `ProductPreview` mockup exactly: `rounded-3xl`, `shadow-md`, `text-xs` score labels, `mb-2` requirement margin, `min-h-[2rem]` bar.
- [x] **`fitAnalysisToText()`** export for copy button — preserves original posting order, prefixes each line with `[STRONG]` / `[PARTIAL]` / `[GAP]`.
- [x] **Tab hierarchy** — Analysis is default tab; tab order: Analysis → Posting → Letter. Letter + Posting visually grouped as a joined pill with internal divider, separated from Analysis by a `|` text divider. All tabs use bordered inactive state (matching right-side icon buttons: `bg-surface-elevated border border-border-default`); active state darkens to `bg-surface-overlay border-border-strong`.
- [x] **Scroll reset** — `useRef` + `useEffect` resets `scrollTop` to 0 on tab switch; fixes scroll position bleeding across tabs.
- [x] **`-webkit-font-smoothing: antialiased`** on dashboard layout (was `auto`) — softer, easier-to-read text rendering.

**Public shared page** (`PublicTailoringView.tsx`):
- [x] Tab order flipped: Job Posting is default and first tab; Advocacy Letter is secondary.

**Share menu + Notion export** (`TailoringDetail.tsx`):
- [x] Share menu toggle order: Job Posting before Advocacy Letter.
- [x] Notion export popover row order: Posting before Letter.

**Notion backend** (`notion.py`, `notion_export.py`):
- [x] `chunks_to_notion_markdown` now uses `advocacy_blurb` (candidate-facing, recruiter-appropriate) instead of `match_rationale` (internal LLM scoring rationale) — matches what the public Job Posting view renders on chunk expand.
- [x] Page creation order enforced: when a Letter is the first export into a fresh container, a "Job Posting" stub page is created first (claiming the top Notion sidebar position). When the user later exports Posting, the stub is overwritten via `update_notion_page`. If Posting is exported first, no stub is needed.

#### Remaining — Frontend Rework
- [x] **FitAnalysis — rationale + advocacy per score level** — tiered display: Strong shows advocacy only; Partial shows advocacy + hr divider + rationale (italic, muted, Info icon); Gap shows rationale only (italic, Info icon, no source). Source rendered as plain text with icon-width spacer alignment (Strong/Partial only). HiOutlineSparkles icon on advocacy blurbs.
- [x] **Generation timing + expectation setting** — replaced partial-loading tab interface with a dedicated `GenerationView` that hides the tab bar entirely during generation and enrichment. Tabs are revealed as a complete package only when both are settled. `GenerationView` shows a phase list (Extracting requirements → Matching to your profile → Writing your tailoring → Scoring requirements) with elapsed timer on the running phase, and a heading ("Generating your Tailoring — this could take a minute…"). Toolbar center shows pulsing "Generating…" text; toolbar buttons remain visible but disabled (regen enabled on failure). Sidebar spinner persists through enrichment via deferred `router.refresh()`.
- [ ] **Homepage `ProductPreview`** — still showing stylized mockup. Low priority — revisit once the product surface is stable. See `16-tailoring-detail-architecture.md`.
- ~~Extend accent touchpoints to dashboard primary buttons and inline links~~ — dropped. The charcoal/cream scheme is working well; more green in the dashboard would be counterproductive.

---

## Phase 2 — Platform (Days P1–P3)

### Day P1 — Security Review

**Goal:** Identify and fix vulnerabilities before the product is referenced publicly or used with real user data.

**Threat model:** single-tenant SaaS, authenticated users, LLM pipeline ingesting untrusted content (job URLs, resume text), public endpoints at `/t/{slug}` and `/u/{slug}`.

#### Prompt Injection
- [x] Audit all LLM calls: user-supplied content always in the `user` role, never interpolated into `system` prompt — confirmed across all five prompts (`job_extraction`, `chunk_matching`, `requirement_matching`, `profile_extraction`, `tailoring`); no changes needed
- [x] **Scrape sanitisation** — `extract_markdown_content` already strips `<script>`, `<nav>`, `<form>`, `<footer>`, ATS form elements, and truncates at "Apply" headings. Added: decompose CSS-hidden elements (`display:none`, `visibility:hidden`, `aria-hidden="true"`) before markdownify — these are invisible to humans but were previously extracted verbatim, creating a prompt injection vector. ATS footer boilerplate (EEO, consent paragraphs, legal) is handled downstream by the chunk scorer (`should_render=false`) and does not require a separate pre-filter.
- [x] Cap scraped content length fed to the LLM (e.g., 8k tokens) — added `_MAX_MARKDOWN_CHARS = 32_000` hard cap at the end of `extract_markdown_content`; logs a warning with before/after sizes when truncation fires
- [x] Confirm LLM output is only ever rendered as Markdown, never as raw HTML or executed — confirmed: `AdvocacyLetter.tsx` and `PublicTailoringView.tsx` both use `<ReactMarkdown>`; the three `dangerouslySetInnerHTML` usages in the codebase are for static developer-authored content (schema.org JSON-LD, privacy policy, terms) only

#### Auth & Token Abuse
- [x] **API key exposure:** confirmed — `X-API-Key` never logged (no logging in `auth.py`, `uvicorn.access` silenced), not returned in error responses, not accessible to client JS (`env.ts` uses non-`NEXT_PUBLIC_` env vars, only consumed from server-side API routes)
- [x] **Session abuse:** confirmed — trust chain is `X-API-Key` (server secret shared only with the frontend) + `X-User-Id` (google_sub from NextAuth JWT). A forged `X-User-Id` also requires the API key. Backend has no public ingress. `require_approved_user` adds approval gate. No changes needed.
- [x] **Public slug enumeration:** confirmed — `GET /tailorings/public/{username_slug}/{tailoring_slug}` requires both slugs; `GET /users/public/{username_slug}` does not expose a tailoring list; `GET /tailorings` is auth-gated and user-scoped. Public slugs have a 4-char random suffix (~1.7M combinations per company+title pair).
- [x] **Rate limiting:** implemented via `llm_trigger_log` table (one row per LLM pipeline trigger — separate table required because `last_regenerated_at` on the Tailoring row only records the most recent regen, making 10 rapid regens on one tailoring look like a single event). Three operations covered:
  - `POST /tailorings` (create) + `POST /tailorings/{id}/regenerate`: combined 10/hour per user, checked against `llm_trigger_log`; both log `tailoring_create` / `tailoring_regen` events
  - `POST /experience/process`: 5-minute cooldown per user via `experiences.last_process_requested_at` (single record per user — window counting not needed)
  - `POST /experience/github` and `POST /experience/user-input`: no LLM calls, not rate limited
  - Schema additions: `llm_trigger_log` table, `tailorings.last_regenerated_at` (UI "last refreshed" display), `tailorings.generated_at` (wall-clock completion time, pairs with `generation_started_at`), `experiences.last_process_requested_at`
  - Migration: `a9b8c7d6e5f4_add_llm_rate_limiting_fields`
  - TODO (future): softer approach — warn at 8 triggers, block at 10
- [x] **OAuth state validation:** confirmed — Notion: `notion/route.ts` generates UUID state in httpOnly `sameSite:lax` cookie (5-min TTL), validated in callback before code exchange. Google: NextAuth handles CSRF state automatically.

#### Input Validation
- [x] **SSRF:** `field_validator` on `TailoringCreate.job_url` in `mvp_schemas.py` — requires `http`/`https` scheme; blocks `169.254.169.254` (Azure IMDS) and `168.63.129.16` (Azure wire server) in all environments; blocks `localhost` by name and `127/8`, `::1` loopback ranges in production; blocks RFC 1918 (`10/8`, `172.16/12`, `192.168/16`) and link-local (`169.254/16`, `fc00::/7`) in all environments. `localhost` allowed in `environment=local` for mock page testing (`/mock/job-software-engineer`). HTTP scheme allowed in both environments — Playwright follows redirects, so HTTP→HTTPS upgrades work transparently and blocking HTTP would break legitimate job boards. Known gap: DNS-based SSRF (public hostname resolving to private IP) — mitigate at infra layer via Azure Container App egress policy.
- [x] **File upload type:** confirmed — extension checked against `ALLOWED_EXTENSIONS` in `get_upload_url` before presigned URL is issued; no change needed.
- [x] **File upload size:** 10 MB cap added in `trigger_process` SSE stream after `download_bytes` — yields error event directly (bypasses `_friendly_processing_error` to show exact size in the message). Resumes are typically < 500 KB; 10 MB is a generous ceiling.
- [x] **XSS:** confirmed — `AdvocacyLetter.tsx` and `PublicTailoringView.tsx` use `<ReactMarkdown>`; no `dangerouslySetInnerHTML` on LLM output anywhere.

#### SQL Injection
- [x] Confirm all DB queries go through SQLAlchemy ORM — confirmed: no `sqlalchemy.text()` imports, no `db.execute()` / `session.execute()` calls, no raw SQL f-strings anywhere in `backend/app`. Every query uses ORM methods (`.query()`, `.filter()`, `.get()`, `.count()`).
- [x] Verify alembic migrations — two raw SQL usages, both safe: `sa.text("now()")` is the standard `server_default` pattern (fixed fragment, no user input); `op.execute("UPDATE tailorings SET letter_public = is_public")` is a fully hardcoded one-time data backfill in `b8c9d0e1f2a3`.

#### Secrets & Config
- [x] **Grep for hardcoded secrets:** `grep -rn` across all `.py` and `.ts`/`.tsx` files for API key patterns — **no matches**. Source is clean.
- [x] **`.env` files gitignored and untracked:** Three local `.env` files exist (`infra/providers/azure/.env.prod`, `frontend/.env.local`, `backend/.env`). Root `.gitignore` covers all three (`.env` matches `backend/.env`; `.env.*` matches the other two, including the subdirectory path — confirmed via `git check-ignore`). None are tracked (`git ls-files` returns empty for all three).
- [x] **Azure Key Vault usage:** All production secrets — `database-url`, `api-key`, `storage-connection-string`, `nextauth-secret`, `google-client-id`, `google-client-secret`, `llm-api-key`, `notion-client-id`, `notion-client-secret` — are stored in Key Vault and injected into Container Apps via `key_vault_secret_id` references (not hardcoded plain env vars). Container Apps managed identity (`azurerm_user_assigned_identity.container_apps`) holds `Key Vault Secrets User` RBAC role. Terraform deployer holds `Key Vault Secrets Officer`. No plaintext secret values in `main.tf` env blocks. ✓

#### Cost & Performance
- [x] **Playwright timeouts:** `playwright_helper.py` has two explicit timeouts — `goto(timeout=60s)` for navigation and `wait_for_load_state("networkidle", timeout=10s)` for JS settling. Both are set. Changed `networkidle` to **non-fatal**: many analytics-heavy pages have continuous background XHR that prevent reaching networkidle state, causing the wait to timeout and wrongly surface a 422 to the user even though the page loaded fine. Now wraps `wait_for_load_state` in try/except, logs a warning, and continues to `page.content()` with the already-available DOM. `goto` timeout remains fatal (caught upstream in `_scrape_job_url` as `PlaywrightTimeoutError` → 422). Also reduced networkidle timeout from 30s → 10s (30s was excessive for what is a best-effort wait).
- [x] **N+1 queries:** `list_tailorings` was emitting N extra `SELECT` queries — one per tailoring — to lazy-load `t.job` for the title/company/url fields. Fixed with `options(joinedload(Tailoring.job))` on the list query: one JOIN, one round-trip regardless of list size.
- [x] **LLM token logging:** Already fully implemented in `app/core/llm_utils.py`. Both `llm_parse` and `llm_generate` log `tokens=prompt+completion=total` at INFO level on every call, alongside model, schema/label, finish reason, and wall-clock latency. These log lines are queryable in Azure Monitor / Log Analytics to establish per-operation averages and set cost alert thresholds. No code changes needed. Cost alert threshold: configure an Azure Monitor log alert on `total_tokens > N` in a rolling window once baseline is established from production traffic.

---

### Day P2 — Testing + CI Gate

**Goal:** Merges to `main` are gated by automated tests and security tooling. The test suite covers critical paths; the security layer catches regressions automatically.

---

#### Local — pre-commit hooks

Use the `pre-commit` framework (`.pre-commit-config.yaml` in repo root, contributors run `pre-commit install` once). Runs on every `git commit` locally; also runs in CI as a gate.

- [x] **`gitleaks`** — secret scanning. Blocks commits containing API keys, connection strings, or credentials before they ever leave the machine. This is the highest-value hook: it is the only layer that prevents a secret from entering git history entirely.
- [x] **`ruff`** — Python linting + formatting (replaces flake8, isort, pyupgrade). Fast, zero config needed beyond `pyproject.toml`. Run on `backend/**/*.py`.
- [x] **Standard hooks** (`pre-commit-hooks`): trailing whitespace, end-of-file newlines, YAML/JSON validity. Low noise, high signal.
- [x] **Frontend ESLint** (local hook): runs `npm run lint` in `frontend/`; scoped to `^frontend/.*\.(ts|tsx|js|jsx|mjs)$` so it only fires when frontend files change.
- [x] Exclude `backend/.venv/`, `frontend/.next/`, `infra/**/.terraform/` from all hooks.

---

#### Backend — pytest

- [x] Set up pytest with a real PostgreSQL test database (`app_test`) — `pytest-mock`, `pytest-cov`, `httpx` added as dev deps; `pythonpath = ["."]` and `testpaths = ["tests"]` in `pyproject.toml`
- [x] Unit tests — pure functions: `notion_export.py` (`chunks_to_notion_markdown`, `_escape`, `_strip_links`, `_strip_formatting`), `chunk_display.py` (`is_display_ready`), `tailorings.py` (`_validate_profile`, `_generate_slug`) — 51 tests
- [x] Integration tests — FastAPI `TestClient`: tailoring CRUD, share/unshare, public slug lookup, user CRUD, public profile, auth guards (401/403/422) — 32 tests
- [x] Fixture helpers: `make_user`, `make_job`, `make_tailoring` factories; `conftest.py` split into top-level (no DB) and `integration/conftest.py` (DB engine, schema lifecycle, per-test cleanup via `table.delete()`)
- [ ] Coverage target: 80%+ on `app/api/` and `app/services/` — currently 42% overall; `app/api/users.py` at 78%, `app/api/tailorings.py` at 39%. Remaining gap: SSE streaming, background tasks, Notion export API, experience endpoints — deferred (see below)

**Not done / deferred:**
- Notion export API integration tests (mock Notion API with `responses` or `httpx`) — deferred to a follow-up; requires mocking `requests.Session` calls
- Experience endpoint tests — lower priority; no pure functions, primarily file upload + SSE flow
- SSE streaming tests — complex to test with `TestClient`; background task completion not observable
- `pytest-asyncio` — not needed; `TestClient` handles `async def` routes synchronously

---

#### Frontend — Jest

- [x] Unit tests: `InlineMarkdown` rendering (8 tests), `scoreBarColor` logic (8 tests), `groupBySection` + `groupChunksForAnalysis` filtering (10 tests) — 26 tests total, all passing
- [x] Jest infrastructure: `jest` + `jest-environment-jsdom` + `@testing-library/react` + `@testing-library/jest-dom`; `jest.config.ts` using `next/jest` (SWC transform, auto-reads `@/*` tsconfig paths); `"test"` and `"test:coverage"` scripts added to `package.json`
- [x] `scoreBarColor` and `groupBySection` extracted from `JobPosting.tsx` into `src/lib/chunks.ts` (exported); `groupChunksForAnalysis` (the ChunkAnalysis variant) extracted alongside — both components updated to import from shared module
- [x] Add `eslint-plugin-security` to the existing ESLint setup — catches `eval`, regex DoS, `innerHTML` patterns in TypeScript. `detect-object-injection` disabled globally (fires on all typed bracket-notation access in TypeScript — too many false positives to be actionable).
- [x] ESLint full pass: fixed all warnings/errors surfaced by first `npm run lint` run — escaped apostrophes (`You&apos;ll`), replaced `<img>` with Next.js `<Image>`, removed unused imports, extracted inline components defined during render (`SpinningLoader` in `Sidebar.tsx`), added `// eslint-disable-next-line` with explanatory comments for intentional `exhaustive-deps` omissions in `TailoringDetail.tsx` (polling effects depend on sub-fields only to avoid spurious interval restarts). `npm run lint` now exits clean.
- [ ] `next-test-api-route-handler` — deferred; API routes are thin proxies with no independent logic, testing them means testing the mock more than the route

---

#### GitHub Actions — CI Gate

Single workflow (`.github/workflows/ci.yml`) with parallel jobs, triggering on every PR to `main` and push to `main`.

- [x] **pre-commit job**: runs `pre-commit run --all-files` with `SKIP=eslint-frontend` — covers gitleaks secret scan, ruff lint, and standard hooks. ESLint skipped here; runs as a dedicated step in the frontend job.
- [x] **Backend job** (parallel):
  - `uv run ruff check backend/` — lint gate
  - `uv run bandit -r app/ -ll -q` — Python SAST. Fixed two real issues it surfaced: `requests.post` (notion OAuth) and `requests.get` (GitHub API) had no timeout — added `timeout=15` and `timeout=10` respectively.
  - `uv run pip-audit` — dependency CVE scan against `uv.lock`
  - `uv run pytest` — test suite with real PostgreSQL service container (`postgres:16-alpine`); `app_test` DB created via psql before test run
  - `bandit[toml]` and `pip-audit` added to `[dependency-groups] dev` in `pyproject.toml`
- [x] **Frontend job** (parallel):
  - `npm run lint` — ESLint including `eslint-plugin-security` rules
  - `npm run build` — type-check + Next.js compile; dummy `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `API_BASE_URL`, `API_KEY` provided as env vars (Next.js validates them at build time)
  - `npm test -- --ci` — Jest in non-interactive mode
  - `npm audit --audit-level=high` — dependency CVE scan, high+ severity only
- [x] **Infra job** (parallel): `checkov -d infra/providers/azure/ --framework terraform --compact --quiet` — runs on every PR (Checkov is fast; job-level path filtering not supported natively in GitHub Actions)
- [x] Cache: `astral-sh/setup-uv@v5` with `enable-cache: true` (uv store); `actions/setup-node@v4` with `cache: npm`
- [ ] Branch protection rule on `main`: require all CI jobs to pass before merge — **GitHub UI setting, not a file change. Go to repo Settings → Branches → Add rule for `main`, check "Require status checks to pass" and select: `pre-commit`, `backend`, `frontend`, `infra`.**

---

#### Dependabot

- [x] Add `.github/dependabot.yml` — enables automated PRs for outdated/vulnerable dependencies:
  - `npm` ecosystem → `frontend/`, weekly Monday
  - `pip` ecosystem → `backend/`, weekly Monday
  - `github-actions` ecosystem → `.github/workflows/`, weekly Monday
- [x] Dependabot PRs are gated by the same CI workflow — they only land if tests + security scans pass

---

#### Container scanning (deploy workflow)

- [x] Add **Trivy** image scan to `.github/workflows/deploy-azure.yml` — `aquasecurity/trivy-action@v0.35.0` runs after each `docker build`, before `docker push`. Build+push steps split into three separate steps (build → scan → push) for both frontend and backend images.
- [x] `--exit-code 1 --severity CRITICAL` — only blocks on critical, avoids noise from informational findings

---

#### Not doing (and why)

- **Semgrep / CodeQL**: CodeQL requires GitHub Advanced Security (paid for private repos). Semgrep is broader but requires rule tuning to avoid noise. Bandit + eslint-plugin-security covers our actual attack surface with zero tuning.
- **Snyk**: SaaS-dependent, paid tier for private repos. Dependabot + pip-audit + npm audit covers dependency scanning natively.
- **Path-filtered CI** (`on.push.paths`): useful at scale; for Tailord's repo size, running all jobs on every PR is fast enough and simpler to reason about. Revisit if CI time grows past 5 min.

---

### Day P3 — Staging Environment + Pipeline Hardening

**Goal:** A staging environment exists with near-zero idle cost. Remaining pipeline robustness gaps are closed.

#### Staging — Azure Container Apps Revisions
- [ ] Create a `staging` revision alongside `prod` within the same Container App
  - `staging`: min replicas = 0, max = 1 — scales to zero when not in use (zero idle cost)
  - `prod`: min replicas = 1 (always on)
  - `staging` receives 0% external traffic but is accessible at its revision-specific URL
- [ ] Deployment workflow update (`.github/workflows/deploy-azure.yml`):
  - On merge to `main`: deploy image → activate `staging` revision → smoke test (`/health` 200) → promote to `prod`
  - On manual trigger or tag: deploy directly to `prod`
- [ ] Staging database: use same DB with clearly-labelled staging data (Option C from P3 notes) — simplest for a solo project; revisit if data bleed becomes a concern
- [ ] Cloudflare: route `staging.tailord.app` → staging revision FQDN via proxied CNAME
- [ ] `ENVIRONMENT=staging` env var for more verbose logging in staging

#### Pipeline Hardening (remaining from Day 8.5)
- [ ] **Token budget cap:** `truncate_to_tokens(text, max_tokens)` helper (tiktoken) — apply to scraped job markdown before any LLM prompt. Prevents runaway costs and context length errors on unusually long postings.
- [ ] **Job URL caching:** skip Playwright scrape + job extraction LLM for recently-seen URLs (< 7 days); rerun all other LLM steps fresh. Implement once extraction quality feels stable enough to trust cached output.
- [ ] **Profile formatting as compact prose:** replace the raw JSON profile dump fed to the LLM with a compact prose block — more natural context, better performance on smaller models.
- [ ] **Prompt minimisation — chunk matching:** trim `chunk_matching.py` system prompt. Cut to 3–4 examples (from 7); make examples shorter; tighten rules. Each added rule or example competes for the model's attention — the prompt should teach *reasoning patterns*, not enumerate domain-specific exceptions. See `18-scoring-reliability.md`.
- [ ] **Reduce chunk batch size:** lower from ~8–10 chunks per batch to 3–5. More calls, smaller context per call, errors isolated. No architecture change required.
- [ ] **Evidence extraction architecture (experimental):** decompose chunk matching into two sequential phases: (1) one call that reads the candidate profile and extracts a flat list of explicit atomic evidence claims; (2) scoring calls that match requirement chunks against the evidence list rather than the raw profile. The evidence list is smaller, auditable, and structurally prevents inferred claims (e.g. "No Terraform" is explicit — the model cannot invent it). Validate against eval baseline before committing. See `18-scoring-reliability.md` for full tradeoff analysis.
- [ ] **Prompt iteration:** review and tighten `generate_tailoring` system prompt; consider few-shot examples for profile extraction.
- [ ] **LLM response validation + retry:** after each `llm_parse` call, assert that the response meets minimum content expectations before committing the result. Retry the full LLM request (up to 2 additional attempts) on validation failure before falling back. Validation rules to implement per call site:
  - **Chunk matching (`chunk_matcher.py`):** for each `ChunkMatchResult` with `score >= 1`, assert `advocacy_blurb` is non-null and non-empty. A batch where all scored chunks lack advocacy blurbs should be treated as a failed response and retried — this is the known failure mode where the LLM silently omits advocacy statements entirely.
  - **Tailoring generation (`tailoring_generator.py`):** assert output is non-empty and exceeds a minimum character threshold (e.g., 200 chars).
  - **Profile extraction (`profile_extractor.py`):** assert `summary` is non-empty and `work_experience` list is non-empty (or absent from resume — distinguish "no work history" from "extraction failure").
  - **Requirement matching (`requirement_matcher.py`):** assert at least one `RequirementMatch` result is returned.
  - Implement as a shared `llm_parse_with_retry(client, ..., validate_fn, max_retries=2)` wrapper around `llm_parse`, or as inline retry loops per call site — prefer the wrapper to avoid duplicating retry logic.

---

### Debug + Eval Pipeline (graduated roadmap)

The `?debug=1` tab is Level 0 — a manual, per-tailoring inspection tool. The roadmap below builds toward automated quality measurement. Not user-facing; belongs in the platform phase alongside testing and hardening.

**Level 1 — Metadata fields on `Tailoring` model** *(low effort, high payoff)*
- Add `model_name` (string), `generation_duration_ms` (int), `chunk_batch_count` (int), `chunk_error_count` (int) columns to `Tailoring`
- Populate during `_finalize_tailoring`: record the model used, wall-clock time from `generation_started_at` to complete, number of LLM batches dispatched, and how many resulted in parse errors
- Surface in the Debug tab's model badge row (timing + batch stats) — no new UI needed beyond what the tab already shows
- These fields make it possible to correlate model version, generation time, and error rate across tailorings without pulling log files

**Level 2 — Profile snapshot on `Tailoring`** *(medium effort)*
- Store a `profile_snapshot` JSON column on `Tailoring` at generation time: the exact `formatted_profile` string (or structured dict) sent to the LLM
- Motivation: `Experience` is mutable — users edit it after tailorings are generated. The debug tab currently reconstructs the profile from the *current* experience, which may differ from what was used at generation time. A snapshot makes the debug view accurate and enables "what would change if I regenerated now?" comparisons.
- Also enables future diff views between profile versions.

**Level 3 — Debug log table** *(deferred, feature-flagged)*
- A `tailoring_debug_logs` table: one row per generation run, storing `chunk_batch_payloads` (JSON), `chunk_batch_responses` (JSON), `llm_call_log` (sequence of model/prompt/response triples)
- Gate behind a `DEBUG_LOGGING_ENABLED` env flag — off by default in production due to storage cost and PII in resume content
- Enable selectively for specific users (add `debug_logging` flag to `User` model) or for local dev
- This is the foundation for the eval pipeline (Level 4)

**Level 4 — Eval pipeline** *(longer term)*
- Build a test set of (job URL, profile) pairs with human-labeled expected chunk scores and advocacy blurb quality ratings
- Eval runner: re-runs chunk matching on the test set using the current prompt + model, computes agreement with human labels (exact match, off-by-one tolerance)
- Diff view: side-by-side comparison of two runs (e.g., prompt change A vs B, or model X vs Y) — highlight chunks where scores diverged
- CI integration: run eval on PR when `prompts/chunk_matching.py` changes; fail (or warn) if agreement drops below threshold
- This closes the loop on prompt iteration: changes to scoring rules or examples become measurable rather than anecdotal

---

## Phase 3 — Block-Based Persistence (Architectural Evolution)

**Philosophy:** Persist composable units — chunks, advocacy statements, experience bullets — rather than rendered blobs. Each block is independently addressable, reusable across surfaces, and a natural unit for future editing, vector embedding, and semantic retrieval. The job chunk model has already validated this pattern; the goal is to extend it to the rest of the platform.

**Backwards compatibility stance:** There are no real users. Existing tailorings are retained for historical comparison only. Prefer simple, clean solutions over backwards-compatible ones. When a fallback is trivial to add, add it; when it requires meaningful complexity, don't.

See `18-scoring-reliability.md` for the broader context on block-based persistence and vector embedding direction.

---

### Step 1 — `structured_output` on `Tailoring` *(prerequisite for Step 2)*

**Goal:** Decouple the LLM-generated substance (advocacy statements, closing) from the rendered presentation (greeting, footer, formatting). Enable template iteration without LLM regeneration.

**What changes:**

Add `structured_output` (JSONB, nullable) to the `Tailoring` model:

```python
# backend/app/models/database.py
structured_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

Stored shape mirrors `TailoringContent`:

```json
{
  "advocacy_statements": [
    { "header": "Five years of platform-scale infrastructure ownership", "body": "...", "sources": ["Resume"] },
    { "header": "Self-serve infrastructure at scale", "body": "...", "sources": ["Resume"] }
  ],
  "closing": "Charles brings the infrastructure depth and operational track record..."
}
```

**Generation change (`tailoring_generator.py`):** `generate_tailoring()` returns both the rendered string and the structured content. Or split into `generate_tailoring_content()` → `TailoringContent` and `render_tailoring()` → `str`, with the caller responsible for saving both.

**Serve-time change:** The GET `/tailorings/{id}` endpoint renders from `structured_output` when present, falls back to `generated_output` for any existing tailorings that predate this change:

```python
if tailoring.structured_output:
    output = render_tailoring(tailoring.structured_output, ...)
else:
    output = tailoring.generated_output  # pre-migration tailorings
```

**What this immediately unlocks:**
- Greeting and footer template changes apply to all future tailorings without regeneration
- `generated_output` becomes a deprecated field — still present but no longer the source of truth for new tailorings
- Alembic migration: single nullable column addition, no data migration required

---

### Step 2 — Individual `AdvocacyStatement` records

**Goal:** Make advocacy statements first-class DB records. Enables independent rendering across all surfaces (letter, analysis, Notion, public posting), future per-statement editing/regeneration, and in-app approval flows.

**New table:**

```python
class AdvocacyStatement(Base):
    __tablename__ = "advocacy_statements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tailoring_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tailorings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int]            # display order, 0-indexed
    header: Mapped[str]              # bold section header in the letter
    body: Mapped[str]                # 2-4 sentence advocacy body
    sources: Mapped[list[str]] = mapped_column(JSON)  # ["Resume"], ["GitHub"], ["Resume", "Direct Input"]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

**Relationship on `Tailoring`:**

```python
advocacy_statements: Mapped[list["AdvocacyStatement"]] = relationship(
    "AdvocacyStatement", back_populates="tailoring",
    order_by="AdvocacyStatement.position", cascade="all, delete-orphan"
)
```

**Generation change:** After the LLM call, write each `TailoringContent.advocacy_statements[i]` as an `AdvocacyStatement` record. `structured_output` (Step 1) and `AdvocacyStatement` records are written together — they describe the same content at different granularities.

**Serve-time change:** Letter render assembles from `AdvocacyStatement` records joined on `tailoring_id`, ordered by `position`. Falls back to `structured_output` render or `generated_output` for pre-migration tailorings.

**What this unlocks beyond Step 1:**
- Analysis view can join chunks to advocacy statements (same chunk → same requirement → same advocacy statement)
- Notion export queries statement records directly, no markdown parsing
- Per-statement regeneration: "regenerate just this section" without touching the rest
- Per-statement editing: user can refine wording in-app
- Approval flow: mark statements as approved/flagged before sharing
- Chunk `advocacy_blurb` and the corresponding `AdvocacyStatement.body` can be linked — same claim, two granularities (chunk-level one-liner vs. letter-level 2-4 sentences)

**Alembic migration:** new table, no destructive changes. Existing tailorings have no `AdvocacyStatement` records — serve-time fallback handles them.

---

### Step 3 — Individual experience bullet records *(deferred)*

Store each work experience bullet, skill entry, and education entry as an individual record on `Experience` rather than inside a JSON blob. This is the prerequisite for vector embedding (embed each bullet independently at processing time) and for the conversational enrichment vision (add evidence to specific bullets via direct input). Schema and timing TBD once Steps 1–2 are stable.

---

## Summary

| Day | Phase | Focus | Key output |
|-----|-------|-------|-----------|
| A1 ✅ | User | Streaming + perceived performance | SSE stage events, early redirect, phase timers, background generation with DB polling |
| A2 ✅ | User | Public profile page | `/u/{slug}` two-pane layout, experience rendering, `profile_public` opt-in, Settings toggle |
| A3 | User | Polish, cleanup, docs | Dead code removed, README, portfolio write-up |
| A4 ✅ | User | My Experience improvements | SSE phase list during processing, `EditableResumeProfile`, `PATCH /experience/profile`, stale tailoring banner |
| A5 ✅ | User | Miscellaneous UX | Profile visibility switch, account deletion, custom pronouns, homepage redesign v1, job chunk advocacy blurbs |
| A6 ✅ | User | Frontend rework | Homepage redesign, accent color system, Mintlify design match, full dashboard UI overhaul (sidebar, New Tailoring, Settings, My Profile, My Experience, Home); Analysis tab redesign (FitAnalysis, debug mode, tab hierarchy, scroll reset); public page tab order flip; Notion advocacy_blurb + page ordering; `?debug=1` Debug tab (DebugPanel, backend debug-info endpoint, per-section copy buttons, Full Debug Dump) |
| P1 | Platform | Security review | Prompt injection, auth/token abuse, SSRF, rate limiting, secrets audit |
| P2 | Platform | Testing + CI gate | pytest, Jest, GitHub Actions PR gate |
| P3 | Platform | Staging + pipeline hardening | Azure revision-based staging, token budget cap, URL caching, prompt iteration |
