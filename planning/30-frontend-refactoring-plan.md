# Planning 30 — Frontend Refactoring Implementation Plan

Derived from `planning/29-frontend-refactoring-candidates.md` with clarifications:
- `(mock)` routes are intentional dev fixtures — no action
- `(demo)` routes serve the public `/demo/dashboard` and must stay, but the profile page has a significant duplication problem (see §4)
- ExperienceManager upload section is named `ResumeUploadSection`

Items are ordered by dependency and risk. Each item is independently shippable.

---

## Item 1 — Delete dead components ✓

**Scope:** 2 file deletions + grep to confirm no imports exist.

**Files:**
- [x] Deleted `src/components/ActionCard.tsx` — confirmed no external imports; used legacy `gray-50` token
- [x] Deleted `src/components/ThemeButton.tsx` — confirmed no external imports; was an empty stub
- [x] Also deleted `src/components/CTA.tsx` and `src/components/UseCases.tsx` (Items 1 + 8 collapsed — both were unreferenced dead code; CTA referenced non-existent `/signup` + `/pricing` routes)

**Verify first:** `grep -r "ActionCard\|ThemeButton" src/` should return zero results outside the files themselves.

**Risk:** None. Neither is imported anywhere.

---

## Item 2 — Extract `tailoringLabel()` to `lib/tailorings.ts` ✓

**Scope:** Add one export to `lib/tailorings.ts`; remove local definitions and update imports in 3 files.

**Current state:** Defined identically in:
- `src/components/dashboard/Sidebar.tsx:166`
- `src/components/dashboard/DashboardHome.tsx:21`
- `src/components/dashboard/RecentTailorings.tsx:5`

**End state:**
```ts
// src/lib/tailorings.ts
export function tailoringLabel(t: TailoringListItem): string { ... }
```
All three files import from `@/lib/tailorings`. Local definitions removed.

- [x] Implemented as planned — but then moved to `lib/utils.ts` post-hoc (see deviation note)
- **Deviation:** `tailorings.ts` imports `env` at module level; `Sidebar.tsx` is a client component. Importing `tailorings.ts` from a client context caused a browser crash (`Missing required env var: API_BASE_URL`). Fixed by relocating `tailoringLabel` to `lib/utils.ts` (no `env` dependency). All three import sites updated to `@/lib/utils`.

**Risk:** Low. Pure rename-and-import; no behavior change.

---

## Item 3 — Extract `formatRelativeDate()` to `lib/utils.ts` ✓

**Scope:** Add one export to `lib/utils.ts`; remove local definitions and update imports in 3 files.

**Current state:** Defined in:
- `src/components/dashboard/DashboardHome.tsx:29` — takes `string` (non-nullable)
- `src/app/admin/AdminView.tsx:13` — takes `string` (non-nullable), same impl
- `src/components/dashboard/ExperienceManager.tsx:61` — takes `string | null | undefined`, returns `string | null`

**End state:** Consolidated with the nullable signature (superset):
```ts
// src/lib/utils.ts
export function formatRelativeDate(iso: string | null | undefined): string | null { ... }
```
All three call sites updated. Where callers previously passed a non-nullable `string`, the broader signature is fully compatible.

- [x] Implemented as planned — nullable superset signature adopted; all 3 call sites updated

**Risk:** Low. The nullable → non-nullable widening is safe at all call sites.

---

## Item 4 — Fix `proxy.ts` duplication ✓

**Scope:** Internal refactor of `src/lib/proxy.ts` only. No other files change.

**Current duplication:**
1. Error detail parsing — 3× identical block extracting `detail` from a text response
2. User header building — 2× identical block constructing `X-User-Id`, `X-User-Email`, `X-User-Name`, `X-User-Image` in `proxyToBackendWithUser` and `proxyStreamToBackendWithUser`

**End state:** Two private helpers at the top of the file:

```ts
function parseErrorDetail(text: string): string {
  try {
    const parsed = JSON.parse(text);
    if (typeof parsed?.detail === 'string') return parsed.detail;
  } catch {}
  return text;
}

function buildUserHeaders(user: UserContext, correlationId: string): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-API-Key': env.apiKey,
    'X-User-Id': user.userId,
    'X-User-Email': user.userEmail,
    'X-Correlation-Id': correlationId,
  };
  if (user.userName) headers['X-User-Name'] = user.userName;
  if (user.userImage) headers['X-User-Image'] = user.userImage;
  return headers;
}
```

