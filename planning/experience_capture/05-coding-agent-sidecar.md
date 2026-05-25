# Surface 05 — Coding Agent Sidecar

**`source_type`:** `mcp_agent`
**Status:** Planned
**Acquisition:** MCP server — `capture_session` tool called by AI coding agents (Claude Code, Cursor, etc.)
**Related:** `planning/28-experience-connectors.md` (section 4)

---

## 1. What It Captures

Coding agents (Claude Code, Cursor, Devin, etc.) assist with increasingly complex, consequential engineering work. They have session context that no other surface does: what was built, what decisions were made, which files changed, which technologies were touched — all described in natural language that the agent generated or the user provided.

The MCP sidecar captures that session context as professional experience. The user ends a session, the agent calls `capture_session`, and the accomplishment enters the review queue.

**What to capture:**
- What was built or changed (concrete output)
- Decisions made and their rationale (judgment signals)
- Technologies introduced or used in a meaningful way
- Problems solved and their scale/impact

**What not to capture:**
- Passive activity metrics ("agent ran 47 tool calls")
- Implementation details that don't reflect user judgment
- Work the user didn't meaningfully guide or review

This distinction matters for honesty and for quality: Tailord captures professional experience, not task throughput. A session where the agent did most of the work and the user approved the output is still valid signal — but the claim should reflect "I designed and shipped X" not "my agent typed X". See Honesty Principle below.

---

## 2. Metadata to Store

| Field | Value |
|---|---|
| `source_type` | `mcp_agent` |
| `source_ref` | `connector_id` (UUID of the ExperienceConnector row) |
| `claim_type` | `work_experience` for accomplishment claims; `skill` for technology signals |
| `group_key` | Repo name or project name if determinable from `repo_url` or session context; null otherwise |
| `date_range` | `session_date` from the tool input (ISO date); defaults to today |
| `technologies` | LLM-inferred from summary + explicit `technologies` field from tool input |
| `confidence` | `medium` by default (LLM-extracted from session summary); see Honesty Principle |
| `chunk_metadata` | `{session_date: "...", repo_url: "...", llm_model: "...", extraction_date: "...", agent_tool: "claude-code"}` |
| `source_urls` | File permalinks constructed from `modified_files` + `repo_url` if available |
| `plugin_connection_id` | FK to `ExperienceConnector` row |

---

## 3. The Honesty Principle

The MCP sidecar must only capture claims that genuinely reflect the user's agency and judgment. Two cases:

**Case A: User designed and built, agent assisted**
- Signal: high — the user made architectural decisions, the agent implemented details
- Confidence: `medium` (LLM-extracted from summary, but the user authored the session direction)
- Claim: "Designed and implemented X"

**Case B: Agent built, user reviewed and approved**
- Signal: still valid, but described accurately
- Confidence: `medium`
- Claim: "Reviewed and deployed X" or "Led agent-assisted development of X"

**What's not capturable:**
- Work the user delegated entirely without meaningful review
- Passive session presence ("I was working in the repo")

