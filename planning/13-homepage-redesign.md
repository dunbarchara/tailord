# Homepage Redesign

*Living document — expected to iterate many times as the product matures and we gather real user feedback.*

---

## What the Current Homepage Gets Wrong

- **Headline is too abstract.** "Understand how your experience fits any job — instantly" reads like a generic job-match tool. It doesn't communicate what the output actually is or what makes it different.
- **Step 3 undersells the product.** "Get a clear match narrative" is the most important step and the vaguest. The actual output — requirement-by-requirement scoring with personal advocacy statements and a tailoring document — is entirely invisible.
- **No visual.** A visitor has no idea what the product looks like before signing up. The product's output is genuinely distinctive and explains itself visually.
- **Differentiator is buried.** "Doesn't rewrite your resume or spam keywords" is a strong positioning statement hidden at the bottom as an afterthought.
- **"Built for serious job seekers"** is on every job platform ever built.
- **Two CTAs in the hero dilute each other.** "Try Tailord" and "Learn More" compete — pick one.

---

## Platform Value (What the Homepage Should Communicate)

The real product: *requirement-by-requirement job analysis scored against a specific candidate background, with a personal advocacy statement per requirement, and a tailoring document written in the candidate's voice.*

Three things worth naming clearly:

1. **It's specific, not generic.** This is about *this* job — not jobs in general. Every output is derived from a real job description matched against a real person's history.
2. **The output is concrete.** A scored analysis (Strong / Partial / Gap per requirement) + a written narrative. Not a percentage. Not a list of keywords.
3. **It respects the truth.** Partial matches are partial. Gaps are gaps. That's a trust signal — when something scores Strong, the candidate (and eventually a recruiter) can believe it. Honest representation of fit *is* the platform's differentiator.

---

## Positioning North Star

> *You have the experience. We'll show you how to prove it.*

This speaks to the real pain: candidates undersell themselves not because they lack qualifications but because they can't articulate the connection. Tailord doesn't manufacture qualifications — it surfaces and contextualizes what's already there.

Secondary positioning angle (for differentiator section):
> *Not keyword stuffing. Not a template. A real argument for why you belong in this role.*

---

## Headline Options

Ranked by preference:

1. **"You have the experience. We'll show you how to prove it."** — Most aligned with the platform's north star. Confident, candidate-empowering, implies specificity.
2. **"Know exactly where you stand before you apply."** — Removes anxiety, implies specificity, action-oriented.
3. **"The honest job match."** — Short, provocative, leads with the integrity differentiator.
4. **"Apply with evidence, not anxiety."** — Emotional resonance, speaks to imposter syndrome.
5. **"Your experience, mapped to every role you want."** — Focuses on output, less emotional.

---

## Subtext

Current:
> "Tailord analyzes your background and job postings to clearly explain why you're a strong candidate — and how to position yourself with confidence."

Proposed:
> "Tailord maps your background against any job description — requirement by requirement — and tells you where you're strong, where you're close, and how to make your case. No keyword stuffing. No generic templates. A real argument for why you belong in this role."

---

## Page Structure

### 1. Hero
- Headline (from options above)
- One tight subtext sentence
- Single primary CTA: **"Start your first tailoring"** (more specific than "Create your account" — names the action)
- Remove the secondary "Learn More" CTA

### 2. Product Preview *(most important section)*
- Show what the output actually looks like — the scored job posting analysis (Strong/Partial/Gap bars, advocacy blurbs per requirement) is visually unique and explains itself
- A screenshot or stylized mockup here does more than any paragraph
- Caption framing: something like *"Every requirement scored against your background — with a clear explanation of why"*
- **Current state:** Not yet implemented — blocked on having a polished enough UI to screenshot. Placeholder or stylized mockup acceptable for v1.

### 3. How It Works (3 steps)
- **Step 1:** "Bring your experience" — Upload your resume, connect GitHub, or add context in your own words.
- **Step 2:** "Paste a job posting" — Provide a URL. We extract what the role is really asking for.
- **Step 3:** "See exactly where you fit" — Every requirement scored. A tailoring document written in your voice. Ready to use in applications and interviews.

### 4. The Differentiator Block
- Lean into the anti-positioning with more conviction
- Proposed heading: *"Built to advocate, not to inflate"*
- Copy: *"Most tools stuff your resume with keywords and hope for the best. Tailord builds a specific, sourced case for your fit — grounded in what you've actually done. Partial matches are called partial. Gaps are called gaps. That honesty is what makes the strong matches mean something."*

### 5. Closing CTA
- Minimal — just a headline and button
- Proposed: *"Ready to see how you fit?"* + "Start your first tailoring"

---

## Future Sections (not yet implemented)

### Interactive demo on homepage
- Let a visitor paste a job URL directly on the homepage and see a preview analysis without signing up
- The most powerful conversion mechanism available — show the product before asking for commitment
- **Blocked on:** guest/anonymous analysis flow; likely a Day P4+ feature

### Share with a recruiter
- The public tailoring URL (`/u/{username}/{tailoring-slug}`) is genuinely differentiated — a structured, scored case for a candidate that a recruiter can read directly
- Worth a dedicated section once the sharing workflow is more polished
- *"Send your tailoring directly to a recruiter. They see your background, the role's requirements, and exactly how you match — all in one place."*

### Usage / social proof
- Real numbers once available: "X tailorings generated," "X job requirements matched"
- Testimonials with specifics — not "changed my job search" but "scored 8 Strong matches for a role I almost didn't apply to"

### Recruiter angle
- The platform has a natural second audience: recruiters receiving a tailoring via share link
- A future homepage variant or section could address this — *"Receive a structured case, not just a resume"*

---

## Component Notes

Current structure:
- `page.tsx` → `Header` + `Hero` + `FeaturesTailord` + `Footer`
- `Hero.tsx` — contains both the hero section and the 3-step "how it works" block
- `FeaturesTailord.tsx` — contains only "Built for serious job seekers" + CTA; thin and should be folded into a proper sections structure

Proposed structure:
- `page.tsx` → `Header` + `HeroSection` + `ProductPreview` + `HowItWorks` + `DifferentiatorSection` + `ClosingCTA` + `Footer`
- Each section is its own component, making iteration easier
- `Features.tsx` and `FeaturesTailord.tsx` can be deleted once replaced

---

## Iteration Log

| Version | Date | Change |
|---------|------|--------|
| v1 | 2026-03-28 | Initial rewrite — headline, subtext, 3-step flow, differentiator block, closing CTA |