All three exported functions call `parseErrorDetail`; both user-scoped functions call `buildUserHeaders`. Public API and behavior unchanged.

- [x] Implemented as planned — `parseErrorDetail` and `buildUserHeaders` extracted; all 3 exported functions updated

**Risk:** Very low. File-internal refactor with identical observable behavior.

---

## Item 5 — Extract shared profile section components ✓

**Background:** `src/app/(dashboard)/dashboard/profile/page.tsx` defines these section components locally:

- `SectionHeader` (icon + label + horizontal rule)
- `ExperienceSection`
- `EducationSection`
- `SkillsSection` (technical, soft, certifications)
- `ProjectsSection`
- `ContactSection` (email + phone)
- `SkillGroupLabel`

`src/app/(demo)/demo/dashboard/profile/page.tsx` is a hand-rolled copy of the same layout, but it is **already diverged**:
- Missing `SkillGroupLabel` — renders skills categories without the label subcomponent
- Missing `SkillsSection.certifications` — certifications are silently dropped
- Missing `ContactSection` for phone — only renders email via a simplified inline block
- Has its own version of `textBtnCls` (slightly different — no hover states, disabled-only)

This means the demo profile will silently show less data than the real profile for the same mock user, and future additions to the real profile sections will not appear in demo.

**Scope:** Extract section components to a shared module; update both profile pages to import from it.

**New file:** `src/components/profile/ProfileSections.tsx`

Exports:
```ts
export function SectionHeader({ icon, label }: { icon: LucideIcon; label: string })
export function ExperienceSection({ jobs }: { jobs: ExtractedProfile['work_experience'] })
export function EducationSection({ education }: { education: ExtractedProfile['education'] })
export function SkillsSection({ skills, certifications }: { ... })
export function ProjectsSection({ projects }: { projects: ExtractedProfile['projects'] })
export function ContactSection({ email, phone }: { email?: string | null; phone?: string | null })
```

**`dashboard/profile/page.tsx`:** Remove the local definitions; import from `@/components/profile/ProfileSections`. The page body does not change.

**`demo/dashboard/profile/page.tsx`:** Replace the entire inline section-rendering block with the same shared components. The demo will now correctly render certifications, phone, and any future additions automatically. The demo-specific parts (the sign-up prompt CTA and the read-only `textBtnCls` toolbar button) remain in the demo page file.

- [x] Created `src/components/profile/ProfileSections.tsx` — 206 lines, exports `SectionHeader`, `ExperienceSection`, `EducationSection`, `SkillsSection`, `ProjectsSection`, `ContactSection`
- [x] `dashboard/profile/page.tsx` updated — removed ~180 lines of local section definitions; now imports from `ProfileSections`
- [x] `demo/dashboard/profile/page.tsx` updated — replaced ~200 lines of hand-rolled inline rendering; demo now has full parity (certifications, phone, `SkillGroupLabel` all present); `hasContact` nav section added

**Risk:** Medium. Touches two files and creates a new shared module. The real profile page behavior must be verified to be pixel-identical after extraction. The demo profile will render slightly more content than before (certifications, phone if present in mock data) — that's correct behavior, not a regression.

---

## Item 6 — Consolidate primary button style ✓ (partial)

**Background:** The filled CTA button style (`bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 hover:opacity-90 ...`) is repeated as a raw string constant in 6 files. It uses raw Tailwind color names rather than design tokens, making theme changes require edits in 6 places.

