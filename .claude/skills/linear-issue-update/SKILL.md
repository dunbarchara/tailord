# Skill: linear-issue-update

Update an existing Linear issue's content or metadata, preserving structure and only changing what was specified.

## Trigger

User says something like:
- `/linear-issue-update`
- "update linear issue ..."
- "edit the issue at https://linear.app/..."
- "mark issue X as done"

## Steps

### 1. Identify the issue

**If the user provides a URL** (`https://linear.app/.../issue/...`):
- Extract the issue identifier directly from the URL (e.g. `TAIL-123`)
- Do NOT call `list_issues` or any search tool — the ID is already known

**If the user provides an issue title or identifier (e.g. `TAIL-123`):**
- If it's a short identifier like `TAIL-123`, use it directly
- If it's a name/title, use the Linear MCP `list_issues` tool with a `query` filter to find it
- If multiple results, ask the user to clarify or provide the URL

### 2. Read current content

Call the Linear MCP `get_issue` tool with the issue ID to load current title, description, labels, and status before making any changes. This ensures edits are additive and preserve existing structure.

### 3. Determine what to change

Ask the user what they want to update if not already clear:
- **Description changes** (Goal section, Technical Details): update via `save_issue` with the `id` and updated `description`
- **Metadata changes** (status, priority, labels): update via `save_issue` with the `id` and relevant fields
- **Both**: do both in a single `save_issue` call

Note: `save_issue` with an `id` updates; without an `id` it creates.

### 4. Apply the changes

- Edit only the sections the user specified
- Preserve all other sections exactly as they are
- Do not reformat, reorder, or "clean up" sections that weren't touched
- Do not infer status changes unless the user explicitly says to update the status

### 5. Confirm the update

Output the issue URL and list what was changed (e.g. "Updated Technical Details section", "Set status to Done").

## Constraints

- Never call `list_issues` — this skill is for targeted updates to a known issue
- Never rewrite sections the user did not ask to change
- Do not infer status changes unless the user explicitly says to update the status
