---
description: Next.js API route conventions for Tailord
globs: frontend/src/app/api/**
---

- User-scoped routes: `proxyToBackendWithUser` — injects X-User-Id/Email/Name headers.
- Public or non-user routes: `proxyToBackend`.
- Always validate `getServerSession(authOptions)` before proxying. Return 401 if no session.
- Routes are thin proxies only — no business logic, no JSON reshaping.
