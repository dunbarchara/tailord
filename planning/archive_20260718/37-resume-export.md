# Resume Export

**Date:** 2026-05-28
**Status:** Design — pending review before implementation
**Scope:** Tailored resume generation as a PDF export from an existing Tailoring

---

## What this feature is

Resume Export generates a single-page resume from a user's Tailoring. The resume is not generic — it reflects the same match intelligence that produced the Tailoring: which of the user's experiences are most relevant to this specific job, in what order, and surfaced in the user's own words.

The output is a clean, professional PDF in a fixed template. There is no editor, no ATS optimization, and no AI-invented content. The resume is a targeted rendering of verified experience through the lens of a specific role.

### What this feature is not

- Not an ATS keyword-optimization tool. The resume is written for human readers: hiring managers and recruiters who will read it, not filters that will parse it. If ATS pass-through rate is a priority, the user may want to supplement with a dedicated tool.
- Not a resume builder. The template is fixed and opinionated. The user takes it or leaves it. We may add more flexibility later; for now, simplicity is intentional.
- Not a replacement for the Tailoring. The resume export complements the generated Tailoring — it gives the user something to submit alongside (or instead of) their existing resume when the job is a strong match.

This positioning should be surfaced inline in the UI near the export entry point — a short, confident callout (not a disclaimer wall) that sets expectations and builds trust.

---

## How generation works

### Source data

Everything used to generate the resume comes from data the user has already provided and verified:

| Source | Used for |
|--------|----------|
| `ExperienceGroup` rows | Role headers: company, title, dates, location |
| `ExperienceClaim` rows | Bullets, skills, education facts |
| `JobChunk.experience_sources` | Signal for which claims are relevant to this job |
| `JobChunk.match_score` + `section` | Ranking signal: score weighted by section priority (see below) |
| `UserProfile` | Name, preferred name, pronouns (for header) |
| `ExperienceSource.source_data.extracted` | LinkedIn URL and location — already extracted from resume by the LLM profile extraction pipeline; same data powering the "Inferred Profile" view |
| `AuthIdentity.email` | Contact line fallback — used if `user_profile.communication_email` is not set |
| `Tailoring` (job context) | Job title + company used to ground the LLM polish prompt |

No content is invented. The LLM's role (in the optional polish phase) is editorial — tightening phrasing or trimming length — never additive.

### Phase 1 — Claim selection (mechanical, no LLM)

For a given Tailoring:

1. **Classify job chunk sections by priority.** Each `job_chunk.section` is classified using keyword matching:
   - `must_have` (weight 2.0): section name contains "Required", "Requirements", "Must Have", "Minimum Qualifications", "Basic Qualifications", "You Must"
   - `nice_to_have` (weight 1.0): section name contains "Preferred", "Nice to Have", "Bonus", "Ideal", "Desired", "Optionally"
   - `unclassified` (weight 1.5): all other sections — most requirement sections are unlabeled but still substantive

   With these weights, a partial match (score 1) in a must-have section scores `1 × 2.0 = 2.0` — equal to a strong match (score 2) in a nice-to-have section. This reflects the real signal: unmet required qualifications matter more than nailed bonus ones.

2. **Gather relevant claims.** For each job chunk where `match_score >= 1`, collect cited claim IDs from `experience_sources` and compute a `claim_relevance_score`:
   ```
   claim_relevance += match_score × section_weight
   ```
   Summed across all chunks that cite a given claim.

3. **Filter contextually redundant claims.** Claims whose content is *primarily* a years-of-experience assertion (pattern: `\b\d+\+?\s+years?\b` with no other substantive content) are flagged as `redundant_in_resume_context`. Resume section headers already show dates — stating "5+ years of Python" in a bullet is noise. These claims are deprioritized: included only if a role has fewer than 3 other bullets to show.

4. **Group by ExperienceGroup.** Claims that belong to a role/project/education group are attached to their parent. Ungrouped claims go into a fallback bucket.

