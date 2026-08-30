# Skill: macro-task-create

Create a new Macro task for the Tailord project, enforcing title format, tag conventions, and required sections.

## Trigger

User says something like:
- `/macro-task-create`
- "create a macro task for ..."
- "add a task to macro for ..."

## Steps

### 1. Gather information (if not already provided)

Ask the user for:
- **What to build/fix**: a short description of the goal
- **Type**: one of `feature`, `improvement`, `bug`, `chore`, `spike`
- **Component**: what area this touches (e.g. `billing`, `tailoring`, `experience`, `backend`, `frontend`, `infra`, `auth`) — free-form, not a fixed set

If the user already provided enough context in their message, infer these without asking.

### 2. Construct the task

**Title format:** `[type] [component] Action Verb + Concrete Object`

Examples:
- `[feature] [tailoring] Add chunk-level confidence scoring`
- `[bug] [auth] Fix Google OAuth redirect on mobile`
- `[chore] [infra] Rotate ACR credentials in Key Vault`
- `[improvement] [experience] Deduplicate GitHub repo claims on re-sync`

**Tags (minimum 3, all required):**
- `#tailord` — always included
- `#type-tag` — matches the type: `#feature`, `#improvement`, `#bug`, `#chore`, or `#spike`
- `#component-tag` — free-form component descriptor: e.g. `#billing`, `#tailoring`, `#frontend`

**Body format:**

```markdown
## Goal

[1–3 sentence description of what this task accomplishes and why it matters. Written from the perspective of an engineer picking this up.]

## Technical Details & Context

[Only include context already known from the current session — the file or function mentioned, the behaviour described, the constraint noted. Do NOT search the codebase to populate this section. Leave empty if nothing specific is known; the deep dive happens when the task is fetched and worked on.]
```

**Keep it lightweight.** Task creation captures intent, not investigation. Enough detail to recall why it was created is sufficient. Do not read files, grep the codebase, or look up implementation details before creating the task.

### 3. Create the document

Use `CreateDocument` with:
- `documentName`: the formatted title
- `fileExtension`: `"md"`
- `isTask`: `true`
- `fileContent`: the markdown body

Tags are **not** a parameter of `CreateDocument` — apply them separately in step 4.

### 4. Apply tags

All stable tags are hardcoded — no `ListTags` call needed unless the component is new.

**Tag set `propertyDefinitionId`:** `019f666c-571a-7c30-9752-752550f8bdeb`

**Type tags (pick one):**
| Type | ID |
|---|---|
| `tailord` | `019f666c-57bc-738d-8f4e-ee663887036e` |
| `bug` | `019f8111-e36b-7fe9-9a1b-e691979c7403` |
| `chore` | `019f8118-0322-7e66-bfe0-89cc432854f4` |
| `feature` | `019f8118-4d06-7df9-a21d-0e758e8f7424` |
| `improvement` | `019f8118-95ca-7a33-9841-e0089a2af0af` |
| `spike` | `019f8118-df8a-7174-b8f4-4e62dd92965d` |

**Known component tags:**
| Component | ID |
|---|---|
| `tailoring` | `019f8111-e391-72fc-b1e0-a58cb7f4abc5` |

**Component tag resolution:**
1. If the component matches a known component above → use its ID directly. No API call needed.
2. If the component is **new** (not in the table above):
   - Call `CreateTag` with `label` = component name, `color` = `gray`
   - Add the new entry to the **Known component tags** table in this skill file so future calls skip the create step
3. Call `SetEntityProperty` with:
   - `entity_id`: the `documentId` from step 3
   - `entity_type`: `"document"`
   - `property_definition_id`: `019f666c-571a-7c30-9752-752550f8bdeb`
   - `add_option_ids`: `[tailord_id, type_tag_id, component_tag_id]`

### 5. Output the task URL

After creation, output:

```
Task created: https://macro.com/app/task/<id>
```

Use the `documentId` returned by `CreateDocument`.

## Constraints

- Never use the old `shark-*` / `concrete-*` / `gold-*` color tokens in descriptions
- Do not list hypothetical future requirements — only what is needed now
- Title must start with `[type]` — no exceptions
- Tags must always include `#tailord`, the type tag, and a component tag — all three are required
