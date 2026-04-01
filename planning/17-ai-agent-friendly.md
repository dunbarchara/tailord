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

## Suggested Starting Point

1. Clean up the OpenAPI schema (already partial — mostly naming/description work)
2. Add `?format=json` to public tailoring and profile pages
3. Build a minimal Tailord MCP server exposing `experience` resource + `get_fit_analysis` tool
4. Use it personally in Claude Desktop or Claude Code — let the friction from actually using it drive the next iteration

The MCP server doesn't need to be feature-complete to be useful. Start with read-only access to experience and tailoring data; add write actions (generate, export) once the data surface feels right.
