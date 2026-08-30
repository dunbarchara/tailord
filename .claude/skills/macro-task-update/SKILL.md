# Skill: macro-task-update

Update an existing Macro task's content or metadata, preserving structure and only changing what was specified.

## Trigger

User says something like:
- `/macro-task-update`
- "update macro task ..."
- "edit the task at https://macro.com/app/task/<id>"
- "mark task X as done"

## Steps

### 1. Identify the task

**If the user provides a URL** (`https://macro.com/app/task/<id>`):
- Extract the `<id>` directly from the URL
- Do NOT call `ListEntities` or `NameSearch` — the ID is already known

**If the user provides a task name:**
- Call `NameSearch` with the task name to find it
- If multiple results, ask the user to clarify or provide the URL

### 2. Read what you need

Determine the change type from the user's request before reading:

- **Content change only** (Goal section, Technical Details): call `ReadContent` only
- **Metadata change only** (status, priority, tags): no read needed — use hardcoded IDs directly
- **Both**: call `ReadContent` only (`ReadMetadata` is not needed since all property IDs are hardcoded)

### 3. Determine what to change

Ask the user what they want to update if not already clear:
- **Content changes** (Goal section, Technical Details): use `EditDocument`
- **Metadata changes** (status, priority, tags): use `SetEntityProperty`
- **Both**: do both

### 4. Apply the changes

**For content edits (`EditDocument`):**
- Edit only the sections the user specified
- Preserve all other sections exactly as they are
- Do not reformat, reorder, or "clean up" sections that weren't touched

**For metadata changes (`SetEntityProperty`):**
- `entity_type` for tasks is always `"document"`
- Status `property_definition_id`: `00000001-0000-0000-0000-000000000002`; use `option_id` with one of:
  - Not Started: `00000001-0000-0000-0002-000000000001`
  - In Progress: `00000001-0000-0000-0002-000000000002`
  - In Review: `00000001-0000-0000-0002-000000000003`
  - Completed: `00000001-0000-0000-0002-000000000004`
  - Canceled: `00000001-0000-0000-0002-000000000005`
- Priority `property_definition_id`: `00000001-0000-0000-0000-000000000003`; use `option_id` with one of:
  - Low: `00000001-0000-0000-0003-000000000001`
  - Medium: `00000001-0000-0000-0003-000000000002`
  - High: `00000001-0000-0000-0003-000000000003`
  - Urgent: `00000001-0000-0000-0003-000000000004`
- For tag changes: use the hardcoded tag IDs from `macro-task-create/SKILL.md` — no `ListTags` call needed. Tag set `propertyDefinitionId`: `019f666c-571a-7c30-9752-752550f8bdeb`. Use `add_option_ids` / `remove_option_ids`.

### 5. Confirm the update

Output:
```
Updated: https://macro.com/app/task/<id>
```

List what was changed (e.g. "Updated Technical Details section", "Set status to done").

## Constraints

- Never call `ListEntities` — this skill is for targeted updates to a known task
- Never rewrite sections the user did not ask to change
- Do not infer status changes unless the user explicitly says to update the status
