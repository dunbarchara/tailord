# CLAUDE.md

## What This Project Is

**Tailord** generates structured, role-specific **Tailorings** — AI-produced documents that map a user's experience to a specific job description. It does not rewrite resumes generically. The core question it answers: *"Why is this candidate a strong fit for this role?"*

---

## Monorepo Structure

```
tailord/
├── frontend/    # Next.js 16 (App Router) — TypeScript
├── backend/     # FastAPI (Python) — LLM pipeline, job parsing
└── infra/       # Terraform — Azure (active) + AWS (inactive/legacy) + Cloudflare IaC
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
- **Deployment**: Azure Container Apps — `next.config.ts` uses `output: 'standalone'` for this reason. Do not add Vercel-specific packages or APIs.

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

## Cloud Portability

The app is **currently deployed on Azure** but is designed to switch providers with minimal code changes. Preserve this when making changes.

**What this means in practice:**
- App code must not import Azure or AWS SDKs directly — always go through the abstraction layer
- `StorageClient` (`backend/app/clients/storage_client.py`) is the storage abstraction; `AzureStorageClient` and `S3StorageClient` are the implementations. Add new providers here, not inline.
- Provider is selected at runtime via `STORAGE_PROVIDER` env var (`"azure"` or `"aws"`)
- Both `boto3` and `azure-storage-blob` are kept as dependencies so the same Docker image runs on either cloud
- The LLM client is already cloud-agnostic: OpenAI SDK with configurable `LLM_BASE_URL` works with OpenAI, Azure AI Foundry, Ollama, and any OpenAI-compatible endpoint
- Use **neutral naming** in API contracts and internal code — `storage_key` not `s3_key`, `storage_provider` not `azure_provider`

**What is intentionally provider-specific:**
- `infra/providers/azure/` — Terraform and bootstrap docs are expected to be Azure-specific
- `infra/providers/aws/` — kept for reference if switching back
- Azure-specific env vars (`AZURE_STORAGE_CONNECTION_STRING`, etc.) are implementation details behind the abstraction

**Never do:**
- Delete a storage provider implementation to "clean up" — keep both S3 and Azure clients
- Import `azure.*` or `boto3` directly in app code outside of `clients/storage_*.py`
- Use cloud-specific terminology in shared API contracts or DB fields

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

**Active provider: Azure** (`infra/providers/azure/`)

| Resource | Detail |
|----------|--------|
| Cloud | Azure |
| Compute | Azure Container Apps (frontend + backend, 0.5 vCPU / 1Gi each) |
| Container registry | ACR (`tailord`) |
| Database | Azure PostgreSQL Flexible Server (B_Standard_B1ms, v16) |
| Storage | Azure Blob Storage (`tailord-uploads` container) |
| Secrets | Azure Key Vault |
| DNS | Cloudflare (proxied CNAMEs → Container App FQDN) |
| Deploy workflow | `.github/workflows/deploy-azure.yml` |

Frontend port: **3000**. Backend port: **8000** (internal ingress only — not publicly exposed).

**Legacy provider: AWS** (`infra/providers/aws/`) — not active, kept for reference.
