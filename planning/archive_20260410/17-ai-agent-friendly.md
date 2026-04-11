# AI Agent Friendliness — Platform Design for Humans, Developers, and Agents

*Exploratory direction — the shape of this is still open*

---

## The Goal

Build Tailord so it works well for three distinct audiences at once:

1. **Human users** — the job seeker using the dashboard
2. **Developers** — integrating or extending Tailord programmatically (API consumers, the B2B path)
3. **AI agents** — LLMs or agent frameworks that want to read, query, or act on Tailord data

The third audience is the new and interesting one. Most products are not designed with agents in mind — the data is buried in rendered HTML, the API (if it exists) requires human-readable auth flows, and there's no structured way for an agent to know what operations are available. Designing for agents from the start is a different kind of engineering decision, and it's becoming a meaningful skill as agent-native tooling matures.

---

## What "AI Agent Friendly" Likely Means in Practice

### 1. Structured, Semantic Data at Public URLs

The public tailoring view (`/u/{slug}/{tailoringSlug}`) already exposes useful data. The question is: is it accessible in a form an agent can reason about without parsing HTML?

- A `?format=json` query param (or `Accept: application/json` header) returning the same data as structured JSON — chunks, scores, advocacy blurbs, company, role — would make the public tailoring readable by any agent that can make HTTP requests.
- Same for the public profile (`/u/{slug}`): structured JSON of extracted experience, skills, work history.
- This is low-effort and high-leverage. The data already exists; it's about surface area.

### 2. An MCP Server

