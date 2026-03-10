# North Star: Empowerment-Driven Design

## The Core Philosophy

Tailord should help users bring out their experience and guide them through that process — not just process documents and return output. The guiding analogy is **Claude Code**: a tool that doesn't just execute tasks but moves through them conversationally, making the user more capable at every step. Users should leave an interaction with Tailord feeling like they've articulated something they couldn't have articulated alone, not just that a document was generated for them.

**The key shift in framing:** Tailord is not a resume tool. It is an experience articulation tool. The difference is that a resume tool takes what you have and formats it. An experience articulation tool helps you discover, surface, and communicate what you have — including things you didn't think to write down.

---

## The Empowerment Pattern

Every major user action should follow this shape:

1. **User provides input** (resume, job URL, GitHub)
2. **Platform generates output** (Tailoring, profile extraction)
3. **Platform reflects back** what it could and couldn't source — specifically, not generically
4. **Platform asks targeted follow-up questions** to fill the gaps
5. **User's answers enrich their Experience** and improve all future Tailorings

This is a conversation, not a form. Each question should be specific to this user and this role — never generic.

---

## Feature Vision: Post-Tailoring Gap Detection

After a Tailoring is generated, the platform has everything it needs to detect gaps: the job requirements and the candidate's profile are both in context. Instead of returning only the document, the system runs a second pass that identifies where claims could not be sourced and surfaces targeted prompts for the user to fill them in.

### Example interaction

> **Tailord:** Your Tailoring for Staff Engineer at Acme is ready.
>
> A few things in this job description we couldn't source from your profile — answering these would strengthen future Tailorings for similar roles:
>
> - The role emphasizes **performance optimization at scale**. You have React listed, but no specific examples. Do you have a project where you measurably improved performance? (Load time, bundle size, query latency — anything concrete.)
> - They require **experience leading cross-functional projects**. Nothing in your resume explicitly covers this. Have you led initiatives that involved non-engineering stakeholders?

The user answers inline. Those answers are stored under the `user_input` source key in their Experience profile and are immediately available to the next Tailoring.

### Technical shape

This is a new LLM task following the existing pattern:

```
app/prompts/gap_analysis.py        — system + user prompt
app/services/gap_analyzer.py       — calls llm_parse()
app/schemas/llm_outputs.py         — ProfileGap + GapAnalysis Pydantic models
```

Proposed output schema:

```python
class ProfileGap(BaseModel):
    job_requirement: str           # the specific requirement from the job
    question_for_candidate: str    # the targeted follow-up question
    context: str                   # why this matters for this specific role
    source_searched: str           # what source was checked (resume, github, etc.)

class GapAnalysis(BaseModel):
    gaps: list[ProfileGap]
    sourced_claim_count: int       # how many claims were successfully sourced
    unsourced_claim_count: int     # how many gaps were found
```

---

## Broader Design Implications

This philosophy should inform decisions across the platform — not just this one feature.

**Tailoring result page** should not be a dead end. It should show:
- The generated document
- What was successfully sourced (and from where)
- What couldn't be sourced, and specific questions to address it
- A way to answer those questions inline, without leaving the page

**Experience section** should feel progressive, not like a one-time upload. Each enrichment action (GitHub, direct input, question answers) should visibly improve the profile — users should be able to see their profile getting stronger.

**Dashboard** should surface actionable prompts, not just status. "Your profile is ready" is less useful than "Your profile is missing work samples — here are 2 questions that would improve your next Tailoring."

---

## Feature Vision: The Interactive Tailoring

A Tailoring today is a static document — a one-way argument for the candidate's fit. That serves the candidate well when preparing an application, but it doesn't serve the moment that actually matters most: the interview itself.

There is a second form a Tailoring could take.

Instead of rendering the candidate's experience as a standalone document, this format re-renders the **job posting** as the frame — with the candidate's experience woven into it. Each requirement, responsibility, or skill from the job description is annotated inline or on hover with sourced evidence from the candidate's profile: specific roles, projects, technologies, or answers they've provided. The job description becomes the shared interface; the candidate's experience becomes the layer on top of it.

### Why this matters in the interview context

Interviews are constrained by time. Both parties arrive with asymmetric information — the interviewer knows the role deeply, the candidate knows their own experience deeply — and the conversation has to bridge that gap in 45 minutes. The failure mode is common: a candidate has directly relevant experience that never surfaces because neither party happened to steer toward it.

An interactive Tailoring shared at the start of a call changes the dynamic. The interviewer can scan the job description they already know and immediately see, attached to each requirement, what the candidate claims as evidence — and choose where to dig in. The candidate isn't waiting to be asked the right question. The shared document becomes an agenda that neither party had to prepare from scratch.

### The shareable format

This is a natural extension of Day 4's public sharing layer. The same `/t/{slug}` URL that serves a static document today could serve either format — toggled at generation time or switchable on the public page. The interactive format is designed to be opened by both parties during a live conversation.

### Technical shape

The interactive Tailoring requires a structured mapping that the static format doesn't: each job requirement must be explicitly linked to sourced evidence rather than synthesized into prose. This implies a different generation pass and a different output schema:

```python
class RequirementAnnotation(BaseModel):
    requirement: str            # verbatim or paraphrased from job description
    category: str               # e.g. "Technical", "Leadership", "Domain"
    candidate_evidence: list[str]  # sourced claims — specific, not generic
    evidence_sources: list[str]    # "resume", "github:repo-name", "user_input"
    strength: str               # "strong" | "partial" | "gap"

class InteractiveTailoring(BaseModel):
    annotations: list[RequirementAnnotation]
    overall_fit_summary: str
```

The frontend renders this as an annotated job description — clean prose from the posting, with expandable or hoverable evidence panels per requirement. Gaps are surfaced honestly, consistent with the empowerment philosophy: a "gap" annotation with a follow-up question is more useful to both parties than silence.

---

## What This Is Not

- Not a chatbot. The conversational pattern is a metaphor for the interaction model, not a product requirement for a freeform chat interface.
- Not generic prompting. "Tell us more about yourself" is the failure mode. Every question must be grounded in a specific job requirement and a specific gap in the user's profile.
- Not interrupting the primary flow. Gap questions should appear after generation, not as a gate before it. Users get value first, then are invited to improve it.
