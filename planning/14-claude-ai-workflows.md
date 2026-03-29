# Claude Code & AI Workflow Expansion

*Practical guide for getting more out of Claude Code on this project — and for building deeper fluency with AI-native development.*

---

## Where We Are Now

Currently using Claude Code in a fairly basic mode: chat-driven edits, a single project-level CLAUDE.md, and auto memory. This is a solid foundation but leaves a significant amount of capability on the table. The sections below go roughly in order of leverage — start at the top.

---

## 1. Path-Specific CLAUDE.md Rules

**What:** Claude Code supports a `.claude/rules/` directory where each file can declare `paths:` frontmatter. Rules only load when Claude is working with matching files — so backend rules don't pollute frontend context and vice versa.

**Why this matters here:** Tailord is a monorepo. The frontend and backend have very different conventions, and the current single CLAUDE.md is already long. Splitting reduces context waste and improves adherence.

**Implementation:**
```
.claude/rules/
├── frontend.md        # paths: "frontend/**"
├── backend.md         # paths: "backend/**"
├── api-contracts.md   # paths: "frontend/src/app/api/**"
└── infra.md           # paths: "infra/**"
```

Each file is a focused, short set of rules for that context. The main `CLAUDE.md` becomes a lightweight orientation doc.

**Rule:** Keep each rules file under 100 lines. Specific beats general — "use `proxyToBackendWithUser` for authenticated routes" beats "follow API conventions."

---

## 2. Hooks — Automation at the Tool Level

**What:** Shell commands (or prompts, HTTP calls, agents) that fire automatically at lifecycle events: before a tool runs, after it completes, when the session stops, etc.

**Why this matters here:** Hooks turn Claude Code from a chatbot into a system that enforces your workflow automatically — without you having to remind it.

**High-value hooks for this project:**

```json
// .claude/settings.local.json (not committed — personal automation)
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit",
        "hooks": [{
          "type": "command",
          "command": "cd frontend && npm run lint --quiet 2>&1 | head -20"
        }]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{
          "type": "command",
          "command": "~/.claude/hooks/block-destructive.sh"
        }]
      }
    ]
  }
}
```

**Specific hooks worth building:**
- **After any frontend Edit:** run `tsc --noEmit` — catch type errors before they compound
- **After any backend Edit:** run `ruff check` / `mypy` on changed file
- **Before Bash:** block `git push --force`, `DROP TABLE`, `rm -rf` patterns — exit code 2 shows the block reason to Claude
- **After alembic migration files are created:** remind Claude to also update `CLAUDE.md` model docs if schema changed

**Start minimal.** One hook that auto-lints after edits saves more context than five hooks you configure and forget.

---

## 3. Skills — Reusable Workflows

**What:** Prompt-based workflows stored as markdown files in `.claude/skills/`. Invocable with `/skill-name` or automatically by Claude when the description matches.

**Why this matters here:** Repetitive tasks (creating an API endpoint, writing a migration, generating a new component) follow the same pattern every time. A skill encodes that pattern once.

**Skills worth building for Tailord:**

```
.claude/skills/
├── new-api-route/
│   └── SKILL.md   # Scaffold a new Next.js API route proxy with auth
├── new-backend-endpoint/
│   └── SKILL.md   # FastAPI endpoint + Pydantic schema + router registration
├── alembic-migration/
│   └── SKILL.md   # Generate migration, verify down_revision chain, remind to test
├── new-component/
│   └── SKILL.md   # New React component following design token conventions
└── security-audit/
    └── SKILL.md   # OWASP checklist for a given file or route
```

**Example — `new-api-route` skill:**
```yaml
---
name: new-api-route
description: Scaffold a new Next.js API proxy route with auth. Use when creating API routes.
allowed-tools: Read, Glob, Write
---

Create a new Next.js API route at the path specified in $ARGUMENTS.

1. Read @frontend/src/lib/proxy.ts to understand proxyToBackend vs proxyToBackendWithUser
2. Determine if the route needs auth (user-scoped = proxyToBackendWithUser)
3. Read an existing similar route as reference
4. Scaffold the new route following that pattern exactly
5. Confirm the backend endpoint it proxies to exists
```

The key insight: a skill is just instructions Claude already knows, codified so you never have to repeat them.

---

## 4. Subagents — Specialized Expertise

**What:** Custom AI assistants with their own system prompt, tool restrictions, model, and persistent memory. Invoked with `@agent-name` or automatically when Claude delegates.

**Why this matters here:** Different parts of the codebase need different expertise. A backend agent knows FastAPI, SQLAlchemy, and Alembic. A frontend agent knows Next.js App Router, Tailwind v4, and our component patterns. Having them as discrete agents keeps context clean and improves output quality.

**Agents worth creating:**

```
.claude/agents/
├── backend.md     # FastAPI, SQLAlchemy, Alembic, LLM pipeline expert
├── frontend.md    # Next.js App Router, React, Tailwind v4, our design system
└── reviewer.md    # Security + correctness review — read-only, no edits
```

**Example — `reviewer` agent:**
```yaml
---
name: reviewer
description: Security and correctness reviewer. Use before merging significant changes.
tools: Read, Grep, Glob, Bash(git diff *)
model: sonnet
permissionMode: dontAsk
---

You are a senior security and correctness reviewer. You do not edit code — only report.

Review for:
- Auth bypass risks (missing session checks, X-User-Id spoofing)
- SQL injection (raw string queries, f-strings with user input)
- Prompt injection (user content in system prompts)
- SSRF (user-controlled URLs passed to Playwright/requests)
- N+1 queries, missing indexes
- Unhandled error cases that leak stack traces

Return a markdown report grouped by severity: Critical, High, Medium, Low.
```

