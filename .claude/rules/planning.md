---
description: Conventions for writing and updating planning documents
globs: planning/**
---

**Format:**
- Day headers: `## Day N — Title`
- Done: `- [x]` with past-tense description
- Deferred: `- [~]` with inline reason
- Pending: `- [ ]`

**Where things live:**
- `planning/` — architecture decisions, sprint plans, research. Safe to be public.
- `CLAUDE.md` — stable conventions Claude needs in every session.
- `planning/private/` — real user data, pricing, internal URLs, business strategy. Gitignored.

**Never write in tracked planning files:**
- Real email addresses (use `user@example.com`)
- Phone numbers
- `*.internal` URLs
- Real user names, feedback verbatim, or revenue figures