5. **Rank groups by relevance.** Score each group by the sum of `claim_relevance_score` across all its cited claims. Groups with no cited claims but high-confidence skill claims may still appear in the Skills section.

6. **Rank bullets within each group.** Within a role, bullets are ordered by `claim_relevance_score` descending. Uncited bullets from that role appear after, ordered by their existing `position`.

7. **Apply section caps.** To stay near one page: max ~5 bullets per role, max 3–4 roles in EXPERIENCE. Overflow roles are omitted entirely (not truncated mid-list).

8. **Extract Skills.** All `claim_type="skill"` claims that are `status="active"`, ordered by `claim_relevance_score` desc then `position`.

9. **Extract Education.** All `group_type="education"` groups, ordered by `end_date` desc.

The output of Phase 1 is a structured **resume selection** object: an ordered list of sections (role groups + bullets), a skills list, and an education list. This is what gets stored and previewed.

### Phase 2 — LLM polish (optional, user-initiated)

After Phase 1 the user sees a preview. If they choose to polish:

- Each bullet is sent to the LLM with its original text and the job context (title + company), and asked to tighten the phrasing for resume format. The LLM may not add claims, roles, skills, or dates that are not in the original.
- The LLM returns a rewritten version alongside the original claim ID.
- The UI presents original vs. rewritten per bullet. The user accepts or reverts individually. A batch "accept all" option is available.
- Accepted rewrites are stored alongside the original in the resume selection object — original content on `ExperienceClaim` is never mutated.

Polish is stateless per-call. It does not run automatically and does not block export.

#### LLM polish prompt (`backend/app/prompts/resume_polish.py`)

```python
SYSTEM = """
You are a resume editor. Your task is to tighten a single resume bullet point — improving conciseness, clarity, and impact — without changing the facts or inventing content.

HARD CONSTRAINTS — violating any of these is an error:
1. Do not add any information not present in the original. If the original mentions no metric, do not add one.
2. Do not reference the company name, role title, or employment dates — these appear in the resume header and are redundant in bullets.
3. Strip phrases like "during my time at [Company]", "in my role as [Title]", "over the past N years", "I was responsible for". The header already provides that context.
4. Do not invent outcomes, numbers, or scale claims that are not explicitly stated in the original.
5. Return the original unchanged if it is already concise and well-formed.

STYLE GUIDE:
- Start with a strong past-tense action verb: Led, Built, Designed, Reduced, Shipped, Architected, Migrated, Drove, Owned, etc.
- Put the most important information first (action → outcome → context).
- If a metric exists in the original, surface it prominently.
- Target: one line, under 120 characters. Two lines only if content genuinely requires it.

JOB CONTEXT (for tone calibration only — do not add job-specific content not in the original):
Role: {job_title} at {company}

ORIGINAL BULLET:
{original_content}

Return JSON only. No markdown fences:
{"rewritten": "...", "unchanged": true|false, "note": "one phrase: what changed or why unchanged"}
"""
```

The `note` field is surfaced in the UI tooltip on hover so users understand what changed without having to diff manually.

### PDF rendering

The backend renders the resume as HTML then converts to PDF using Playwright (already in the stack for job scraping). No new dependency.

The HTML template is a fixed layout: constrained-width page, semantic structure, print-optimized CSS (no color, no shadows, standard serif/sans-serif fonts, controlled spacing). The same template is used for the preview in the frontend — visual consistency between preview and export.

---

## Template structure

```
[Name]
[email] | [tailord.app/u/slug or tailord.app/t/slug] | [LinkedIn if provided] | [Location if available]

EXPERIENCE
[Company]                           [City, State]
[Title]                          [Month Year – Month Year]
- [Bullet]
- [Bullet]
...

SKILLS
[Comma or pipe separated list]

EDUCATION
[School]                            [City, State]
[Degree] | [GPA / Honors if available]      [Graduated Month Year]
```