**Agent memory:** Add `memory: project` to let agents accumulate knowledge about the codebase between sessions — what patterns you use, what bugs you've hit, what to avoid.

---

## 5. MCP Servers — Direct Tool Access

**What:** External integrations Claude can call as tools. Configured in `.mcp.json`. Hundreds of pre-built servers exist for databases, APIs, cloud providers, etc.

**High-value MCPs for this project:**

**GitHub MCP** — Let Claude create PRs, view issues, check CI status, read PR comments without you copy-pasting:
```bash
claude mcp add --transport http github https://api.githubcopilot.com/mcp/v1 \
  --header "Authorization: Bearer $GITHUB_TOKEN" --scope project
```

**PostgreSQL MCP** — Let Claude query the database directly to debug issues or verify migrations ran correctly. Invaluable for iterating on LLM pipeline output stored in the DB.

**Filesystem MCP** — Broader file access beyond the project directory when needed.

**Note:** Be deliberate about which MCPs you add to `.mcp.json` (shared with team via git) vs your personal `~/.claude.json`. Database MCPs with real credentials should never go in committed config.

---

## 6. Plan Mode — Safer Large Changes

**What:** A read-only mode where Claude researches and proposes a plan before making any edits. Claude can read, grep, and explore — but cannot write until you approve.

**When to use:** Any refactor that touches more than 3–4 files. Schema changes. Any time you're unsure what the blast radius is.

```bash
# Start in plan mode
claude --permission-mode plan

# Or switch mid-session with Shift+Tab
# Or prefix a prompt:
/plan Refactor the tailoring generation pipeline to support streaming per-section output
```

The proposal is written to a file you can review, edit, and approve. This is the right workflow for the P1–P3 platform hardening days — explore first, edit second.

---

## 7. The Agent Tool — Parallelism

**What:** The `Agent` tool (already available in our sessions) lets Claude spawn specialized subagents for parallel work. When two tasks are genuinely independent, running them in parallel halves the time.

**Where you're already using this:** The session summary mentions it. But you can also explicitly ask for parallel execution.

**Patterns worth knowing:**

```
"Run the security audit on the backend API routes and the frontend proxy
routes in parallel, then summarize the findings."

"While you write the new migration, have another agent update the
TypeScript types and API response schemas."
```

**When NOT to parallelize:** When tasks share state (editing the same file, dependent DB migrations) — sequential is safer.

---

## 8. AI Development Learning Opportunities (Specific to Tailord)

Since part of the goal is building AI development fluency, here are the highest-leverage learning areas within this project:

### LLM Pipeline Design
Tailord already has a real multi-step LLM pipeline: scrape → extract → match → generate → chunk-score. This is exactly the kind of orchestration that matters in production AI systems. Key things to go deeper on:
- **Structured output with Instructor/`llm_parse`** — understand how the retry and validation wrapper works under the hood
- **Prompt engineering discipline** — our chunk matching prompts have evolved organically; understanding what changes move scores and why is a real skill
- **Token budgeting** — the BATCH_SIZE discovery (advocacy_blurb doubles tokens) is a microcosm of a real production problem; the P3 `llm_parse_with_retry` work will be a good exercise in making pipelines robust

### Evaluation
Currently we evaluate LLM output by eyeballing it in the Analysis tab. The natural next step is:
- Define what "good" looks like per call site (e.g., advocacy blurbs: specific evidence, respects score, no "the candidate" phrasing)
- Build a small eval set: a handful of job descriptions + profiles with known expected outputs
- Run the pipeline against the eval set after prompt changes to catch regressions
This is how production AI teams work. Even 5 test cases is better than zero.

### Retrieval / Context Management
The `_format_sourced_profile` function is basically building a context window for the LLM. Understanding how to represent structured data (resume, GitHub, user input) compactly and usefully for different task types is a core LLM engineering skill. The "compact prose vs JSON dump" item in P3 is a good exercise.

### Claude API / Agents SDK
Since you're building on top of OpenAI-compatible endpoints, the jump to using Claude directly (for future features, or for evaluation tooling) is small. The Claude API's tool use, structured output, and multi-turn patterns map directly to what you're already doing.

---

## 9. The Frontend-Design Plugin (from the tip)

The tip mentioned:
```
/plugin install frontend-design@claude-code-plugins
```

This is a Claude Code plugin specifically for frontend/CSS/design work. Install it and it likely provides:
- Skills for generating Tailwind components
- Skills for design review and accessibility checks
- Possibly a design system documentation skill

Worth installing and exploring — given the Mintlify design matching work ahead, a plugin purpose-built for frontend design could be directly useful.

```bash
/plugin marketplace add anthropics/claude-code
/plugin install frontend-design@claude-code-plugins
```

---

## Priority Order

If you implement one thing from this doc at a time:

| Priority | Feature | Time to implement | Leverage |
|----------|---------|------------------|---------|
| 1 | Path-specific rules (`.claude/rules/`) | 1 hour | High — cleaner context immediately |
| 2 | Post-edit lint hooks | 30 min | High — catches errors before they compound |
| 3 | `new-api-route` + `new-backend-endpoint` skills | 1 hour | High — most repeated task |
| 4 | `reviewer` subagent | 30 min | High — enforces security review |
| 5 | GitHub MCP | 30 min | Medium — reduces context-switching |
| 6 | Plan mode habit | 0 min | High — just use Shift+Tab before big changes |
| 7 | frontend-design plugin | 15 min | TBD — explore it |
| 8 | Eval set for LLM pipeline | 2–3 hours | High — pays dividends over every iteration |
