# Plan 28 — Repository Identity & Experience Surface Design

## Core Identity Statement

> *Tailord is a repository for atomic, sourced professional experience — and an advocate that leverages it. The Tailoring is the output; the record is the value.*

Tailord advocates in two directions:
- **Externally** — structured, role-specific advocacy documents per application
- **Internally** — actively helping candidates surface, articulate, and accumulate the evidence of their own work

The platform should make users feel positively about every interaction. The experience of *adding to the record* should feel rewarding, not administrative.

---

## Design Principle: Make the Repository Feel Alive

Users who see their record growing will tend it. Users who don't see it won't. Every feature that adds to the repository should make the addition visible and feel meaningful.

### Experience Heatmap (dashboard homepage)

A GitHub-style contribution heatmap showing experience claims over time — one cell per day, color intensity by number of claims added that day. Clicking a cell could surface the claims from that period.

Goals:
- Makes the repository feel like something worth tending
- Creates a visible history of engagement with the platform
- Gives users a sense of momentum — a growing record they can see
- Signals to users when they've been away and their record has stalled

Implementation notes:
- Data source: `created_at` timestamps on individual experience claims
- Need to design the atomic claim data model if not already present (each claim has: source, content, date, optionally a source link)
- Dashboard homepage is the right place — it's the first thing users see
- Consider: should the heatmap show all claims, or only claims added since joining? Probably all, with the join date visible.

### Other "repository feels alive" surfaces to explore

- A counter or progress indicator in the sidebar: "142 experience claims across 6 sources"
- A "recently added" strip on the dashboard: the last 3–5 claims with their source label
- A "coverage" indicator per Tailoring: how many of the job's requirements map to sourced claims vs. gaps

---

## Design Principle: Advocate Internally — Tone and Language

When a user adds experience (via text, gap enrichment answer, commit hook, etc.), the confirmation response should acknowledge the work briefly and warmly. Not generic ("Saved!"). Not effusive ("Amazing work, you're incredible!"). Something specific, brief, and genuine.

### Principles for the tone

- **Specific over generic.** Reference what was just added if possible: "Leadership experience added." beats "Saved."
- **Brief.** One short phrase or sentence. The acknowledgment should not compete with the content.
- **Not hollow.** Warmth loses meaning when it's applied uniformly and automatically to everything. Reserve it for moments that deserve it — adding a substantial claim, completing a hard gap question, hitting a milestone.
- **Advocate framing.** The platform knows the candidate's value; it's helping them see it too. Phrases like "That's worth having on record." or "Good to capture — this is exactly the kind of thing that gets overlooked." feel like a knowledgeable ally, not a chatbot.

### Examples by context

| Trigger | Example response tone |
|---------|----------------------|
| User adds text experience | "Added. That kind of context is often what tips a decision." |
| User answers a hard gap enrichment question | "Good one to have on record — specifics like this are hard to reconstruct later." |
| User connects GitHub | "GitHub connected. Pulling your work history now." |
| First claim added to the repository | "This is the beginning of your record. It grows from here." |
| User hits a milestone (e.g., 50 claims) | "50 claims in your record. That's a lot of signal." |

Avoid:
- Emoji unless explicitly part of the product design language
- Superlatives ("incredible", "amazing", "awesome")
- Generic affirmations that could apply to literally anything ("Great!", "Nice work!", "Done!")

---

## Planned Capture Surfaces (in rough priority order)

### 1. Gap Enrichment Loop (highest priority — flywheel mechanism)

After generating a Tailoring, detect which job requirements lack strong coverage in the repository. Surface targeted follow-up questions. Questions should be:
- Specific to the gap ("The role emphasizes distributed systems — do you have an example of scaling a service under real load?")
- Not generic ("Tell me about your technical skills")

Answers become permanent, dated, sourced repository claims — not just inputs to the current Tailoring. The user should see the claim being added to their record as a result.

### 2. Quick-capture / text input

Low-friction surface for ambient capture. A user gets off a call and someone said something noteworthy. A PR gets merged. A hard problem gets solved. The capture surface needs to be reachable in seconds — not buried in a form.

Possible surfaces:
- A text field on the dashboard ("Add something to your record")
- SMS / WhatsApp integration (text Tailord, claim gets added asynchronously)
- A mobile-friendly quick-add screen

### 3. Commit/merge hooks (developer-native capture)

A merge to main is a claim: something shipped. A draft claim can be auto-generated ("Shipped [PR title] to [repo]") and queued for the user to confirm and annotate.

Implementation: GitHub webhook or CLI hook. User confirms/annotates in Tailord dashboard. Draft claims that go unconfirmed for 30 days can be surfaced as a batch ("You have 8 unconfirmed claims from the last month — want to review them?").

### 4. Coding agent session sidecar

The most ambitious capture surface. Observes Claude Code (or Cursor) sessions and generates draft experience claims from active technical work. What problem was being solved, what approach was taken, what shipped.

Not a passive read of JSONL files (like claudeconnect does as a one-time harvest) — a continuous feed that generates draft claims as work happens.

### 5. Peer and performance review signals

Structured, link-based forms sent to colleagues or managers. Short — designed to take under 3 minutes.

Design constraints:
- Reviewer experience must feel worthwhile, not like filling out a form for someone else's CV
- Responses should be attributed (real person, relationship to candidate, date)
- Candidate should not be able to edit the attributed content — sourced means sourced
- Reviewer should see a summary of what they're contributing to ("Sami is building a professional record and asked for a quick observation")

Strategic note: save this for when the repository has enough depth that the context feels real. Sending a testimonial request when someone has 3 claims and a basic resume upload may feel premature.

---

## Open Questions

- What is the data model for an atomic experience claim? (source, content, date, source_url, claim_type, confidence?)
- How do draft claims (from commit hooks, session sidecar) differ from confirmed claims in the repository and UI?
- How do we surface the repository's value on the profile/public page? Can employers or evaluators eventually see a sourced record, not just a generated document?
- Portability: should the repository be exportable? (Argument for: trust-building; "your data, your record." Argument against: switching cost. Probably should be exportable — the quality of the record is the lock-in, not the lock.)
