---
name: new-api-route
description: Create a new Next.js API route at `frontend/src/app/api/<path>/route.ts`.
---

Create a new Next.js API route at `frontend/src/app/api/<path>/route.ts`.

Pattern:
1. Import `proxyToBackendWithUser` (user-scoped) or `proxyToBackend` (public) from `@/lib/proxy`
2. Import `getServerSession` + `authOptions` from `@/lib/auth`
3. Validate session — return 401 if missing
4. Proxy to the matching backend path with the correct method
5. Return the backend response directly — no reshaping

Reference: `frontend/src/lib/proxy.ts` and `frontend/src/app/api/tailorings/route.ts`.
If it's a new backend route, also register it in `backend/app/main.py`.
