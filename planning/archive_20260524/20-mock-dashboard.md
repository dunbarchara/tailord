# Day 17 — Mock Dashboard + Demo UX Polish

**Branch:** `dunbarchara/mockdashboard`
**Theme:** Public-facing demo mode for the dashboard, mock job postings, homepage CTA overhaul, and posting tab rendering correctness.

---

## Part 1 — Mock Data Infrastructure

- [x] Created `frontend/src/mock/data.json` — exported from real DB via export script; contains `displayName`, `user`, `experience`, `experienceChunks`, `tailorings`, `tailoringDetails`, `chunks`
- [x] Created `frontend/src/mock/data_archive.json` — archived copy for reference
- [x] Created `frontend/src/mock/loader.ts` — typed accessors: `getMockTailoring()`, `getMockTailoringChunks()`, `getMockExperience()`, `getMockExperienceChunks()`, `getMockTailoringList()`
- [x] Created `frontend/src/mock/context.tsx` — `MockContext` React context; `useMockData()` hook for demo pages
- [x] Created `backend/scripts/export_mock_data.py` — CLI: `uv run python scripts/export_mock_data.py --user-id <uuid> --tailoring-id <uuid> [...]`; writes `frontend/src/mock/data.json`

---

## Part 2 — Demo Dashboard Routes

- [x] Created `frontend/src/app/(demo)/demo/dashboard/layout.tsx` — Sidebar shell (no banner); uses mock context
- [x] Created `frontend/src/app/(demo)/demo/dashboard/page.tsx` — tailorings list from mock data
- [x] Created `frontend/src/app/(demo)/demo/dashboard/experience/page.tsx` — `ExperienceManager` with `readOnly` + `initialChunks={getMockExperienceChunks()}`
- [x] Created `frontend/src/app/(demo)/demo/dashboard/profile/page.tsx` — profile preview from mock data
- [x] Created `frontend/src/app/(demo)/demo/dashboard/tailorings/[tailoringId]/page.tsx` — `TailoringDetail` with mock tailoring + chunks

---

## Part 3 — Mock Job Posting Pages

- [x] Created `frontend/src/app/(mock)/mock/job-mid-level-engineer/page.tsx` — Stripe mid-level SWE posting; `robots: noindex`
- [x] Created `frontend/src/app/(mock)/mock/job-software-engineer-linear/page.tsx` — Linear SWE posting; mixed requirements
- [x] Created `frontend/src/app/(mock)/mock/job-staff-engineer/page.tsx` — Vercel staff engineer posting; skewed toward leadership/systems

---

## Part 4 — ChunkedProfile + ExperienceManager: readOnly mode

- [x] `ChunkedProfile.tsx` — added `initialData?: ExperienceChunksResponse` and `readOnly?: boolean` props; skips fetch when `initialData` provided; propagates `readOnly` to sub-components; hides Edit/Delete/Add controls in `readOnly`
- [x] `ExperienceManager.tsx` — added `initialChunks?: ExperienceChunksResponse` prop; removed `ReadOnlyProfilePreview`; passes `initialChunks` + `readOnly` through to `ChunkedProfile`

---

## Part 5 — AnalysisView: readOnly gap question display

- [x] `AnalysisView.tsx` — added `readOnly?: boolean` prop; passed to `ChunkContextPanel`; in `readOnly` mode with a gap question: shows question text + "Sign in to add context" CTA → `/register` instead of answer form
- [x] `TailoringDetail.tsx` — passes `readOnly={readOnly}` to `AnalysisView`

---

## Part 6 — Homepage + Pending Page CTAs

- [x] `HeroSection.tsx` — signed-out: two CTAs: primary "View Demo" → `/demo/dashboard`, secondary "Start your first tailoring →" → `/register`; signed-in: unchanged ("Create a tailoring")
- [x] `ClosingCTA.tsx` — same two-CTA pattern for signed-out; primary "View Demo", secondary "or get started →"
- [x] `frontend/src/app/(auth)/pending/page.tsx` — added "While you wait" block below check-status button with demo link → `/demo/dashboard`

---

## Part 7 — Posting Tab Rendering + Banner + Copy Button

- [x] `TailoringDetail.tsx` — added `publicMode={true}` to `JobPosting` on Posting tab; GAP chunks now render as plain text (no red bar), PARTIAL chunks show sage green — matches public `/t/[slug]` view exactly
- [x] `TailoringDetail.tsx` — updated preview banner text: "Preview — this is how your tailoring appears when shared. Gap requirements are hidden, partial matches appear green, and each matched item includes an advocacy statement and the experience source that supports it."
- [x] `TailoringDetail.tsx` — simplified `canCopy` to `activeTab === 'letter' && !!tailoring.generated_output`; Copy button now disabled on Analysis and Posting tabs (AnalysisView is an interactive editor surface, not static copyable content)

---

## Part 8 — Sidebar + DashboardHome

- [x] `Sidebar.tsx` — updated to support demo mode context (mock user display name, nav links scoped to `/demo/dashboard/*`)
- [x] `DashboardHome.tsx` — renders tailoring list from mock data in demo mode