**Files affected:**
- `src/components/dashboard/NewTailoringForm.tsx:49` (`primaryBtn` const)
- `src/components/dashboard/SettingsPanel.tsx:45`
- `src/components/dashboard/ChunkedProfile.tsx:22` (`MintBtn` local component)
- `src/components/dashboard/ExperienceManager.tsx:134` (`MintBtn` local component — duplicate of ChunkedProfile's)
- `src/components/dashboard/DashboardHome.tsx:175,183,209,217`
- `src/app/(demo)/demo/dashboard/profile/page.tsx:230`

**Approach — new design token, not a new component:**

Add to `globals.css` `:root` / `.dark` blocks:
```css
/* Primary action button — foreground/background inversion */
--color-btn-primary-bg: theme(colors.zinc.950);
--color-btn-primary-fg: theme(colors.white);

.dark {
  --color-btn-primary-bg: theme(colors.white);
  --color-btn-primary-fg: theme(colors.zinc.950);
}
```

Expose via `@theme inline`:
```css
--color-btn-primary-bg: var(--color-btn-primary-bg);
--color-btn-primary-fg: var(--color-btn-primary-fg);
```

Classes become: `bg-btn-primary-bg text-btn-primary-fg`.

The `MintBtn` local component defined in both `ChunkedProfile.tsx` and `ExperienceManager.tsx` gets consolidated into a single shared component at `src/components/ui/MintButton.tsx` that uses the new tokens.

**Note:** Token naming is open for discussion — `btn-primary-*` is one option. Whatever is chosen should be added to the token table in `CLAUDE.md`.

- [x] `MintButton` extracted to `src/components/ui/MintButton.tsx` (49 lines) — consolidates `MintBtn` from `ExperienceManager` and `ChunkedProfile`/`ProfileChunkEditor`; used by `ResumeUploadSection` and `GitHubSection`
- [~] Design token (`btn-primary-*`) and raw `primaryBtn` string consolidation across remaining 6 files not done — deferred; the `MintButton` extraction was the prerequisite for Item 9, and the remaining token work doesn't block anything critical

**Risk:** Medium. Requires touching 6+ files and adding to the design token layer. The visual result must be identical; verify in both light and dark mode.

---

## Item 7 — Rename components ✓ (partial)

Four components have names that are ambiguous, legacy-influenced, or easily confused with each other.

| Current name | Proposed name | Reason |
|---|---|---|
| `ChunkedProfile` | `ProfileChunkEditor` | Describes what it does (edit profile chunks), not just the data structure |
| `ChunkAnalysis` | `RequirementAnalysis` | Prevents confusion with `ChunkedProfile`; describes the job requirement scoring view |
| `ParsedProfile` | `ProfilePreview` | The name implies process (parsing); it's a read-only display component |
| `EditableResumeProfile` | `EditableExperienceProfile` | "Resume" is the legacy term; the model uses "Experience" throughout |

**Scope per rename:** Update the file name, the component name, and all import sites via find-replace. Each is a standalone commit.

- [x] `ChunkedProfile` → `ProfileChunkEditor` (`ProfileChunkEditor.tsx`, export + interface renamed; `DebugPanel.tsx` import updated)
- [x] `ChunkAnalysis` → `RequirementAnalysis` (`RequirementAnalysis.tsx`, export + interface `ChunkAnalysisProps` → `RequirementAnalysisProps`; `DebugPanel.tsx` import updated)
- [~] `ParsedProfile` → `ProfilePreview` — skipped; grep confirmed no external importers (only defined in its own file); it's dead code, not a rename candidate
- [~] `EditableResumeProfile` → `EditableExperienceProfile` — skipped; same reason — no external importers; dead code

**Verify:** Run `grep -r "ChunkedProfile\|ChunkAnalysis\|ParsedProfile\|EditableResumeProfile" src/` before and after each rename to confirm all references are updated.

**Risk:** Low per individual rename. Do them one at a time.

---

## Item 8 — Reorganize top-level `components/` marketing files ✓

**Current state:** `CTA.tsx` and `UseCases.tsx` sit at `src/components/` alongside global components like `ClientWrapper`, `ThemeProvider`, `Header`.

**`CTA.tsx`:** Searching the codebase reveals it is not imported anywhere (it may be a stale/unused component, distinct from the marketing CTAs in `home/`). Verify before acting.

**`UseCases.tsx`:** If it is marketing-only, move to `src/components/home/UseCases.tsx`.

**End state:** `src/components/` root contains only truly cross-cutting components. Marketing-page-specific components live under `src/components/home/`.

- [x] `CTA.tsx` and `UseCases.tsx` confirmed unreferenced — deleted (collapsed into Item 1)

**Risk:** Very low (file moves + import update), but verify `CTA.tsx` usage first — if unused, delete rather than move.

---

## Item 9 — Split `ExperienceManager.tsx` ✓ (partial — upload + GitHub done)

**This is the largest and riskiest item. Do it last, after Items 1–8.**

**Current state:** `src/components/dashboard/ExperienceManager.tsx` is ~1100 lines and mixes:
- File upload state machine + drop zone UI
- GitHub connect/disconnect + repo list
- Manual text input panel
- Inline profile field editing
- Computed YoE display logic
- Polling orchestration
- A locally-defined `MintBtn` component

**Target structure:**

```
src/components/dashboard/
  ExperienceManager.tsx          # Orchestration only: state, API calls, polling, composes sub-sections
  ResumeUploadSection.tsx        # File drop zone, upload progress, file status display
  GitHubSection.tsx              # GitHub connect/disconnect, repo list, scanned-at display
  UserInputSection.tsx           # Free-text manual experience input panel
```

The `MintBtn` in `ExperienceManager` is eliminated by Item 6 (shared `MintButton` component).

**What stays in `ExperienceManager.tsx`:**
- `fetchRecord()` / polling logic
- All API call handlers (`handleUpload`, `handleGitHubConnect`, etc.)
- The top-level layout (toolbar, section composition)
- Shared local state passed down as props to sub-sections

**Sub-section props:** Each section receives its slice of state + the relevant action callbacks as props. They are purely presentational — no direct API calls.

**Prerequisite:** Item 6 (MintButton consolidation) should be done first so ExperienceManager's `MintBtn` is already removed before splitting.

- [x] `ResumeUploadSection.tsx` extracted (197 lines) — exports `UploadPhase` discriminated union; presentational, no API calls
- [x] `GitHubSection.tsx` extracted (351 lines) — exports `GithubState` type; includes `Toggle`, `LiveBadge` sub-components, `renderControls()` with 3 UI states
- [~] `UserInputSection.tsx` — not extracted; manual text input panel is tightly coupled to ExperienceManager's parsing state; left for a future pass
- `ExperienceManager.tsx` reduced from ~1100 lines to ~504 lines (post-split diff stat)
- **Lint fix:** `Date.now()` in `ResumeUploadSection.tsx:93` flagged by `react-hooks/purity`; added eslint-disable comment with rationale (parent re-renders via tick interval)

**Risk:** High. Requires careful prop interface design and thorough manual testing of all three experience flows (upload, GitHub, manual). Do not split speculatively — do it when the file is actively causing pain or when test coverage is in place.

---

## Item 10 — Update `CLAUDE.md` API route table ✓

Not a code change. The route table in `CLAUDE.md` is missing ~20 routes added since it was last updated. Update the table to match the actual `src/app/api/` directory.

Routes to add:
- `api/experience/chunks/` and `api/experience/chunks/[id]/`
- `api/experience/gap-response/`
- `api/experience/user-input/chunks/`
- `api/experience/user-input/parse/`
- `api/tailorings/[id]/chunks/`, `[id]/chunks/[chunkId]/`, `[id]/chunks/[chunkId]/rescore/`
- `api/tailorings/[id]/chunks/merge/`, `[id]/chunks/rename-group/`
- `api/tailorings/[id]/gap-answer/`
- `api/tailorings/[id]/refresh/`
- `api/tailorings/[id]/debug/`
- `api/tailorings/public/[userSlug]/[tailoringSlug]/`
- `api/users/check-username/[slug]/`
- `api/health/`

- [x] CLAUDE.md route table updated — added all ~20 missing routes listed above
- [~] `btn-primary-*` token not added to token table — Item 6 token work deferred

---

## Execution Order

```
1  → Delete ActionCard + ThemeButton          (no deps)
2  → Extract tailoringLabel                   (no deps)
3  → Extract formatRelativeDate               (no deps)
4  → Fix proxy.ts duplication                 (no deps)
10 → Update CLAUDE.md                         (no deps)

    ── can all be done in parallel or any order ──

5  → Extract ProfileSections                  (no deps)
7  → Renames (one at a time)                  (no deps, but do after reading through each file)
8  → Reorganize marketing components          (verify CTA.tsx usage first)

6  → Consolidate primary button style         (do before 9)

9  → Split ExperienceManager                  (depends on 6 — MintBtn must be gone first)
```

Items 1–4 and 10 are safe to batch into a single PR. Items 5–8 can follow in a second PR. Item 9 warrants its own PR.

---

## TODO — My Experience: always-visible section shells

Consider always rendering all experience section shells (Resume, GitHub, Additional
Experience, Inferred Profile) with empty states and descriptions even when unpopulated.
This lets users understand the full surface area of the platform on a single page scan
without having to interact with anything. Each shell's empty state should describe
what kinds of experience claims that section produces.
