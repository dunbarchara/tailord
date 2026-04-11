# Tailoring Philosophy — What We're Building and Why

## What a Tailoring Is

A Tailoring is a structured advocacy document generated on a candidate's behalf, written in direct response to a specific job posting. It is not a resume. It is not a cover letter. It is something new: a third-party advocate's argument for why a conversation between this candidate and this company is worth having.

The document addresses the company directly ("Hello GreenSpark,") and presents targeted evidence from the candidate's profile mapped to the requirements of the role. It is written as if by a knowledgeable third party who has reviewed both the job posting and the candidate's experience — not by the candidate themselves.

The goal of a Tailoring is not to get the candidate hired. It is to get them **a conversation**. That reframe governs every design decision in how Tailorings are structured, what they include, and how gaps are handled.

---

## The Format

### Opening

A Tailoring opens with a direct greeting and a single sentence that references the job posting. Get the reader into the content immediately — no preamble, no "the following is written on behalf of":

> Hello GreenSpark,
>
> Given the requirements described in your Software Engineer job posting, here are some reasons Charles would be a strong fit for the role.

The job posting reference is intentional — it signals that these arguments were built from what the company is actually looking for, not assembled generically. That signal is worth the extra words.

There is no document title. The greeting is the opener. A title stating "Application for Software Engineer at GreenSpark" is redundant — the greeting establishes context immediately and more naturally.

### Advocacy Sections

The body consists of thematic advocacy sections. Each section:

- Has a heading that leads with the **candidate's strength**, not the job requirement. `## Five years building cloud-native systems at scale` rather than `## 4+ years of professional software engineering experience`.
- Presents 2–4 sentences of specific, evidence-backed prose.
- Ends with a brief inline source tag: `[Resume]`, `[GitHub]`, or `[Direct Input]`. These anchor trust without interrupting the reading experience. In the rendered UI, these tags may link to the relevant section of the candidate's parsed profile.

### Candidate Brief

Education and contact information appear as a compact footer or header — not as a standalone advocacy section. Unless the candidate's education is itself a differentiator (notable research, non-traditional path, relevant thesis), a full section on a CS degree wastes space that should be used for advocacy.

Format:

> Charles Dunbar
> B.S. in Computer Science — University of Arizona
> charles@example.com

### Closing

A brief closing statement synthesises the argument and invites next steps:

> Charles's infrastructure and cloud platform experience maps closely to what GreenSpark is building, and his record of improving systems rather than just maintaining them is the kind of signal that's hard to fake.
>
> If you're interested in continuing the conversation, you can contact Charles here: charles@example.com

---

## The Advocacy Philosophy

### The document's job is to open a door

A hiring manager reading a Tailoring is deciding whether 30 minutes is worth their time — not whether to extend an offer. The bar is low. The risk calculus shifts: drawing attention to gaps in a document designed to open a door is almost always the wrong move. Lead with strength. Let the conversation surface the rest.

### Omit gaps; never fabricate

There is a meaningful difference between *omitting* a gap (correct) and *fabricating* strength where none exists (never acceptable). The platform must stay on the right side of that line at all times.

A Tailoring presents the best **truthful** version of the candidate for this specific role. Every statement must be grounded in evidence from the candidate's profile. If no evidence exists for a requirement, that requirement is omitted — not invented.

### Frame partial matches positively

When a candidate has adjacent but not exact experience, the Tailoring reframes it as foundation rather than gap. The underlying evidence is real; the framing is generous.

> "TypeScript is foundational to Charles's profile and frontend work is part of his background."

This is a positive statement derived from a real partial match. The hiring manager can draw their own conclusions. The platform's job is not to preemptively disqualify the candidate on their behalf.

### Address gaps only as a fallback — and frame them constructively

When a candidate genuinely lacks experience in an area that is central to the role, outright omission may read as conspicuous. In this case, the fallback is a brief, constructive acknowledgement that leads with adjacent evidence:

> "React specifically isn't named in Charles's current experience. The learning curve would be narrow given his TypeScript fluency and full-stack history — worth a first conversation."

This is honest, not damaging. It demonstrates self-awareness and frames the gap as a near-miss rather than a disqualification.

This fallback applies when:
- The requirement is prominent in the job posting (not a minor nice-to-have)
- The candidate has no strong signals elsewhere that indirectly address it
- Omitting it would feel dishonest to the candidate or misleading to the reader

---

## The Scoring Hierarchy and What Gets Into a Tailoring

The chunk matching pipeline produces scored signals that directly inform what appears in the Tailoring and how:

| Score | Meaning | Tailoring treatment |
|-------|---------|-------------------|
| 2 — Strong | Clear, direct evidence | Lead with it; give it space; most sections should be built on these |
| 1 — Partial | Adjacent or indirect evidence | Include; reframe positively using the specific adjacent evidence |
| 0 — Gap (with adjacent signals) | No direct match, but related experience exists | Brief positive reframe if space warrants; otherwise omit |
| 0 — Gap (no signals) | Genuine absence | Omit entirely, or fallback acknowledgement if requirement is central |
| -1 — N/A | Non-evaluable (perks, boilerplate, headers) | Never appears in Tailoring |

The Tailoring is not a requirements matrix. It does not need to address every chunk. It should address the highest-signal requirements first and build a coherent argument, not a checklist.

---

## What a Tailoring Is Not

- **Not a resume.** The resume lists; the Tailoring advocates.
- **Not a cover letter.** The cover letter is written by the candidate in first person. The Tailoring is written on their behalf in third person, by a system that has read both sides.
- **Not a requirements matrix.** Heading sections after job requirements ("4+ years of experience") makes the document feel like a form being filled in, not an argument being made.
- **Not an internal analysis tool.** The chunk analysis and match scores are infrastructure. The Tailoring is the user-visible output. These are separate surfaces with different audiences and purposes.
- **Not exhaustive.** A good Tailoring makes 3–5 strong arguments, not 10 weak ones. Quality of argument over quantity of coverage.

---

## Voice and Tone

- **Third person, advocating voice.** Written as if by a knowledgeable third party on the candidate's behalf.
- **Specific over generic.** "Owned AKS infrastructure for 40+ microservices" beats "experienced with Kubernetes." Every statement should be something only this candidate's profile could produce.
- **Confident, not superlative.** Avoid "exceptional," "outstanding," "world-class." Let the specifics carry the weight.
- **Concise.** A hiring manager should be able to read the full document in under two minutes. Favour density over length.
- **Honest.** The document's credibility depends on it. A single fabricated or overstated claim undermines everything else.

---

## The Experience-to-Tailoring Pipeline (Summary)

1. **Candidate profile** — sourced from resume, GitHub, and direct input; processed into structured signals with pre-computed YOE and role history
2. **Job posting** — scraped, cleaned, chunked by section; non-evaluable content stripped before it reaches the LLM
3. **Chunk enrichment** — each job requirement scored against the candidate profile (−1 / 0 / 1 / 2) with mandatory rationale
4. **Fast match** — a single call producing ranked requirement matches used to seed the tailoring prompt
5. **Tailoring generation** — the LLM returns a structured `TailoringContent` object (`advocacy_statements[]` + `closing`), not free-form markdown. Each `AdvocacyStatement` has `header`, `body`, and `sources`. The final document is assembled deterministically from this object plus known data (candidate name, email, education, company, job title).

### Why structured output

The LLM's job is reasoning and synthesis — selecting the right claims, writing compelling prose, choosing the right evidence. Format consistency is a product decision that should not vary between runs. Returning `TailoringContent` rather than free-form markdown means: heading capitalisation, source tag formatting, divider placement, and footer layout are all owned in code. Every Tailoring has exactly the same structure. The only variables are the content the model generates.

The Tailoring is the only user-visible output of this pipeline. Everything upstream exists to make this document as accurate and as strong as possible.

---

## Reference Example

*Charles Dunbar applying to Software Engineer at GreenSpark. Demonstrates: short intro, candidate-led headings, inline source tags, compact candidate brief footer, no React gap section.*

---

Hello GreenSpark,

Given the requirements described in your Software Engineer job posting, here are some reasons Charles would be a strong fit for the role.

---

### Five years of platform-scale infrastructure ownership

Charles spent the core of his career at Microsoft owning infrastructure for a globally distributed service running 40+ microservices on Kubernetes — working daily with AKS, Docker, Helm, and Istio across Azure cloud. He didn't inherit a stable system; he built and operated it through growth, provisioning regional deployments and maintaining reliability for a service with 35+ contributing engineers. `[Resume]`

### A record of improving systems, not just maintaining them

Beyond operating existing infrastructure, Charles consistently delivered improvements that compounded: overhauling CI/CD pipelines to triple deployment frequency, replacing a UI-tightly-coupled deployment architecture with a RESTful deployment engine, and developing internal tooling that democratised infrastructure operations across the team. His track record is one of leaving systems measurably better than he found them. `[Resume]`

### Technical leadership that scales with the team

Charles mentored junior engineers, coordinated incident response across multiple service teams and regions, and delivered structured weekly reporting to leadership — bridging technical depth and organisational communication. This combination appears consistently throughout his profile, not as an isolated mention. `[Resume]`

---

Charles's cloud platform experience and infrastructure depth map closely to what GreenSpark is building. If you're interested in continuing the conversation, Charles can be reached at charles@example.com.

---

*Charles Dunbar · B.S. Computer Science, University of Arizona · charles@example.com*
