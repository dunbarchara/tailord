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
docker compose up -d                   # PostgreSQL :5432 + Azurite blob storage :10000 (required before anything else)
uv run alembic upgrade head            # apply pending migrations
uv run uvicorn app.main:app --reload   # FastAPI dev server on :8000
```

**Quality checks** (from repo root — mirrors CI):
```
make check             # all checks
make check-backend     # ruff → bandit → pip-audit → pytest
make check-frontend    # eslint → build → jest → npm audit
make check-infra       # checkov on Terraform
```

**Local Claude Code hooks** (`.claude/settings.local.json` — gitignored, one-time setup):
Post-edit hooks run `tsc --noEmit` after frontend edits and `ruff check` after backend edits.
Script: `.claude/hooks/post-edit.py`. Hook config to add to `settings.local.json`:
```json
"hooks": { "PostToolUse": [{ "matcher": "Edit|Write", "hooks": [{ "type": "command", "command": "python3 .claude/hooks/post-edit.py" }] }] }
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
├── (marketing)/                   # Public landing page
├── (auth)/login                   # Google sign-in
├── (auth)/register                # Server component — redirects authenticated users
├── (dashboard)/dashboard/
│   ├── layout.tsx                 # Sidebar shell — keep stable
│   ├── page.tsx                   # Dashboard home (tailorings list)
│   ├── experience/                # My Experience (upload, GitHub, processing, edit)
│   ├── profile/                   # Profile preview + visibility controls
│   ├── settings/                  # Account settings (username slug, profile visibility)
│   ├── tailorings/new/            # New tailoring form (SSE stream)
│   └── tailorings/[tailoringId]/  # Tailoring detail (generation polling, sharing, Notion)
├── admin/                         # Admin panel — server component, isAdmin gate, user management
├── u/[slug]/                      # Public profile page (server component, OG meta)
├── t/[slug]/                      # Public tailoring page (shared link)
└── api/                           # Next.js API routes — thin proxies to FastAPI backend
    ├── auth/[...nextauth]/        # NextAuth Google OAuth
    ├── auth/notion/               # Notion OAuth initiation
    ├── auth/notion/callback/      # Notion OAuth callback
    ├── admin/users/               # → GET /admin/users
    ├── admin/users/[id]/approve/  # → POST /admin/users/{id}/approve
    ├── admin/users/[id]/revoke/   # → POST /admin/users/{id}/revoke
    ├── experience/                # → GET/DELETE /experience, PATCH /experience/profile
    ├── experience/upload-url/     # → POST /experience/upload-url
    ├── experience/process/        # → POST /experience/process (SSE)
    ├── experience/github/         # → POST/DELETE /experience/github
    ├── experience/user-input/     # → POST /experience/user-input
    ├── tailorings/                # → GET/POST /tailorings
    ├── tailorings/[id]/           # → GET/POST(regenerate)/DELETE /tailorings/{id}
    ├── tailorings/[id]/chunks/    # → GET /tailorings/{id}/chunks
    ├── tailorings/[id]/share/     # → POST/DELETE /tailorings/{id}/share
    ├── tailorings/[id]/export/notion/  # → POST /notion/export/{id}
    ├── tailorings/public/[slug]/  # → GET /tailorings/public/{slug}
    ├── users/                     # → GET/PATCH /users/me
    ├── users/public/[slug]/       # → GET /users/public/{slug}
    └── notion/                    # → DELETE /notion/disconnect
