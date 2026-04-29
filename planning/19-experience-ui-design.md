# My Experience — UI Design Reference

**Date:** 2026-04-28
**Status:** Established — use this before touching Experience UI.

---

## Core Principle

The user is the author and owner of every claim in their profile. Tailord accelerates
aggregation from multiple sources (resume, GitHub, direct input, gap responses), but the
user retains full editorial control over all of it. No claim is locked to its source.

**Consequence:** every individual ExperienceChunk — regardless of source_type — is
independently editable and deletable from the same surface. Resume bullets, GitHub
skill tags, user_input claims, and gap_response answers all behave identically at the
interaction level.

---

## Layout

**Single scrollable page, visually sectioned.** No tabs. The experience view is a
unified profile — the user should see the full picture in one scroll without choosing
which source to look at.

Sections (only rendered if they have data):
1. **Resume** — work experience, skills, projects, education, certifications
2. **GitHub** — one card per connected repo
3. **Additional Experience** — user_input chunks + Add Experience form
4. **Gap Responses** — only shown if ≥ 1 gap_response chunk exists

The source management controls (upload resume, connect GitHub) remain at the top of
the page in the existing `SettingRow` layout — unchanged structurally, just the
"Additional Context" row is replaced by the new Add Experience flow.

The sectioned profile view lives below the source management rows, separated by a
divider, and replaces the current tabbed `ChunkedProfile`.

---

## Edit/Delete Affordance

**Every chunk is an editable, deletable item.** The consistent visual language:

- **View state**: content rendered normally; hover reveals pencil (✎) and × controls
  as small icons at the trailing edge of the item
- **Edit state**: content replaced with textarea (or inline input for short fields);
  Save / Cancel controls below
- **Delete**: clicking × optimistically removes from local state and calls
  `DELETE /api/experience/chunks/[id]`; no confirmation for individual chunks (they
  are small and easy to re-add)

The pencil/× row appears on `group-hover` using Tailwind's group utility — the parent
element is `group`, controls are `opacity-0 group-hover:opacity-100`. This pattern
already exists in `EditableChunk` for the pencil; × is added alongside it.

For skill pills specifically: the × appears inline inside the pill on hover, rather
than as a separate icon. The pill expands slightly on hover to reveal it.

---

## Section-Specific Rendering

### Resume

Renders like a familiar resume structure. Users recognize the format and immediately
understand what they're reading and editing.

```
Work Experience
  ACME Corp | Senior Engineer · 2020–2023
    · Built the pipeline for X                    [✎] [×]
    · Led migration from A to B                   [✎] [×]

  Startup Inc | Founding Engineer · 2018–2020
    · Scaled from 0 to 10k users                  [✎] [×]

Skills
  Python  [×]   FastAPI  [×]   React  [×]   PostgreSQL  [×]

Projects
  MyApp
    A web app for doing Y                         [✎] [×]

Education
  BSc Computer Science, MIT, 2018                 [✎] [×]
```

- Work experience group header (Company | Title · Date) remains editable via
  `EditableGroupHeader` — editing one header updates all bullets in that group
- Bullets are each individually deletable
- Skills render as pills with × inside on hover
- Projects, education, certifications: editable + deletable per chunk

### GitHub

One card per connected repo. The repo name is the card header (not editable — it's a
structural label from the GitHub connection, not a chunk).

```
┌─ tailord ──────────────────────────────────────────────────────┐
│  An AI tailoring platform that maps experience to job...   [✎] [×]  │
│                                                                │
│  Python  [×]   FastAPI  [×]   PostgreSQL  [×]   React  [×]   │
└────────────────────────────────────────────────────────────────┘
```

- Project summary (readme_summary chunk): editable content, deletable
- Tech stack skills: pills with × on hover, same as resume skills
- Deleting all chunks within a repo does not disconnect the repo — source management
  (re-scan, disconnect) stays in the top SettingRow
- If enrichment is in progress (no chunks yet), show a subtle "Enrichment in progress"
  state inside the card

### Additional Experience

