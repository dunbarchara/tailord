# Looking Forward

**Date:** 2026-04-28
**Context:** End of the Platform Maturity sprint (Days 11–15). Written as a forward-looking
perspective to inform the next sprint plan — not a task list, but a view of where we are,
what matters most, and what's on the horizon.

---

## Where We Are

The sprint plan from `09-platform-maturity.md` has been executed end-to-end. What that
delivered:

- **Single-responsibility LLM calls** — scorer, question writer, tailoring generator,
  and profile extractor are independent, each testable in isolation
- **Deterministic pre-selection** — vector similarity reduces LLM input context from
  the full profile to the top-K most relevant chunks; cosine math is deterministic, scoring
  is still LLM-driven
- **Measurable baseline** — eval harness with 5 fixtures, CI gate, pipeline hash, weekly
  shadow run; changes to matching behavior are now caught automatically
- **Chunks as first-class data** — `ExperienceChunk` and `JobChunk` rows are the source
  of truth for everything rendered and everything scored; `extracted_profile` blob is a
  legacy artifact now
- **Observability foundation** — `TailoringDebugLog` is writing; every generation is
  tagged with matching_mode, model, and duration

The system has good bones. It is not a proof of concept anymore — it is a measurable,
improvable platform. That's the material change from where we started the sprint.

---

## Immediate Hardening (Before Adding Features)

These are defects, gaps, or risks in things we've already built. They should be addressed
before expanding the product surface.

### 1. Branch protection on `main`
The CI gate currently gates nothing — without branch protection, PRs can merge without
CI passing. One GitHub UI setting: Repo Settings → Branches → require `pre-commit`,
`backend`, `frontend`, `eval-offline`. Without this, everything we built in Day 15 is
advisory rather than enforced.

### 2. Fixture calibration — fixture 02 and fixture 04
Two known issues in the eval baseline:

- **Fixture 02** (`expected_scores: [1, 1]`): the model consistently produces GAP for
  Kubernetes/Terraform, not PARTIAL. The system prompt rule "do not infer presence of a
  specific tool from experience with a related tool" is being applied correctly. The labels
  are aspirational, not accurate. Options: (a) accept current behavior and update labels to
  `[0, 0]`, or (b) soften the prompt rule with a "credit adjacent infrastructure experience"
  carve-out and verify against the gate. Either way, the disagreement should be resolved
  deliberately.

- **Fixture 04 vector mode**: work-authorization paragraph scores GAP (should be N/A).
  The SYSTEM prompt in `chunk_matching.py` doesn't explicitly list visa/work-authorization
  statements under `should_render=false`. Low-effort fix with measurable impact on fixture
  04. Add this and re-record.

### 3. GitHub race condition bug
If a user connects GitHub while their resume is still processing, `remove_github` sets
`status → "ready"` prematurely, and the experience processor then overwrites `github_repos`
with `None` on its stale read. Fix: the GitHub endpoint should not touch `status` when
`status == "processing"`; the experience processor should update only its own columns.
Latent data corruption bug — low reproduction frequency, high damage when it hits.

### 4. Legacy endpoint cleanup
`/parse`, `/generate`, and `job.py` (`/job`) are dead code. They create confusion when
reading the API and maintenance surface when dependencies change. Delete them along with
any frontend wiring. Fast and clean.

### 5. Rate limit soft warning
Users hit a hard block at 10 LLM triggers/hour with no prior signal. Add a soft warn at
8 triggers ("you're approaching your generation limit"). Small UX improvement, no
architectural change.

---

## Pipeline Quality — Next Round

These improve the matching pipeline's accuracy and efficiency. All are independently
measurable against the eval harness now that the gate exists. The eval results drive the
ship/don't-ship decision — not intuition.

### Section pre-filtering (high confidence, low effort)
Before chunk enrichment, classify sections by header: "What We Offer", "Benefits",
"Compensation", "Equal Opportunity", "About Us" → skip entirely. Zero LLM cost for
non-evaluable content, eliminates false GAP scores for perks and boilerplate without
touching the scoring prompt. Fixture 04 partially addresses this, but the broader pattern
is worth handling at the section level before chunks are even created.

### Targeted self-verification on GAP scores (medium confidence, medium effort)
For requirement chunks scored GAP — specifically those that look like YOE thresholds,
named technologies, or education requirements — run a lightweight second call: "Does the
candidate meet this? Yes/No and one sentence." Small context, binary output. Catches false
gaps that the vector retrieval missed because the relevant chunk wasn't in the top-K.
Gate the decision to run this on chunk type / content pattern, not on every GAP score.

