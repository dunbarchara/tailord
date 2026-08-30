# Skill: linear-issue-create

Create a new Linear issue for the Tailord project, enforcing title format, label conventions, and required sections.

## Trigger

User says something like:
- `/linear-issue-create`
- "create a linear issue for ..."
- "add an issue to linear for ..."

## Steps

### 1. Gather information (if not already provided)

Ask the user for:
- **What to build/fix**: a short description of the goal
- **Type**: one of `feature`, `improvement`, `bug`, `chore`, `spike`
- **Component**: what area this touches (e.g. `billing`, `tailoring`, `experience`, `backend`, `frontend`, `infra`, `auth`) — free-form, not a fixed set

If the user already provided enough context in their message, infer these without asking.

### 2. Construct the issue

**Title format:** `[type] [component] Action Verb + Concrete Object`

Examples:
- `[feature] [tailoring] Add chunk-level confidence scoring`
- `[bug] [auth] Fix Google OAuth redirect on mobile`
- `[chore] [infra] Rotate ACR credentials in Key Vault`
- `[improvement] [experience] Deduplicate GitHub repo claims on re-sync`

**Labels (minimum 3, all required):**
- `tailord` — always included
- type label — matches the type: `feature`, `improvement`, `bug`, `chore`, or `spike`
- component label — free-form component descriptor: e.g. `billing`, `tailoring`, `frontend`

**Description format:**

```markdown
## Goal

[1–3 sentence description of what this task accomplishes and why it matters. Written from the perspective of an engineer picking this up.]

## Technical Details & Context

[Only include context already known from the current session — the file or function mentioned, the behaviour described, the constraint noted. Do NOT search the codebase to populate this section. Leave empty if nothing specific is known; the deep dive happens when the issue is fetched and worked on.]
```

**Keep it lightweight.** Issue creation captures intent, not investigation. Enough detail to recall why it was created is sufficient. Do not read files, grep the codebase, or look up implementation details before creating the issue.

### 3. Resolve labels

All stable labels are hardcoded — no `list_issue_labels` call needed unless the component is new.

**Type labels (pick one):**
| Label | ID |
|---|---|
| `tailord` | `10ceaea1-51dc-4c2a-873e-e9bfadcaaa2b` |
| `bug` | `962c0c4d-ba9d-4c4b-a8f2-d9b2ca174ea9` |
| `chore` | `e485f20c-c1c6-471c-a820-c49fbb08c9ff` |
| `feature` | `59ff6b77-93ff-42f9-a516-deacb16c29e5` |
| `improvement` | `4e817a71-a15f-4a35-ab54-d1ba9671f948` |
| `spike` | `830ad847-6ca0-4262-af59-0a8d799caf6a` |

**Known component labels:**
| Component | ID |
|---|---|
| `tailoring` | `979b2030-9fce-47e4-bed8-36551d3735ae` |

**Component label resolution:**
1. If the component matches a known component above → use its name directly. No API call needed.
2. If the component is **new** (not in the table above):
   - Call `create_issue_label` with the component name, team `Tailord`, and color `#889096` (gray)
   - Add the new entry to the **Known component labels** table in this skill file so future calls skip the create step

### 4. Create the issue

Use the Linear MCP `save_issue` tool with:
- `title`: the formatted title
- `team`: the team name (e.g. `Tailord`)
- `description`: the markdown body
- `labels`: array of label strings

Note: `save_issue` handles both create (no `id`) and update (with `id`).

### 5. Output the issue URL

After creation, output the URL returned by the Linear MCP tool:

```
Issue created: https://linear.app/...
```

## Constraints

- Title must start with `[type]` — no exceptions
- Labels must always include `tailord`, the type label, and a component label — all three are required
- Do not search the codebase or read files before creating the issue
