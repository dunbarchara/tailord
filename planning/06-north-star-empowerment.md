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

## What This Is Not

- Not a chatbot. The conversational pattern is a metaphor for the interaction model, not a product requirement for a freeform chat interface.
- Not generic prompting. "Tell us more about yourself" is the failure mode. Every question must be grounded in a specific job requirement and a specific gap in the user's profile.
- Not interrupting the primary flow. Gap questions should appear after generation, not as a gate before it. Users get value first, then are invited to improve it.