### Fixture corpus expansion (ongoing)
Five fixtures is a thin baseline. The real expansion strategy: `TailoringDebugLog` is now
writing — in a few weeks of production usage, mine it for generations where the pipeline
struggled (high error_count, unusual batch count) and turn those real inputs into labeled
fixtures. This is the flywheel: production data → fixtures → better gate → better pipeline
→ better production data. The OPS.md documents this process.

### Prompt review — tailoring generation and profile extraction
Neither prompt has been systematically reviewed since early iterations. The tailoring
generator prompt in particular is doing heavy lifting and has not been touched since the
pipeline architecture changed significantly. A review session with a few test cases would
likely yield improvements. This is unstructured work — block time for it, don't put it
on a sprint.

---

## The Product Gap That Matters Most

The conversational enrichment loop.

We've built every underlying piece: gap detection, ExperienceChunk model, embeddings,
per-chunk inline editing. What we haven't built is the experience where a candidate
**reads a gap question, answers it, and watches their tailoring improve**. That loop is
the product's core differentiator — "Tailord didn't just analyze the job, it helped me
articulate experience I didn't know I had."

The infrastructure is there. The missing piece is the UX surface: a gap question flow
after tailoring generation that collects answers inline, persists them to Experience
(under `user_input` source), and either re-runs matching or triggers a regeneration.
The gap analyzer already generates questions per GAP chunk. Gap answers from the frontend
already update ExperienceChunks. The wiring between "question surfaced in tailoring detail"
and "answer feeds back into experience" is what's missing.

This should be the first significant feature sprint after hardening.

---

## Admin Observability (Short-Term)

`TailoringDebugLog` is writing. The data will exist. The missing piece is a surface in
the admin panel that doesn't require a DB query to answer: "what matching mode are
tailorings using, and how long are they taking?"

A single "Matching Quality" card in the admin dashboard — mode distribution, average
generation duration, recent error count — gives operational visibility without tools.
This is Day 16 work as documented in the sprint plan.

---

## Strategic Horizon

These are not near-term — they're worth keeping in view as the product matures.

### Privacy policy + terms pages → Notion public review
The Notion integration currently has a 10-workspace development limit. Removing it
requires Notion's manual review, which requires live privacy policy and terms pages.
These are table-stakes for any serious external usage and a prerequisite for the Notion
integration being a real selling point. Not complex to write — just needs to happen.

### Headless enrichment API (`POST /enrich`)
The business model. Job boards, ATS platforms, and agent frameworks call Tailord's
matching pipeline as a backend service. The B2C product is both a proof of concept and
the distribution channel. Prerequisite: B2C usage evidence to pitch with. The
architecture is ready for this — the matching pipeline is already API-driven,
`TailoringDebugLog` is the telemetry foundation, and `matching_mode` is an env flag.
What's missing is the partner auth layer, the async job ID + poll pattern, and the
`POST /enrich` contract. Design this with the eval pipeline in mind — partners will
want a quality SLA, and the eval gate is how we defend it.

### MCP server
Relatively low effort, high discoverability among Claude Code / Claude Desktop users.
Expose `tailord://experience`, `tailord://tailorings`, and a `generate_tailoring` tool.
Start read-only. The OpenAPI schema cleanup (from the remaining-work-dump) is a
prerequisite — the MCP tool definitions will mirror the API contract.

### Interactive tailoring format
Instead of a static generated document, re-render the job posting as the frame with
the candidate's evidence woven in per requirement. Each requirement annotated inline with
sourced experience and a STRONG/PARTIAL/GAP badge. The natural use case: live interviews
where both parties reference the same document. Nothing else does this. The chunk
architecture makes it structurally possible — the data is already requirement-level.
This is a 1–2 sprint investment but a genuinely differentiated surface.

---

## What I'd Prioritize in the Next Sprint

1. **Branch protection + fixture calibration** — the CI gate needs to actually gate, and
   the eval baseline should be accurate before we iterate against it
2. **Section pre-filter + fixture 04 prompt fix** — low-effort pipeline improvements that
   improve the baseline numbers
3. **Conversational enrichment UX** — the product gap that matters most; all the
   infrastructure is in place
4. **Admin observability card** — completes the Day 15 deferred item; TailoringDebugLog
   data will exist by then

The race condition bug and legacy cleanup can be folded into any sprint as housekeeping.
Privacy/terms pages should happen before the Notion public review submission — worth
timboxing a session to just write them.
