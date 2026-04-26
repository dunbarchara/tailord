---
description: Next.js frontend conventions for Tailord
globs: frontend/**
---

- Server components are default. Only add `"use client"` for hooks, event handlers, or browser APIs.
- Design tokens only: `surface-*`, `text-*`, `border-*`, `brand-*`. No arbitrary Tailwind values, no `shark-*`/`concrete-*`/`gold-*`.
- Icons: Lucide React only. No new icon libraries.
- No Vercel-specific packages — deployment target is Azure Container Apps (`output: 'standalone'`).
- No global client-side state for things that can live in server state.