User_input chunks rendered as a vertical list of claim cards, each independently
editable and deletable.

```
Additional Experience

  I have 5 years of experience leading data platform migrations    [✎] [×]
  Proficient in Terraform and Kubernetes                           [✎] [×]
  Contributed to open source ML tooling (3k GitHub stars)         [✎] [×]

  ┌─────────────────────────────────────────────────────────────┐
  │  Describe experience, projects, or skills not captured above │
  │                                                             │
  └─────────────────────────────────────────────────────────────┘
  [ Parse & Add ]
```

**Add Experience flow:**
1. User types in textarea
2. Clicks "Parse & Add"
3. If short (≤200 chars or single sentence): skip preview, persist immediately as 1 chunk
4. If longer: call `POST /api/experience/user-input/parse`, show parsed claim list
   with checkboxes; user can deselect unwanted claims
5. "Confirm" → call `POST /api/experience/user-input/chunks` with selected claims
6. New chunks appear at the bottom of the list; textarea clears

The textarea and button are always visible at the bottom of the Additional Experience
section (not hidden behind an "Add" button). Empty state shows just the textarea.

### Gap Responses

Only rendered if the user has ≥ 1 gap_response chunk. Hidden entirely otherwise
(not an empty section).

```
Gap Responses

  ╌ Asked when applying to Stripe — "Do you have experience with  ╌
  ╌  distributed tracing in high-throughput systems?"             ╌
  I spent two years maintaining a tracing pipeline at ACME...     [✎] [×]

  ╌ Asked when applying to Figma — "..."                         ╌
  We built a canvas rendering engine from scratch...               [✎] [×]
```

- Question shown as muted context above the answer (italic, text-tertiary)
  Format: *"Asked when applying to [Company] — [question text]"* where Company
  comes from the tailoring's job data (may not always be available — fall back to
  just the question)
- Answer is the main content, full edit via `EditableChunk`
- Delete removes the chunk from experience entirely
- `chunk_metadata.question` and `chunk_metadata.tailoring_id` drive the context line

---

## Empty States

- `hasExperience` check includes user_input chunks and gap_response chunks —
  a user with only gap responses should see the profile view, not the upload prompt
- Resume section: hidden if no resume chunks (not "upload resume here" — that's in the
  top SettingRow)
- GitHub section: hidden if not connected
- Additional Experience section: always shown (textarea is always available)
- Gap Responses section: hidden if no gap_response chunks

---

## Source Management (unchanged)

The top SettingRow layout — Resume upload, GitHub connect/disconnect/rescan —
remains structurally unchanged. The "Additional Context" SettingRow is removed
(replaced by the inline section below the divider). The resume upload, processing
states, and GitHub connection management flows are not part of this overhaul.

---

## Component Inventory

| Component | Status | Notes |
|-----------|--------|-------|
| `ExperienceManager` | modify | Remove old textarea row; update hasExperience |
| `ChunkedProfile` | rewrite | Remove tabs; single sectioned view; add delete |
| `EditableChunk` | extend | Add onDelete prop and × button |
| `EditableGroupHeader` | keep | No change needed |
| `AddExperienceForm` | new | Parse & Add flow with preview |
| `GapResponseSection` | new | Question context + answer cards |

---

## API Surface Used

| Endpoint | Purpose |
|----------|---------|
| `GET /api/experience/chunks` | Load all chunks for the profile view |
| `PATCH /api/experience/chunks/[id]` | Edit chunk content |
| `DELETE /api/experience/chunks/[id]` | Delete any individual chunk |
| `POST /api/experience/user-input/parse` | Preview atomic claims before persisting |
| `POST /api/experience/user-input/chunks` | Persist user_input claims |

---

## Design Tokens Used

- `surface-base` for section backgrounds
- `surface-elevated` for cards and inputs
- `text-primary / text-secondary / text-tertiary` for hierarchy
- `border-subtle` for card borders
- `text-disabled` for muted context (gap question lines)
- Error red (`hover:text-error`) for × delete controls on hover
