# Skill: linear-issue-get

Load a specific Linear issue into context and output a structured summary.

## Trigger

User says something like:
- `/linear-issue-get`
- "get linear issue https://linear.app/..."
- "show me issue TAIL-123"
- "what's in issue TAIL-123"

## Steps

### 1. Identify the issue

**If the user provides a URL** (`https://linear.app/.../issue/...`) **or a short identifier** (e.g. `TAIL-123`):
- Extract the identifier directly
- Call the Linear MCP `get_issue` tool immediately — no search needed

**If the user provides a title/name:**
- Call `list_issues` with a `query` filter to find it
- If multiple results, ask the user to clarify or provide the identifier
- Once found, call `get_issue`

### 2. Do NOT call `list_issues`

Never scan all issues. This skill is for targeted retrieval of a known or named issue only. `list_issues` is only acceptable as a last resort to disambiguate a name — never to browse.

### 3. Output a structured summary

```
## [title]

**URL:** https://linear.app/...
**Identifier:** TAIL-123
**Type:** [type derived from title, e.g. feature / bug / chore]
**Status:** [status]
**Priority:** [priority, if set]
**Labels:** [comma-separated label list]

### Goal
[Goal section content]

### Technical Details & Context
[Technical Details section content]
```

If a section is empty or missing, omit it from the output rather than showing a blank heading.

## Constraints

- Never call `list_issues` — targeted retrieval of a known issue only
- Do not infer or hallucinate issue fields — only output what `get_issue` returns
- This skill is read-only — do not modify the issue
