# Planning 29 — Frontend Refactoring Candidates

A comprehensive audit of the frontend codebase for refactoring opportunities. Items are grouped by category and roughly ordered by impact vs. risk. Nothing here is implemented — this document is the review checkpoint before any work begins.

---

## 1. Duplicated Utility Functions

### 1a. `tailoringLabel()` — defined in 3 files

```
src/components/dashboard/Sidebar.tsx:166
src/components/dashboard/DashboardHome.tsx:21
src/components/dashboard/RecentTailorings.tsx:5
```

All three implementations are identical: derive a display label from a `TailoringListItem` by combining company and role fields. Should be extracted to `src/lib/tailorings.ts` (which already exists and is a natural home for tailoring-related helpers).

### 1b. `formatRelativeDate()` — defined in 3 files

```
src/components/dashboard/DashboardHome.tsx:29
src/components/dashboard/ExperienceManager.tsx:61
src/app/admin/AdminView.tsx:13
```

The `DashboardHome` and `AdminView` versions are essentially identical (format an ISO string as "X days ago" etc.). The `ExperienceManager` version has a slightly different null-handling signature. Should be consolidated into `src/lib/utils.ts` with a consistent nullable-input signature.

**Action:** extract both into their respective lib files; update all three import sites.

---

## 2. Dead Code

### 2a. `ActionCard.tsx`

`src/components/ActionCard.tsx` is imported nowhere in the codebase. It also uses the legacy `gray-50` color token (`hover:bg-gray-50`) which violates the design system. Safe to delete.

### 2b. `ThemeButton.tsx`

`src/components/ThemeButton.tsx` is essentially a stub — one line of content, no meaningful implementation, not imported anywhere. Safe to delete.

### 2c. `(mock)` route group

```
src/app/(mock)/mock/job-software-engineer/page.tsx
src/app/(mock)/mock/job-mid-level-engineer/page.tsx
src/app/(mock)/mock/job-software-engineer-linear/page.tsx
src/app/(mock)/mock/job-staff-engineer/page.tsx
```

These are development fixtures that expose URLs in production. If they're still needed for local development, they should either be guarded by an env flag or moved outside the App Router (e.g. scripts/fixtures/). If they're no longer needed, delete them.

### 2d. `(demo)` route group

```
src/app/(demo)/demo/dashboard/
  layout.tsx
  page.tsx
  experience/page.tsx
  profile/page.tsx
  tailorings/[tailoringId]/page.tsx
```

A full shadow copy of the dashboard. Unclear if actively used or maintained. If it's a demo mode, consider whether it should be gated or replaced with a more maintainable approach (e.g. seeded test account). If unused, delete.

---

## 3. Repeated Inline Button Styles (Design Token Drift)

Across multiple files a CTA button style is duplicated verbatim as a long className string rather than using a shared component or design token:

```
bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 hover:opacity-90 transition-opacity ...
```

This pattern appears in:
- `src/components/dashboard/NewTailoringForm.tsx:49` (defined as `const primaryBtn = '...'`)
- `src/components/dashboard/SettingsPanel.tsx:45`
- `src/components/dashboard/ChunkedProfile.tsx:22`
- `src/components/dashboard/ExperienceManager.tsx:134`
- `src/components/dashboard/DashboardHome.tsx:175,183,209,217`
- `src/app/(demo)/demo/dashboard/profile/page.tsx:230`

The color values (`zinc-950`, `white`) are correct semantically (foreground/background inversion) but are expressed as raw Tailwind colors rather than design tokens. Either:
- Define a `brand-cta` token in `globals.css` and use it via `bg-brand-cta`, or
- Extract a shared `<PrimaryButton>` component wrapping the `shadcn/ui` `<Button>` with the right variant

Whichever approach, the string should not be repeated across 6+ files.

---

## 4. `proxy.ts` Structural Duplication

`src/lib/proxy.ts` has three exported functions (`proxyToBackend`, `proxyToBackendWithUser`, `proxyStreamToBackendWithUser`) that share identical error-parsing logic repeated three times and duplicated header-building logic between the two user-scoped functions.