```

`middleware.ts` protects `/dashboard/*` and `/admin/*` via NextAuth `withAuth`. All backend routes require `X-API-Key`.

---

## Key File Paths

| File | Purpose |
|------|---------|
| `frontend/src/lib/auth.ts` | NextAuth config (Google provider, `session.user.id = token.sub`) |
| `frontend/src/middleware.ts` | Route protection (`/dashboard/*`) |
| `frontend/src/lib/proxy.ts` | `proxyToBackend` (public) + `proxyToBackendWithUser` (injects X-User-Id/Email/Name) |
| `frontend/src/types/index.ts` | Domain interfaces: `ExtractedProfile`, `ExperienceRecord`, `TailoringListItem`, etc. |
| `frontend/src/app/(dashboard)/dashboard/layout.tsx` | Dashboard shell |
| `frontend/src/components/ClientWrapper.tsx` | SessionProvider + ThemeProvider |
| `frontend/src/components/profile/ProfileSidebar.tsx` | Shared sidebar for `/dashboard/profile` and `/u/[slug]` |
| `backend/app/main.py` | FastAPI app factory |
| `backend/app/config.py` | Pydantic Settings (env vars) |
| `backend/app/clients/llm_client.py` | OpenAI SDK wrapper (configurable `LLM_BASE_URL`) |
| `backend/app/clients/storage_client.py` | Storage abstraction — `AzureStorageClient` / `S3StorageClient` |
| `backend/app/models/database.py` | SQLAlchemy ORM: `User`, `Experience`, `Job`, `Tailoring`, `LlmTriggerLog`, `TailoringDebugLog` |
| `backend/app/api/experience.py` | Experience CRUD, GitHub enrichment, SSE processing stream |
| `backend/app/api/tailorings.py` | Tailoring CRUD, SSE generation stream, sharing, Notion export |
| `backend/app/api/admin.py` | Admin user management — `require_admin()` dependency, approve/revoke |
| `backend/app/services/experience_processor.py` | Text extraction (PDF/DOCX/TXT) + background processing |
| `backend/app/services/tailoring_generator.py` | LLM tailoring generation — profile formatting, ranked match rendering |
| `backend/app/services/requirement_matcher.py` | Scores job requirements against candidate experience (STRONG/PARTIAL) |
| `backend/app/services/profile_extractor.py` | LLM profile extraction, bullet post-processing |
| `backend/app/prompts/profile_extraction.py` | Profile extraction prompt + temperature |
| `backend/app/core/scraper.py` | Playwright job page extraction |
| `backend/app/core/deps_user.py` | `get_current_user` FastAPI dep — upserts User from X-User-* headers |

---

## Data Models

**SQLAlchemy ORM (`backend/app/models/database.py`):**

- `User` — `id` (UUID), `google_sub` (unique, indexed), `email`, `name`, `preferred_first_name`, `preferred_last_name`, `pronouns`, `avatar_url`, `username_slug` (unique, nullable), `profile_public`, `status` (pending/approved), `is_admin`, Notion OAuth fields (`notion_access_token`, `notion_bot_id`, `notion_workspace_*`, `notion_parent_page_id`), `created_at`

- `Experience` — `id`, `user_id` (FK, 1:1), `storage_key` (blob key, nullable), `filename` (nullable), `status` (pending/processing/ready/error), `extracted_profile` (JSON — keyed by source: `"resume"`, `"github"`, `"user_input"`, etc.), `raw_resume_text`, `github_username`, `github_repos` (JSON), `user_input_text`, `error_message`, `uploaded_at`, `processed_at`, `last_process_requested_at`

- `Job` — `id`, `user_id` (FK), `job_url`, `extracted_job` (JSON), `created_at`; one-to-many with `JobChunk`

- `Tailoring` — `id`, `user_id` (FK), `job_id` (FK), `model` (LLM model name), `generated_output` (markdown), `generation_status` (pending/generating/ready/error), `generation_stage`, `generation_error`, `generation_started_at`, `generated_at`, `last_regenerated_at`, `enrichment_status` (pending/complete), `profile_snapshot` (formatted profile string passed to LLM — for debug), telemetry (`generation_duration_ms`, `chunk_batch_count`, `chunk_error_count`), sharing (`letter_public`, `posting_public`, `public_slug`), Notion export fields, `created_at`

- `LlmTriggerLog` — tracks LLM events per user for rate limiting; `event_type` (`tailoring_create`, `tailoring_regen`), `user_id`, `created_at`

- `TailoringDebugLog` — schema-only scaffold for future LLM telemetry (Level 3); no data written yet

**Relationships:** `User` → one `Experience`, many `Tailorings`; `Tailoring` → one `Job`; `Job` → many `JobChunk`

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