[Model Context Protocol](https://modelcontextprotocol.io/) is the emerging standard for giving AI agents structured access to external tools and data. Claude Code, Claude Desktop, and a growing list of agent frameworks support MCP natively.

A Tailord MCP server could expose:

**Resources (readable data):**
- `tailord://experience` — the user's full extracted profile (resume, GitHub, additional context)
- `tailord://tailorings` — list of tailorings with status, company, role
- `tailord://tailoring/{id}` — full tailoring including chunks, scores, advocacy blurbs
- `tailord://analysis/{id}` — the fit analysis for a specific tailoring

**Tools (callable actions):**
- `generate_tailoring(job_url)` — trigger a new tailoring generation
- `get_fit_analysis(tailoring_id)` — return the structured analysis
- `export_to_notion(tailoring_id, view)` — trigger a Notion export

The concrete use case: a Claude Desktop or Claude Code user installs the Tailord MCP server, and can then say *"look at my Tailord profile and tell me which of these three job postings I should prioritize"* — without leaving their agent environment. The agent reads structured experience data, reads each tailoring's chunk scores, and reasons across all of it.

This is a natural extension of what Tailord already does. It's not a new product — it's an API surface that makes the existing product accessible to agents.

### 3. A Well-Specified OpenAPI Schema

The FastAPI backend auto-generates an OpenAPI schema at `/docs` and `/openapi.json`. Making this schema clean, well-described, and stable is the minimum required for any developer (human or agent) to use the API reliably.

- Consistent response shapes (no ad-hoc dict returns where a typed model should be)
- Meaningful operation IDs (not `post_tailorings_tailorings_post`)
- Documented error codes and their meanings

This is also the prerequisite for Path 2 (B2B platform pitches) — any serious integration partner will look at the OpenAPI schema first.

### 4. Webhooks (Longer Term)

Agent-driven workflows often need to react to events asynchronously — "when a tailoring is ready, send me the result" rather than polling. Webhooks are the standard mechanism.

- `tailoring.ready` — generation complete
- `tailoring.enriched` — chunk analysis complete
- `experience.processed` — profile extraction complete

Not needed yet, but worth keeping in mind when designing the event model.

---

## What's Still Open

The honest answer is: **it's not fully clear what "AI agent friendly" implies for a product like Tailord until you try to build something that uses it agentically.**

The best way to learn is to be the agent-side developer first:

1. Try to write a script or agent prompt that uses Tailord data to answer a question (e.g. *"given my Tailord experience profile and this job description, what's my weakest area?"*)
2. Notice where the friction is — what data is hard to get, what format doesn't work, what auth is in the way
3. Fix those specific gaps

The MCP server is probably the highest-signal starting point because it forces you to design a clean, tool-oriented interface to the product — and because it's directly useful for personal workflows (using Claude to reason over your own tailoring data).

---

## Why This Is Worth the Investment

- **Developer portfolio signal**: building for agents is a forward-looking skill that most developers haven't practiced yet. An MCP server is a concrete, explainable artifact — "I designed the data model and tool interface for an AI agent to query and act on my platform."
- **Product differentiation**: most job tools are black boxes. A Tailord that's natively queryable by agents is a different kind of tool — one that extends into whatever workflow the user already lives in (Claude, Cursor, whatever agent runtime they use).
- **Personal usefulness**: the most immediately useful version is being able to query your own experience and tailoring data from within a Claude conversation without switching contexts.

---

---

## Headless Enrichment Layer — Job Board Integration

*A distinct and higher-leverage B2B direction: Tailord as infrastructure, not product.*

### The Model

Job boards with user accounts already have the two inputs Tailord needs: a user's stored resume/experience, and a specific job posting. What they lack is the enrichment layer — structured scoring, advocacy blurbs, fit analysis.

The vision: a job board like Ashby, Greenhouse, or Lever could pass user context to Tailord's backend and get back enriched, structured data for any given job posting. The user never knows Tailord exists — Ashby surfaces the analysis in their own UI, in their own voice.

This is Tailord as an enrichment microservice. The platform retains its brand and UX; Tailord provides the intelligence.

### What This Requires

- **A backend-to-backend auth model**: the job board authenticates to Tailord's API with a partner API key; user context (resume text, structured experience) is passed per-request or stored as a Tailord profile tied to that user's identity in the job board's system
- **A clean request/response contract**: `POST /enrich` — body contains job URL (or raw job text) + user profile (or a reference to a stored profile); response returns chunks with scores, advocacy blurbs, and fit summary
- **No UI dependency**: the enrichment pipeline must work headlessly — no SSE stream a human watches, just a synchronous or async job that returns structured JSON
- **Webhooks or polling**: for async enrichment (which takes 30–45s), the partner either polls a job ID or receives a webhook when enrichment is complete

### Two Consumer Postures

The enrichment output can be surfaced in fundamentally different directions depending on who the job board chooses to show it to:

**Candidate-facing**: The job board surfaces enriched views to the applicant — "here's how you match this role, here's what to emphasize." The candidate sees the intelligence before or during their application. Tailord's role: score the candidate's profile against the posting before they apply.

**Recruiter/hiring-team-facing**: The job board surfaces enriched views to the hiring team, not the candidate. The candidate submits an application normally; the recruiter sees structured scoring and sourced claims for each applicant vs. the role — automated screening intelligence. The candidate never knows enrichment happened. Tailord's role: score submitted applications against the role spec after they apply.

Both postures use the same Tailord enrichment pipeline. The difference is entirely in how the job board chooses to surface the output. Tailord doesn't need to know or care which direction the data flows — that's the partner's product decision. This makes the integration model clean: one API, two very different product experiences.

The recruiter-facing posture is particularly interesting because it puts Tailord's intelligence in front of the people who act on it — hiring decisions — rather than adding it to the already-crowded candidate workflow.

### Why This Direction Is Compelling

- Tailord's differentiation (honest scoring, advocate-voice blurbs, requirement-level analysis) is most valuable *inside* the hiring workflow, not as a separate tool users have to remember to use
- Most job seekers don't seek out external tools — they use what's in front of them. Embedding Tailord's intelligence in the platform they're already on removes the activation barrier entirely
- From a business model perspective: API usage billed per enrichment call scales better than per-seat SaaS, and the partner handles all user acquisition
- This is the model Clearbit used for enrichment, or how Stripe powers payments inside other products — infrastructure that's invisible to end users but essential to the experience

### Design Constraint

The current generation pipeline is SSE-based and designed for a human watching a progress list. A headless mode needs:
1. A synchronous blocking endpoint (for short jobs) or an async job ID + poll/webhook pattern
2. The same enrichment pipeline, but without any SSE events or stage-tracking UI concerns
3. A stripped-down response schema — just the data the partner needs, no internal debug fields

This is achievable as a thin wrapper around the existing `_finalize_tailoring` + chunk enrichment pipeline.

---

## Suggested Starting Point

1. Clean up the OpenAPI schema (already partial — mostly naming/description work)
2. Add `?format=json` to public tailoring and profile pages
3. Build a minimal Tailord MCP server exposing `experience` resource + `get_fit_analysis` tool
4. Use it personally in Claude Desktop or Claude Code — let the friction from actually using it drive the next iteration

The MCP server doesn't need to be feature-complete to be useful. Start with read-only access to experience and tailoring data; add write actions (generate, export) once the data surface feels right.