The error parsing block appears 3× verbatim:
```ts
let errorMessage = res.statusText;
try {
  const errBody = await res.json();
  errorMessage = errBody.detail ?? errBody.message ?? errorMessage;
} catch {}
```

Suggested cleanup:
- Extract `parseErrorBody(res: Response): Promise<string>` as a private helper
- Extract `buildUserHeaders(session, apiKey)` as a private helper shared by the two user-scoped functions

Low risk, no behavior change.

---

## 5. Large Components — Split Candidates

The following components are very large and mix concerns:

### 5a. `ExperienceManager.tsx` (~1100+ lines)

Contains: file upload UI, GitHub connection UI, manual text input UI, inline profile editing, section rendering, computed YoE display, polling logic, and more. Reasonable split candidates:
- `ExperienceUploadSection` — file drop + upload state
- `GitHubSection` — GitHub connect/disconnect + repo list
- `UserInputSection` — free-text input panel
- `ExperienceManager` — orchestration only (state, API calls)

### 5b. `ChunkedProfile.tsx` (~900+ lines)

The profile chunk editor. Contains: chunk list rendering, inline editing for each chunk type (work, education, project), add/delete/reorder actions, and the `MintBtn` local component. The `MintBtn` component defined inline could at minimum be extracted to a shared location or replaced with a properly configured `<Button>` variant.

### 5c. `JobPosting.tsx` (~500+ lines)

Job requirements editor with chunk expand/collapse, inline editing, scoring display. Reasonably self-contained but the `ChunkRow` and `SectionHeader` sub-components defined inline could be module-level or separate files for readability.

### 5d. `TailoringDetail.tsx` (~500+ lines)

Tab orchestration component that delegates to `AnalysisView`, `AdvocacyLetter`, `JobPosting`, `DebugPanel`. Already well-decomposed at the tab level; the main opportunity is the toolbar button cluster which is dense and could be a `<TailoringToolbar>` component.

**Note:** splitting should not be done speculatively. Prioritize files that are actively causing pain (merge conflicts, hard to navigate, hard to test).

---

## 6. Inline Local Components That Should Be Extracted or Promoted

### 6a. `MintBtn` in `ChunkedProfile.tsx:22` and `ExperienceManager.tsx:134`

Both files define their own version of `MintBtn` with identical styling. This is the same duplication problem as §3. One instance or a shared component.

### 6b. `SectionHeader` in `JobPosting.tsx`

Defined inline as a sub-component. Could be a module-level component in the same file (above the main export) or extracted to a `dashboard/` sub-component file if used elsewhere.

---

## 7. Naming

### 7a. `ChunkedProfile.tsx` / `ChunkAnalysis.tsx`

The names are easy to confuse. `ChunkedProfile` is the experience chunk editor (user edits their profile chunks). `ChunkAnalysis` is the job requirement score view. Consider:
- `ChunkedProfile` → `ProfileChunkEditor` or `ExperienceChunkEditor`
- `ChunkAnalysis` → `RequirementAnalysis` or `JobRequirementsView`

### 7b. `ParsedProfile.tsx`

Renders a read-only formatted view of the extracted profile. The name suggests parsing (a process) rather than display. Consider `ProfilePreview` or `ExtractedProfileView`.

### 7c. `InlineMarkdown.tsx`

Good name. No change needed, just noting it is well-named and should remain a stable primitive.

### 7d. `EditableResumeProfile.tsx`

The word "Resume" is a legacy term — the model now uses "Experience" throughout. Consider `EditableExperienceProfile` or just `ExperienceProfileEditor`.

---

## 8. Directory Structure

### 8a. `src/components/` root level

Currently contains: `ActionCard.tsx` (dead), `ThemeButton.tsx` (dead), `ThemeProvider.tsx`, `ClientWrapper.tsx`, `AuthCard.tsx`, `Header.tsx`, `Footer.tsx`, `CTA.tsx`, `UseCases.tsx`.

The `CTA.tsx` and `UseCases.tsx` are marketing-page-specific components sitting at the root alongside truly global components (`ClientWrapper`, `ThemeProvider`). These could move to `src/components/home/` alongside `HeroSection.tsx`, `DifferentiatorSection.tsx`, etc.

