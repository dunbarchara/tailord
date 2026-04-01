# Tailoring Detail Architecture — Three Views, Three Audiences

*Captures a strategic discussion on the purpose and priority of each view in the tailoring detail page, and the direction for the Analysis tab redesign.*

---

## The Core Insight: The Enriched Job Posting Is the Primary External Artifact

The job posting is the one artifact both the candidate and the recruiter have already read. It's the shared language — the interface both parties are using to evaluate fit.

An enriched re-rendering of that posting doesn't add something new to a recruiter's stack. It annotates the document they already own: *"You asked for X. Here is why this candidate has X, line by line."* That framing earns trust in a way a standalone letter can't, because it respects the recruiter's frame of reference rather than replacing it.

This makes the enriched job posting the most compelling external artifact the platform produces — not a supplementary view. For the recruiter, it should be the primary view.

The advocacy letter is genuine supplementary value: a narrative synthesis for hiring managers who want to read an argument rather than a line-item response. But it's the second thing someone reaches for, not the first.

---

## Three Views, Three Purposes

### 1. Analysis Tab — Private, Candidate-Facing

**Audience:** The candidate, before and after generating a tailoring.

**Purpose:** Empowerment. "Where do I actually fit, honestly?"

This is the tab the candidate lives in. It's the canonical internal view — the source of truth about the match. The Letter and Posting are both derived from what this tab represents.

**What it should show:**
- **Strong matches** — advocacy blurb only. The candidate already fits; the advocacy tells them how to present it. Rationale adds no new actionable signal at this score level.
- **Partial matches** — advocacy blurb + rationale. Both earn their place here. The advocacy shows how to frame the partial match; the rationale explains *why it's partial and not strong* — that's the signal that tells the candidate what's missing and what to prepare. Rationale rendered as secondary text below the advocacy (smaller, more muted).
- **Gaps** — rationale only (advocacy is null for gaps by design). Currently gap cards show nothing but the requirement text. The rationale fills this: *"No evidence of X found in profile"* is directly actionable — the candidate knows exactly what to add to their experience.

**Rationale vs. advocacy — why both belong in this tab:**
The advocacy blurb is written for a recruiter (external voice, confidence framing). The rationale is the LLM's analytical reasoning (internal voice, diagnostic). The Analysis tab is the candidate's private view — the place where analytical honesty is more valuable than polished presentation. Showing rationale here, at the score levels where it changes what the user does next, is consistent with the tab's purpose: empowerment through accurate self-assessment, not optimism.

**Alternative — expandable rationale:**
Rather than inline tiered display, rationale could sit behind a click expand (same interaction pattern as the JobPosting chunk expand). Default card shows advocacy only; clicking reveals rationale in a callout below. Keeps the Analysis tab visually clean at a glance; trades discoverability for density control. The tradeoff is that for gaps — where rationale is the most actionable signal — it risks being missed entirely. Worth exploring if the tiered inline approach feels too heavy in practice.

**What it should not show (move to admin/debug):**
- Chunk IDs, score integers, raw match metadata
- Anything that reads as an LLM evaluation tool rather than a candidate empowerment tool

**Why it's primary:** This is where the platform's north star lives — making the candidate more capable, not just producing documents for them. The Analysis tab is where a candidate learns something actionable about their position. It's also the natural home for the proactive enrichment loop: if a gap surfaces here, the right action is "add context to your experience."

---

### 2. Enriched Job Posting — Public, Recruiter-Primary

**Audience:** Recruiters and hiring managers receiving a shared tailoring link.

**Purpose:** A line-by-line response to the recruiter's own document. Meets them where they already are.

The job posting is common and familiar language between candidate and company. An enriched re-rendering takes that common interface — which is more of a company descriptor — and enriches it with the candidate's experience and context, effectively making both what the company is looking for and what the candidate has to offer common language, and easily digestible for both parties.

**What it shows:**
- Each job requirement from the original posting
- Candidate evidence mapped directly to each requirement (advocacy blurbs)
- Score-informed presentation: Strong matches lead; Partial matches are included with honest framing; Gaps are handled gracefully (omitted or briefly acknowledged)

**Why it's the hero of the shared page:** Of the two shareable views, the enriched posting is what a recruiter is most likely to engage with. It validates that the candidate read and understood the job posting. It makes the recruiter's evaluation effortless — every requirement is already answered.

---

### 3. Advocacy Letter — Public, Supplementary

**Audience:** Hiring managers who prefer narrative over structured lists; secondary read after the enriched posting.

**Purpose:** A synthesised, third-person argument for why a conversation is worth having. Not a resume, not a cover letter — a third-party advocate's case for fit, written in the candidate's voice.

See `09-tailoring-philosophy.md` for the full philosophy, voice guidelines, and format specification.

**What it is not:** The primary shareable artifact. The enriched posting leads; the letter is supplementary for those who want the narrative version.

---

## Implications for the Public Shared Page (`/u/{slug}/{tailoringSlug}`)

**Current state:** The letter is probably shown first; the enriched posting is secondary.

**Target state:** The enriched posting is the default/hero view at the shared URL. The letter is a secondary tab for those who want the narrative synthesis. This flip reflects the actual priority: the recruiter's most useful document is the enriched posting.

---

## Implications for the Dashboard Tailoring Detail Page

**Current state:** Three tabs (Letter, Posting, Analysis) with roughly equal weight. Analysis feels like an admin debug tool.

**Target state:**

- **Analysis is the primary tab** — the first thing the user sees. Redesigned for a candidate audience (see above). This is where the user spends most of their time.
- **Letter and Posting are "Preview" tabs** — clearly framed as previews of what external parties see, derived from the Analysis. The user switches to these when they want to see what a recruiter would receive.
- **Tab labels** could reflect this: "Analysis" (primary) vs. "Preview: Letter" / "Preview: Posting" — or some equivalent framing that communicates the relationship.

---

## Admin / Debug View

The current Analysis tab's raw scoring data (chunk scores, rationale text, internal labels, chunk IDs) has genuine value for evaluating LLM output quality — but it belongs in a development/admin context, not in the production UI.

**Approach:** Preserve the current debug view at `?debug=1` on the tailoring detail page, or at a protected admin route `/admin/tailorings/{id}`. Keeps it one parameter away without cluttering the production interface.

---

## Implications for the Homepage ProductPreview

Once the Analysis tab is redesigned as a proper user-facing view, the homepage mockup becomes something that can be honestly screenshotted and shown.

The ProductPreview section can then tell both sides of the value proposition:

- **Left / primary:** The Analysis view — *"What you see: your fit, honestly."* Strong/Partial/Gap with candidate-facing explanations.
- **Right / secondary:** The enriched posting — *"What your recruiter sees: your case, line by line."*

This is a story no other platform can tell, and it's accurate to what's actually been built. It also directly answers the homepage headline: *"You have the experience. We'll show you how to prove it."* — the Analysis is where you *see* it; the enriched posting is how you *prove* it.

---

## Implementation Priority

1. **Analysis tab redesign** — highest leverage. Unlocks the homepage screenshot, delivers the most user value, and establishes the correct hierarchy for the dashboard. See `11-adjusted-sprint-plan.md` for sprint context.
2. **Public shared page tab order flip** — the enriched posting becomes the default view. Low effort, high impact for the recruiter experience.
3. **Homepage ProductPreview screenshot** — blocked on (1). Once the Analysis tab is polished, screenshot and replace the stylized mockup.
4. **Admin/debug route** — low effort. `?debug=1` on the tailoring detail page preserves LLM evaluation capability.
