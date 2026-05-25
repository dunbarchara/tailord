# Mock Data Review — Charles Dunbar Demo Tailorings

**Reviewed:** 2026-05-02
**Subject:** Three demo tailorings exported from live DB: Linear (SE), Stripe (Senior SE), Vercel (Staff Engineer)

---

## What the System Got Right

- **Generated letters are strong.** Specific, grounded in actual resume bullets, not generic filler. They read like a recruiter who did their homework, not a chatbot.
- **Most chunk scores are calibrated.** Score 0/1/2 maps correctly to gap/partial/strong in the majority of cases.
- **Multi-source attribution is accurate.** `experience_sources` correctly identifies which claims come from resume vs. GitHub. The `[Resume] [GitHub]` citation pattern in letters is accurate.
- **Partial question format is correct.** "At Microsoft, can you share..." is the right framing — it identifies the gap precisely and asks for a concrete example rather than a yes/no.
- **Gaps are real gaps.** The system doesn't hallucinate experience or manufacture fit. GraphQL, Electron, payments domain — these are genuinely absent.
- **Score 0 chunks have null blurbs.** The enforcement rule (no advocacy blurb on a gap) is correct.

---

## What Was Wrong (Pre-Fix)

### Critical Integrity Issues (wrong scores)

**1. Vercel — "8+ years of software engineering experience" (chunk `7b04f9e6`)**
Scored **2 (STRONG)**. Charles has 5.8 documented years (03/2018–04/2023). The rationale said "when considering the full profile evidence provided" — this is rationalization. Fixed to **0 (GAP)** with null blurb.

**2. Vercel — "Proven technical leadership across multiple teams" (chunk `0f80ee3e`)**
Scored **2 (STRONG)**. Building shared tooling and doing incident response across teams is *adjacent influence*, not formal multi-team technical leadership. An SE II at a company doesn't hold multi-team leadership authority. Fixed to **1 (PARTIAL)**.

**3. Vercel — "Experience with serverless or stateless compute patterns" (chunk `c8aa2f49`)**
Scored **1 (PARTIAL)**. Azure Container Apps is a managed container hosting platform, not a serverless/edge compute execution model. These are fundamentally different paradigms. Fixed to **0 (GAP)**.

**4. Vercel — "CDN, caching, or edge compute infrastructure design" (chunk `1c3947eb`)**
Scored **1 (PARTIAL)**. Kubernetes/Istio/Docker is container orchestration, not CDN design. The system confused "distributed infrastructure" with "edge networking." Fixed to **0 (GAP)**.

**5. Vercel — "Lead cross-functional technical initiatives from inception to production" (chunk `f5098d7f`)**
Scored **2 (STRONG)**. A UX/UI refresh after engineers left, shared tooling, and incident involvement are engineer-level cross-team contributions — not Staff-level initiative ownership with formal DRI accountability. Fixed to **1 (PARTIAL)**.

### Structural Issues

**6. Linear — GraphQL in both gaps and partials (near-duplicate questions)**
Chunk `28861749` ("GraphQL API design and implementation") was scored 0 and appeared in `gaps`. Chunk `447bc046` ("Contribute to the public GraphQL API and developer platform") was scored 1 and appeared in `partials`. Both generated near-identical questions. Fixed: removed from `gaps`, kept the more actionable `partials` entry.

**7. Stripe — 3 near-identical payments-domain questions**
The `gaps` entry for "Payments or financial services domain experience" plus two partials (`cfd2d2b1`, `d944b44c`) all asked essentially the same question: "Have you worked in payments?" Fixed: removed both redundant partials, kept only the `gaps` entry.

**8. Vercel — 11 partials was too many**
Three roadmap/architectural-direction partials (`1baa4038`, `e1d3f0a9`, `50779e84`) were near-redundant. Two duplicate mentoring entries (`e5039df0`, `4ef5a7ba`). Fixed: removed `1baa4038`, `e1d3f0a9`, `4ef5a7ba`. CDN and serverless entries moved to `gaps`. Final count: 8 partials, 4 gaps.

**9. `user_input_text` contained test data**
Value was `"[Gap answer — At Capital One, we are creating responsible and reliable AI ]: Test gap answer"`. Fixed to `null`.

**10. All chunks have `experience_source: null`**
This field is a dead legacy field, superseded by `experience_sources` (array). It's inert in the UI. Not changed (too noisy for 80+ chunks), but noted here for schema cleanup in a future migration.

### Letter-Level Polish

**11. Linear — "UI-adjacent delivery"** was corporate filler. Replaced with "hands-on UI contribution."

**12. Stripe — fourth section closing** was underselling the multiplier effect. Replaced "can support teammates while improving the way a team works" with a sharper framing about system-level and individual-level leverage.

**13. Vercel — closing paragraph positioned Charles as a ready Staff Engineer** when he's applying at stretch. Revised to acknowledge the trajectory and invite the conversation honestly rather than overclaiming.

---

## Platform Recommendations

### Prompt-Level

- **Enforce date math on experience requirements.** When a job requires "8+ years," the prompt or pre-processing should compute the candidate's documented experience span and fail hard rather than rationalize. The rationale "when considering the full profile evidence provided" is a red flag that the model is overclaiming.
- **Add a "paradigm check" guard for infrastructure requirements.** Container orchestration ≠ CDN ≠ serverless. These are distinct infrastructure domains. The prompt should require the model to verify that the experience domain *matches*, not just that it involves "infrastructure."
- **Distinguish influence from authority in leadership scoring.** "Built tooling used by multiple teams" is not the same as "held technical leadership authority over multiple teams." The prompt should distinguish adjacent/influence patterns from formal multi-team leadership roles.

### Deduplication

- **Gap analysis dedup rule.** If multiple job chunks map to the same underlying skill gap, generate one question — the clearest one — not one per chunk. The GraphQL/payments duplicates arose because multiple job sections mentioned the same domain.

### Calibration

- **Score 0 should be strict.** If there is zero evidence for a requirement (no direct match, no close transfer), the score should be 0. The current system sometimes scores 1 on "no explicit evidence, but adjacent" — this is fine for genuine adjacent cases, but not for domain mismatches like CDN vs Kubernetes.
- **Partial to strong threshold.** The LinkedIn-style "strong match" signal should require *direct* evidence of the specific skill, not just adjacent work that the model infers would transfer.

### Demo Data

- The Vercel tailoring is now honest about the stretch: Charles is a strong SE II applying for a Staff role. That's a useful demo signal — Tailord should help candidates understand their true fit position, not just cheerleading advocacy.
- The Linear tailoring is the best fit in the demo set — genuine match across most requirements with honest gaps on GraphQL and Electron. This should be the hero demo.
- The Stripe tailoring sits in the middle — strong technical match, single domain gap (payments). Good illustration of the "strong candidate, one gap" scenario.