**Contact line logic:**
- Email: `user_profile.communication_email` if set, otherwise `auth_identity.email` for the google provider
- Public link: `tailord.app/t/{public_slug}` if `letter_public OR posting_public`, else `tailord.app/u/{username_slug}` if `profile_public`, else omit
- LinkedIn: pulled from `experience_sources.source_data.extracted` (LLM-extracted from resume); surfaced as an editable field in the export modal so the user can correct it; override stored in `resume_draft.contact_override`
- Location: same source as LinkedIn — extracted profile; same editable override pattern

**Missing sections are omitted gracefully.** If there are no education groups, no EDUCATION section appears. If there are no cited skill claims, SKILLS is omitted. The resume is still valid and exportable.

---

## Prerequisites and graceful degradation

### Required to generate
- At least one active `ExperienceClaim` linked to this user. If the user has zero claims, show a prompt directing them to **My Experience** to upload a resume or add experience manually. Do not attempt generation.

### Degraded but not blocked
- **No resume uploaded (experience from manual input, GitHub, or gap responses only).** Surface a soft callout in the preview: "This resume was generated from your manually entered experience. Uploading your resume in My Experience may expand what's available." Allow export regardless.
- **No education groups.** Omit EDUCATION section silently.
- **No cited claims for a role.** Role still appears in the preview if it has any active claims and it is a high-relevance group (ranked in top N). Bullets are ordered by `position` when no match signal is available.
- **No skills claims.** Omit SKILLS section.
- **No public profile or tailoring.** Omit the public link from the contact line.

---

## Data model

### Resume selection object (JSONB)

Stored on `tailorings.resume_draft` (new nullable JSONB column). Null = not yet generated.

```json
{
  "generated_at": "2026-05-28T...",
  "polished": false,
  "contact_override": {
    "linkedin_url": null,
    "location": null
  },
  "sections": [
    {
      "group_id": "uuid",
      "group_type": "role",
      "included": true,
      "claim_ids": ["uuid", "uuid"],
      "rewrites": {
        "claim_uuid": "Rewritten bullet text accepted by user"
      }
    }
  ],
  "skills_claim_ids": ["uuid", "uuid"],
  "education_group_ids": ["uuid"]
}
```

`included: false` on a section means the user explicitly excluded it in the preview. Excluded sections persist across preview sessions so the user does not have to redo the same edits.

### Migration

Add `resume_draft JSONB nullable` to `tailorings`. No new table needed for v1.

---

## API design