### 8b. `src/components/home/` vs `src/app/(marketing)/`

Home page components live in `src/components/home/` but their only consumer is `src/app/(marketing)/` pages. This is a reasonable pattern — no urgent change needed — but worth noting that if the marketing site grows, co-locating these under `src/app/(marketing)/_components/` would be more idiomatic for App Router.

### 8c. `src/app/admin/AdminView.tsx`

The pattern across the codebase is: page files are server components at `app/.../page.tsx` and large client logic is in `src/components/`. `AdminView.tsx` breaks this by being a large client component living inside `app/admin/` rather than `src/components/dashboard/` or `src/components/admin/`. Minor inconsistency, not urgent.

---

## 9. Type Inconsistencies

### 9a. `formatRelativeDate` signature mismatch

`DashboardHome` and `AdminView` versions take `string` (non-nullable). `ExperienceManager` version takes `string | null | undefined`. When consolidated, pick the nullable signature.

### 9b. `ExperienceInput` vs inline form state types

Some components manage form state as plain object literals rather than using the `ExperienceInput` type from `src/types/index.ts`. Audit at consolidation time.

---

## 10. API Route Documentation Gap

`CLAUDE.md` lists the API routes table but it's notably out of date. The actual routes include:
- `api/experience/chunks/` and `api/experience/chunks/[id]/`
- `api/experience/gap-response/`
- `api/experience/user-input/chunks/`
- `api/experience/user-input/parse/`
- `api/tailorings/[id]/chunks/`, `[chunkId]/`, `[chunkId]/rescore/`, `merge/`, `rename-group/`
- `api/tailorings/[id]/gap-answer/`
- `api/tailorings/[id]/refresh/`
- `api/tailorings/[id]/debug/`
- `api/tailorings/public/[userSlug]/[tailoringSlug]/`
- `api/users/check-username/[slug]/`
- `api/health/`

This isn't a code change — it's a CLAUDE.md update that should be done alongside any route work to prevent drift.

---

## 11. Misc Patterns Worth Standardizing

### 11a. Polling with `setInterval` vs. React state machines

`NewTailoringForm` and `ExperienceManager` both implement polling via `setInterval` in `useEffect`. The patterns are slightly different (different cleanup approaches, different error handling). If a third polling scenario arises, extract a `usePolling(fn, intervalMs, enabled)` hook.

### 11b. Inline `cn()` calls with long ternary chains

Several components build className strings with 3–4 levels of nested ternaries. This is readable at 2 levels but becomes error-prone at 4+. No immediate action needed but keep in mind as a smell when touching those files.

### 11c. `divide-y divide-zinc-950/5 dark:divide-white/5` repeated string

This separator pattern appears in `NewTailoringForm.tsx:261`, `SettingsPanel.tsx:389`, `ExperienceManager.tsx:1084,1129`, `AdminView.tsx:192`. Could be a utility class or a `<Divider>` component.

---

## Priority Order (Suggested)

| # | Item | Risk | Impact |
|---|------|------|--------|
| 1 | Extract `tailoringLabel()` to `lib/tailorings.ts` | Low | Eliminates 3× duplication immediately |
| 2 | Extract `formatRelativeDate()` to `lib/utils.ts` | Low | Eliminates 3× duplication immediately |
| 3 | Delete `ActionCard.tsx` + `ThemeButton.tsx` | None | Removes noise |
| 4 | Fix `proxy.ts` duplication | Low | Cleaner shared lib, easier to maintain |
| 5 | Decide on `(mock)` / `(demo)` route groups | Medium | Either gate or delete |
| 6 | Consolidate `MintBtn` / primary button style | Medium | Requires touching 6+ files |
| 7 | Rename `ChunkedProfile`, `ParsedProfile`, `EditableResumeProfile` | Low | Rename + update imports |
| 8 | Update CLAUDE.md API route table | None | Documentation only |
| 9 | Split `ExperienceManager` | High | Large refactor, do last |

Do not do items 6 or 9 speculatively — they should be driven by a concrete reason (feature work, active bugs, test coverage goal).
