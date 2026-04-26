---
name: commit-message
description: Generate a commit message for the current staged changes.
---

Generate a commit message for the current staged changes.

1. Run `git diff --cached --stat` and `git log -5 --oneline` to understand scope and follow existing style
2. Draft a message:
   - Imperative subject line, lowercase, no period, ≤72 chars ("add", "fix", "update", "improve")
   - Optional body: what changed and why when non-obvious; key filenames or numbers worth noting
3. Present the message as a code block — do NOT run `git commit` unless explicitly asked
