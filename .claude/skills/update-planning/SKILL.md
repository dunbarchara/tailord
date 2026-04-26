---
name: update-planning
description: Update the active sprint plan to mark completed or deferred items.
---

Update the active sprint plan to reflect work just completed.

1. Identify the relevant planning doc in `planning/`
2. Find the section(s) matching the work just done
3. Mark items:
   - `- [ ]` → `- [x]` completed (past tense, add inline notes)
   - `- [ ]` → `- [~]` deferred (add inline reason)
4. Inline notes should capture: actual numbers (coverage %, line counts, migration IDs), filenames created/modified, and any deviations from the original plan and why
5. Do not rewrite the original item — annotate it. Keep additions concise.
6. Follow format conventions in `.claude/rules/planning.md`
