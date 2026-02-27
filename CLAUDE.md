# CLAUDE.md

## What This Project Is

**Tailord** generates structured, role-specific **Tailorings** — AI-produced documents that map a user's experience to a specific job description. It does not rewrite resumes generically. The core question it answers: *"Why is this candidate a strong fit for this role?"*

---

## Monorepo Structure

```
tailord/
├── frontend/    # Next.js 16 (App Router) — TypeScript
├── backend/     # FastAPI (Python) — LLM pipeline, job parsing
└── infra/       # Terraform — AWS + Cloudflare IaC
```

---

## Dev Commands

**Frontend** (from `frontend/`):
```
npm run dev      # Next.js dev server on :3000
npm run build
npm run lint
```

**Backend** (from `backend/`):
```
uv run uvicorn app.main:app --reload   # FastAPI dev server on :8000
```

---

## Stack

### Frontend
- **Next.js 16** (App Router), React 19, TypeScript strict
- **Auth**: NextAuth.js 4 — Google OAuth only, JWT sessions
- **Styling**: Tailwind CSS 4 with CSS variable-based design tokens (see Design System)
- **Icons**: Lucide React
- **No SWR/React Query** — native fetch in API routes
- **Deployment**: AWS ECS (EC2, `t3.small`) — `next.config.ts` uses `output: 'standalone'` for this reason. Do not add Vercel-specific packages or APIs.

### Backend
- **FastAPI** + Uvicorn, Python 3.14+
- **ORM**: SQLAlchemy + alembic migrations, psycopg driver
- **Database**: PostgreSQL
- **LLM**: OpenAI SDK with configurable `base_url` (currently local LLM at `localhost:1234/v1`)
- **Scraping**: Playwright (async headless Chrome) + BeautifulSoup4
- **Auth**: API key via `X-API-Key` header (`require_api_key()` dependency)

---

## Routing Architecture

```
frontend/src/app/
├── (marketing)/          # Public landing page
├── (auth)/login          # Public — Google sign-in
├── (auth)/register
├── (dashboard)/dashboard/
│   ├── layout.tsx        # Sidebar + header shell — keep stable
│   ├── page.tsx          # Dashboard home
│   ├── experience/
│   ├── jobs/
│   ├── tailorings/[tailoringId]/
│   ├── tailorings/new/
│   └── settings/
└── api/                  # API routes proxy to backend
    ├── auth/[...nextauth]/
    ├── parse/            # → POST backend /parse
    ├── analyze/          # → POST backend /analyze
    ├── profile/          # → POST backend /profile
    ├── job/              # → POST backend /job
    └── generate/         # → POST backend /generate
```

`middleware.ts` protects `/dashboard/*` via NextAuth `withAuth`. All backend routes require `X-API-Key`.

---

## Key File Paths

| File | Purpose |
|------|---------|
| `frontend/src/lib/auth.ts` | NextAuth config (Google provider) |
| `frontend/src/middleware.ts` | Route protection |
| `frontend/src/app/(dashboard)/dashboard/layout.tsx` | Dashboard shell |
| `frontend/src/components/ClientWrapper.tsx` | SessionProvider + ThemeProvider |
| `backend/app/main.py` | FastAPI app factory |
| `backend/app/config.py` | Pydantic Settings (env vars) |
| `backend/app/clients/llm_client.py` | OpenAI SDK wrapper |
| `backend/app/models/database.py` | SQLAlchemy ORM: `Profile`, `Job` |
| `backend/app/services/parser.py` | Job parsing orchestrator |
| `backend/app/core/scraper.py` | Playwright extraction |

---

## Data Models (Actual)

**Backend SQLAlchemy:**
- `Profile` — `id` (UUID), `summary` (Text), `raw_profile` (JSON), `updated_at`
- `Job` — `id` (UUID), `job_url` (String), `extracted_job` (JSON), `created_at`

**Conceptual domain model (in-progress):**
- `User` → has one `Experience`, has many `Tailorings`
- `Tailoring` → `jobTitle`, `company`, `jobDescription`, `generatedOutput`, timestamps

---

## Domain Concepts

- **Experience**: A user's professional background (resume upload, GitHub, manual input). Reusable across all Tailorings.
- **Tailoring**: An AI-generated, role-specific document derived from Experience + a job description. Persisted, viewable, regeneratable.
- **Dashboard** (`/dashboard`): The authenticated workspace. This route is a stable product surface — do not remove or rename it.

---

## Design System

Tailwind uses CSS variable tokens. Use these classes — not arbitrary values:

| Token group | Classes |
|-------------|---------|
| Brand | `brand-primary`, `brand-secondary`, `brand-accent` |
| Surfaces | `surface-base`, `surface-elevated`, `surface-overlay`, `surface-sunken`, `surface-border` |
| Text | `text-primary`, `text-secondary`, `text-tertiary`, `text-disabled`, `text-inverse`, `text-link` |
| Borders | `border-default`, `border-subtle`, `border-strong`, `border-focus` |
| States | `success`, `warning`, `error`, `info` (each has a `-bg` variant) |

The old `shark-*`, `concrete-*`, `gold-*` scales are commented out — do not use them.

Tone: structured, professional, clean. Favor whitespace. Strong typographic hierarchy. Subtle shadows over heavy borders.

---

## Constraints

**Never do:**
- Remove or rename `/dashboard` route
- Move auth checks into client-only logic — session validation belongs in server components/middleware
- Add Prisma — the backend already uses SQLAlchemy
- Introduce new npm/pip packages without necessity
- Flatten the `(marketing)` / `(auth)` / `(dashboard)` route group structure
- Use the old `shark-*` / `concrete-*` / `gold-*` color tokens

**Server vs Client components:**
- Server components are default in the App Router
- Only add `"use client"` for hooks, event handlers, or browser APIs
- Do not use global client-side state for things that can live in server state

**Naming:**
- Keep names domain-aligned: `TailoringCard`, `ExperienceSection`, `GenerateTailoringAction`
- Avoid: `DataItem`, `HelperThing`, `JobStuff`

---

## Infrastructure (`infra/`)

Managed with Terraform. Do not modify unless working on infra tasks specifically.

| Resource | Detail |
|----------|--------|
| Cloud | AWS (us-east-2) |
| Compute | ECS Service on EC2 (`t3.small`), ASG min 1 / max 4 |
| Container registry | ECR (`tailord`) |
| Networking | VPC with public + private subnets, NAT gateway |
| Load balancer | ALB → HTTPS only; HTTP redirects to HTTPS |
| TLS | ACM cert for `tailord.app` + `www.tailord.app` |
| DNS | Cloudflare (proxied CNAMEs) |
| Logs | CloudWatch `/ecs/tailord` (30-day retention) |
| State | S3 bucket `tailord-tf-state` + DynamoDB lock |

Container port is **3000** (frontend). The ECS task definition targets the frontend container — the backend is not yet containerized in this config.
