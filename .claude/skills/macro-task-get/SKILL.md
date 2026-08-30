# Skill: macro-task-get

Load a specific Macro task into context and output a structured summary.

## Trigger

User says something like:
- `/macro-task-get`
- "get macro task https://macro.com/app/task/<id>"
- "show me the task for ..."
- "what's in task <id>"

## Steps

### 1. Identify the task

**If the user provides a URL** (`https://macro.com/app/task/<id>`):
- Extract the `<id>` directly from the URL
- Call `ReadMetadata` and `ReadContent` in parallel — no search needed

**If the user provides a task name:**
- Call `NameSearch` with the task name
- If multiple results, ask the user to clarify or provide the URL
- Once the ID is known, call `ReadMetadata` and `ReadContent` in parallel

### 2. Do NOT call `ListEntities`

Never scan all tasks. This skill is for targeted retrieval of a known or named task only.

### 3. Output a structured summary

Format the output as:

```
## [title]

**URL:** https://macro.com/app/task/<id>
**Type:** [type derived from title tag, e.g. feature / bug / chore]
**Status:** [status from metadata]
**Priority:** [priority from metadata, if set]
**Tags:** [comma-separated tag list]

### Goal
[Goal section content, verbatim or lightly condensed]

### Technical Details & Context
[Technical Details section content, verbatim or lightly condensed]
```

If a section is empty or missing, omit it from the output rather than showing a blank heading.

## Constraints

- Never call `ListEntities`
- Do not infer or hallucinate task fields — only output what `ReadMetadata` and `ReadContent` return
- Do not edit or modify the task — this skill is read-only