The `capture_session` tool input is a free-text summary — the user (or agent on the user's behalf) writes what happened. The LLM extraction pass should not inflate this. If the summary is vague ("misc work"), signal quality should be rated `low` and the ConnectorEvent skipped.

This is a values choice: Tailord represents candidates honestly. A profile inflated with agent-completion tasks that the user didn't meaningfully drive will perform worse at tailoring (lower cosine match quality on specific requirements) and risks misrepresenting the candidate.

---

## 4. Source URLs

Constructed from `modified_files` + `repo_url` if provided:

- If `repo_url` is a GitHub URL and files are repo-relative paths: `{repo_url}/blob/HEAD/{filepath}`
- If files are absolute local paths: store as-is in `chunk_metadata.local_paths` — human-readable provenance, not clickable links
- LLM identifies which files are most relevant to each claim (same ranking heuristic as PR enrichment)
- Store top 1–3 file URLs per claim

Note: `HEAD`-based links are not permanent (the file may change), unlike the commit-SHA permalinks used in surface 03. This is acceptable for agent sessions — the session captures a point-in-time claim; the exact file state is less critical than the PR-evidence use case. Use the commit SHA from `modified_files` metadata if the agent provides it.

---

## 5. MCP Tool Schema

```json
{
  "name": "capture_session",
  "description": "Save a summary of this work session to your Tailord experience repository. Tailord will extract experience signals and queue them for your review.",
  "inputSchema": {
    "type": "object",
    "required": ["summary"],
    "properties": {
      "summary": {
        "type": "string",
        "description": "What was accomplished this session — what was built, decided, or shipped. Be specific about outcomes and the user's role."
      },
      "modified_files": {
        "type": "array",
        "items": { "type": "string" },
        "description": "File paths modified (relative or absolute)"
      },
      "repo_url": {
        "type": "string",
        "description": "GitHub repo URL if applicable (used to construct source URLs)"
      },
      "technologies": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Explicit tech signals (optional; LLM also infers from summary and file paths)"
      },
      "session_date": {
        "type": "string",
        "description": "ISO date (e.g., 2026-05-24); defaults to today if omitted"
      }
    }
  }
}
```

**Tool output:**
```json
{
  "status": "queued",
  "preview_url": "https://tailord.app/dashboard/experience?review=<event_id>"
}
```

The agent can surface `preview_url` to the user immediately ("Session captured — review it here: …"). The review gate is the user's confirmation step.

---

## 6. Processing Pipeline

```
1. User configures MCP server in their agent tool (~/.claude/settings.json or equivalent):
   { "name": "tailord", "url": "https://api.tailord.app/mcp", "apiKey": "<personal_api_key>" }
2. Agent calls capture_session at end of session (user-triggered or post-session hook)
3. POST /mcp/capture — authenticated by X-API-Key + X-User-Id headers
   a. Validate session input
   b. Store raw payload in ConnectorEvent (extraction_status = "pending")
   c. Return preview_url immediately (202 response)
4. Background task:
   a. LLM signal-quality gate: same PREnrichment-style model
      - signal_quality == "low": mark ConnectorEvent as "skipped", skip_reason set
      - signal_quality != "low": proceed
   b. LLM extraction: experience_claims from summary + detected_stack from technologies + file paths
   c. Source URL construction from modified_files + repo_url
   d. Create candidate ExperienceChunk records (not yet committed — stored as JSON on ConnectorEvent)
5. User navigates to preview_url (or sees dashboard badge "N items to review")
6. Review card: raw summary, extracted claims, source links
7. User approves, edits, or rejects
8. Approved chunks embedded and persisted
```

---

## 7. Sensitivity Filters

- Strip colleague names from summary text before LLM extraction
- Flag internal project codenames — surface to user in review card: "This summary mentions [Codename X] — remove before saving?"
- Strip salary or compensation signals if present
- For private repos: `repo_url` pointing to a private GitHub repo is stored but treated as internal — source URLs generated from it are for the user's reference only, not shown on public tailoring pages

---

## 8. Dedup and Atomic Decomposition

**Session dedup**: a user might call `capture_session` at the end of every day. Multiple sessions on the same project produce overlapping skill signals. Standard dedup applies: cosine threshold check at ingest, route near-duplicates to review queue.

**Accomplishment dedup**: two sessions that both produced a React component are not the same accomplishment — they should not merge. The dedup threshold (0.92) should only collapse genuinely identical claim text, not thematically related work.

**Granularity**: each `experience_claims` item from the LLM extraction becomes one ExperienceChunk. Sessions that produced multiple distinct outcomes produce multiple chunks. Sessions with one main outcome produce one chunk.

---

## 9. Human Approval Gate

**Required.** No session data is persisted as ExperienceChunks until the user reviews and approves. The preview_url surfaced in the MCP tool response is the entry point for review. The dashboard badge "N items to review" provides a persistent reminder.

This gate is non-negotiable for v1. Agent sessions may contain unreleased product details, internal architecture, or employer-confidential context. The user must decide what enters their professional record.

---

## 10. Backend Entry Points

**MCP server entry (planned):**
```
POST /mcp/capture
Headers:  X-API-Key, X-User-Id
Request:  {
  summary: string,
  modified_files?: string[],
  repo_url?: string,
  technologies?: string[],
  session_date?: string
}
Response: 202 { status: "queued", preview_url: string, event_id: UUID }
```

**Connector registration (planned — shared with other connectors):**
```
POST /experience/connectors
Request:  { connector_type: "mcp_agent" }
Response: ExperienceConnector { id, api_key_hint, mcp_server_url }
```

---

## 11. Open Questions

1. **Automatic vs. user-triggered capture**: should the agent call `capture_session` automatically at end of session, or should the user explicitly say "capture this session"? Auto-capture risks ingesting sessions the user doesn't want recorded. User-triggered maintains intent clarity. Recommended: user-triggered for v1; offer a post-session hook as an opt-in setting.

2. **Confidence differentiation**: should "user designed, agent built" sessions have higher confidence than "agent built, user reviewed" sessions? The tool schema has no field for this distinction today. A simple boolean `user_led: true | false` could capture it.

3. **Agent identity**: should `chunk_metadata` record which agent tool was used (Claude Code vs. Cursor vs. Devin)? Useful for provenance but may create user-facing complexity.

4. **Rate limiting**: a power user with Claude Code running all day could call `capture_session` dozens of times. Rate limit per user per day (e.g., 10 sessions) to keep the review queue manageable.

5. **MCP server vs. direct API**: should Tailord implement the full MCP protocol or expose a simpler REST endpoint that agent tools call directly? MCP is more portable across agent tools; REST is simpler to implement. The `POST /mcp/capture` endpoint above is effectively REST — MCP protocol wraps it.