All routes are user-scoped (require `require_api_key` + `get_current_user`).

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/tailorings/{id}/resume/generate` | Run Phase 1 selection; store in `resume_draft`; return selection |
| `GET` | `/tailorings/{id}/resume` | Return current `resume_draft`; 404 if not yet generated |
| `PATCH` | `/tailorings/{id}/resume` | Update `included` flags, `contact_override`, `rewrites` (user edits in preview) |
| `POST` | `/tailorings/{id}/resume/polish` | Run Phase 2 LLM polish on specified claim IDs; returns rewrites for user review |
| `POST` | `/tailorings/{id}/resume/pdf` | Render current `resume_draft` to PDF; stream bytes |

The frontend Next.js API routes are thin proxies to these endpoints, following the standard `proxyToBackendWithUser` pattern.

---

## Frontend UX

### Entry point
A "Export Resume" button or menu item on the Tailoring detail page, visible only when `generation_status = "ready"`.

### Export modal / panel (initial state)
Before Phase 1 runs, the panel shows:
- Brief positioning callout (see below)
- "Generate Resume" CTA
- If user has zero claims: instead shows a prompt to visit My Experience

### Preview state
After Phase 1:
- Resume rendered in a visual preview (same HTML template, not PDF)
- Each section has an exclude toggle; each bullet has an exclude toggle
- Optional fields (LinkedIn, Location) surfaced as inline inputs if not already set
- "Polish with AI" button triggers Phase 2 (with loading state per bullet)
- "Export PDF" button — always available; does not require polish

### Polish UX
Per bullet: shows original text and rewritten text side by side. "Use rewritten" / "Keep original" toggle. Batch accept-all option.

### Positioning callout (copy)

Short, confident, placed near the top of the preview panel:

> **How this resume was built**
> Your resume reflects the same analysis as your Tailoring — it surfaces the experience most relevant to this specific role, in your own words, in a clean one-page format.
>
> This is optimized for human readers, not ATS filters. If keyword pass-through rate is a priority for a specific application, you may want to supplement with a dedicated ATS tool.

Tone guidance: matter-of-fact, not apologetic. Frame what we do well, name what we deliberately don't do. The ATS line is a confidence signal, not a retreat.

---

## Build sequence

### Step 1 — Migration
Add `resume_draft JSONB nullable` to `tailorings`. Alembic migration.

### Step 2 — Selection service (`backend/app/services/resume_selector.py`)
- `generate_resume_selection(tailoring, db) -> ResumeDraft` — Phase 1 mechanical pipeline
- `check_resume_prerequisites(user, tailoring, db) -> PrerequisiteResult` — returns whether generation is possible and any soft warnings

### Step 3 — LLM polish service (`backend/app/services/resume_polisher.py`)
- `polish_bullets(claim_ids, job_context, db) -> dict[str, str]` — returns `{claim_id: rewritten_text}`
- Prompt: tighten for resume format; do not add or invent; return JSON only

### Step 4 — PDF renderer (`backend/app/services/resume_renderer.py`)
- `render_resume_html(resume_draft, user, tailoring) -> str` — renders Jinja2 HTML template
- `render_resume_pdf(html: str) -> bytes` — Playwright headless print-to-PDF

### Step 5 — API endpoints (`backend/app/api/tailorings.py` or new `resume.py` router)
Five endpoints as specified above. `POST /pdf` streams bytes with `Content-Type: application/pdf`.

### Step 6 — ORM model update
Add `resume_draft` mapped column to `Tailoring`.

### Step 7 — Frontend: Next.js API routes
`/api/tailorings/[id]/resume/` (generate, GET, PATCH, polish, pdf) — thin proxies.

### Step 8 — Frontend: preview component + export modal
`ResumePreview.tsx` — renders the resume draft as a visual preview. `ResumeExportPanel.tsx` — wrapper with positioning callout, polish controls, and export button.

### Step 9 — Integration into TailoringDetail
Add entry point (button/menu) on the Tailoring detail page. Wire to `ResumeExportPanel`.

---

## Out of scope (v1)

- Multiple resume templates
- Resume editor (drag-reorder, rich text editing)
- ATS scoring or keyword gap analysis
- Storing or versioning multiple resume exports per tailoring
- Resume sharing (separate public URL)
- Export formats other than PDF

---

## Considered and rejected approaches

### Resume-as-base (LLM edits the uploaded resume document)
An alternative approach: take the user's uploaded resume as a base and prompt the LLM to swap or supplement bullets using the job match analysis and experience claims.

**Rejected for v1 because:**
- Moves toward "resume rewriter" territory — harder to explain honestly and harder to audit.
- LLMs editing existing documents drift more than LLMs working from structured source material. Hallucination risk is higher when the task is "improve this" than "express this claim concisely."
- Decouples the output from the Tailoring analysis. The resume should be a direct consequence of match intelligence, not a riff on the existing resume document.
- The underlying bullet quality comes from claim extraction. If extracted claims are well-phrased (they often are — the resume is the source), Phase 1 + polish gets there without the risks.

Worth revisiting if users report that claim extraction produces noticeably rougher content than their original resume. The right fix in that case is improving extraction quality, not switching to a document-editing model.

## Open questions

- **One-page enforcement:** Phase 1 applies heuristic caps (~5 bullets/role, 3–4 roles). Real one-page guarantee requires knowing the rendered height, which only Playwright knows at PDF time. Start with the heuristic; revisit if users report frequent overflows.
- **Polish prompt iteration:** The prompt in this doc is a first pass. It should be tested against 3–5 real claims from varied roles before Phase 2 ships. The hardest case is claims that are already well-written — the prompt must reliably return `"unchanged": true` rather than making cosmetic changes that the user then has to evaluate.
- **Experience-only users (no resume upload):** Soft warning is sufficient. No hard block. Revisit if user feedback indicates the output quality is too low without a resume.

---

## Future work: "Refresh layout" action

**Problem:** `resume_draft` stores two kinds of data with different ownership:

1. **User intent** — include/exclude toggles, accepted rewrites, contact overrides. Should be preserved.
2. **Derived structure** — section ordering (date sort), metadata (name, dates, location, `group_type`), education entries, which claims were selected. These are outputs of the selection algorithm, not user decisions. They can become stale if the selection logic improves after a draft was generated.

Full regeneration is a blunt instrument — it discards user intent (their toggles and rewrites) to pick up structural improvements. The right primitive is a lighter "Refresh layout" action.

**Proposed behaviour:**
- Re-run `generate_resume_selection` against the tailoring to get fresh ordering, metadata, location lookups, and claim selection
- Merge the result with the existing draft: preserve `included` flags, `rewrites`, and `contact_override` for any sections/claims that carry over
- New sections (claims that weren't previously selected) start included by default; removed sections are dropped without warning
- Returns the merged `ResumeDraft` — user reviews the diff before exporting

**Implementation sketch:**
- Backend: new `POST /{tailoring_id}/resume/refresh-layout` endpoint (or reuse `generate` with a `preserve_user_edits=true` flag)
- Merge logic: for each new section, if a section with the same `group_id` exists in the old draft, copy over `included` and any `rewrites` entries for claim IDs that appear in both
- Frontend: "Refresh layout" button in the controls panel, below "Generate Resume"; only shown when a draft exists

**When this matters:** After shipping any change to `resume_selector.py` that affects ordering, metadata resolution, or claim selection (location lookup improvements, date parsing fixes, new source types). Users who generated before the fix would benefit from a one-click refresh without losing their edits.

**Status:** Not planned — track as a post-v1 improvement once the selection logic stabilises.

---

## North star: resume-scoped claim versions for scoring consistency

**Problem:** The Tailoring's match scoring runs against the user's original `ExperienceClaim` rows (sourced from their uploaded resume). If the user edits bullets in the Resume Export panel — accepting AI rewrites, toggling bullets, reordering — the Tailoring's scoring and advocacy analysis still references the old content. This creates a consistency gap: the resume the recruiter reads may differ meaningfully from the experience Tailord analyzed.

**Target behaviour:** When a user finalises a Resume Export they intend to share (e.g. clicks "Export PDF" or a future "Lock & Share"), offer to rescore the Tailoring using the generated resume's content as the reference. Concretely:

1. **Materialise the resume as a claim snapshot.** At "lock" time, write a versioned copy of the draft's bullets back as a new `ExperienceSource` row (`source_type = "resume_export"`, linked to `tailoring_id`) with the accepted rewrites merged in. Chunk it using the same `experience_chunker` pipeline — these become the scored claims for the locked tailoring.
2. **Rescore job chunks against the snapshot.** Re-run `enrich_job_chunks` using the new source's embeddings. Store the result as a parallel `match_score_v2` (or write to a new `tailoring_job_scores` table so the original scoring is preserved).
3. **Regenerate the Tailoring against the snapshot.** Run the letter generator with the snapshot profile as the source, replacing the old `generated_output`. The user gets a Tailoring that accurately reflects what their exported resume says.
4. **Display the scoring/advocacy in sync.** The match score, requirement hits, and gap responses shown in the Tailoring detail would reflect the actual submitted resume — no divergence.

**Why not do this now:** Adds significant backend complexity (versioned sources, rescore pipeline trigger, UI for "lock" state). Phase 1 — the export itself — has clear standalone value. The disclaimer in the UI is the right intermediate step. Track this as a future milestone once export adoption is established.

**Signals to watch:** User confusion about discrepancy between Tailoring analysis and resume content; users asking "does this change affect my score?"; users editing bullets but not regenerating the Tailoring.
