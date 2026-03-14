# Tailord — Project Status

_Last updated: 2026-03-06_

---

## What Tailord Is

Tailord generates structured, role-specific **Tailorings** — AI-produced documents that map a user's professional experience to a specific job description. The core question it answers: _"Why is this candidate a strong fit for this role?"_

---

## Infrastructure

**Active provider: Azure (Canada Central)**

| Resource | Detail |
|---|---|
| Compute | Azure Container Apps — `tailord-frontend`, `tailord-backend` |
| Container registry | ACR (`tailordregistry`) |
| Database | PostgreSQL Flexible Server (`tailord-db`, v16, B_Standard_B1ms) |
| Storage | Azure Blob Storage (`tailorduploads`) |
| Secrets | Azure Key Vault (`tailord-kv`), managed identity (no credentials in env) |
| DNS | Cloudflare (proxied CNAMEs → Azure Container App FQDN) |
| TLS | Cloudflare Full (Strict) — Azure-managed cert for `tailord.app` bound via CLI |
| IaC | Terraform in `infra/providers/azure/` |

**Custom domain status:** `tailord.app` is live through Cloudflare Full (Strict). The domain verification TXT record and CNAME are managed by Terraform. The Azure managed cert was bound manually via `az containerapp hostname bind`.

**AWS infra (`infra/providers/aws/`):** Exists but is not the active provider. The frontend container definition there is missing all required env vars (`NEXTAUTH_URL`, `NEXTAUTH_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`). Do not apply this config without completing it first.

**Terraform state:** Remote in Azure storage backend.

---

## Application Stack

### Frontend — `frontend/`
- Next.js 16, App Router, TypeScript strict, React 19
- Auth: NextAuth.js v4, Google OAuth only, JWT sessions
- Styling: Tailwind CSS v4, CSS variable design tokens, shadcn/ui (New York style)
- Deployment: `output: 'standalone'`, port 3000

### Backend — `backend/`
- FastAPI + Uvicorn, Python 3.14+
- ORM: SQLAlchemy + Alembic migrations, psycopg driver
- Database: PostgreSQL
- LLM: OpenAI SDK, configurable `base_url` and model via env
- Storage: Azure Blob Storage in production (`STORAGE_PROVIDER=azure`)
- Auth: `X-API-Key` header required on all routes

---

## Auth Architecture

```
Browser → Cloudflare (HTTPS, Full Strict) → Azure Container Apps → Next.js (port 3000)
```

- **Provider:** Google OAuth only (`190481102513-g4d2b90oqr68v91qjpj0tee37oc90757`)
- **Strategy:** JWT sessions via NextAuth v4
- **Route protection:** `middleware.ts` uses `withAuth`, matcher `["/dashboard/:path*"]`
- **`pages.signIn: "/login"`** is set in both `authOptions` and `withAuth` options — required to prevent a redirect loop (`withAuth` → `/api/auth/signin` → `/login` → `withAuth` → ∞)
- **User identity:** `session.user.id` = Google `sub` from JWT token. Backend receives `X-User-Id` / `X-User-Email` / `X-User-Name` headers from the Next.js proxy layer
- **Authorized redirect URIs registered in Google Cloud Console:**
  - `https://tailord.app/api/auth/callback/google`
  - `https://tailord-frontend.mangosky-42677261.canadacentral.azurecontainerapps.io/api/auth/callback/google` (for direct Azure testing)

---

## API Route Security

All Next.js API routes (`/api/*`) are server-side proxies to the FastAPI backend. The API key is never exposed to the browser.

| Route | Session required | Notes |
|---|---|---|
| `POST /api/parse` | Yes | Proxies to `POST /parse` |
| `POST /api/analyze` | Yes | Proxies to `POST /analyze` |
| `POST /api/job` | Yes | Proxies to `POST /job` |
| `POST /api/generate` | Yes | Proxies to `POST /generate` |
| `GET/DELETE /api/experience` | Yes | User-scoped |
| `POST /api/experience/upload-url` | Yes | Returns presigned Azure Blob PUT URL |
| `POST /api/experience/process` | Yes | Triggers background processing |
| `POST /api/experience/github` | Yes | GitHub enrichment |
| `POST /api/experience/user-input` | Yes | Manual text input |
| `GET/POST /api/tailorings` | Yes | User-scoped |
| `GET/POST/DELETE /api/tailorings/[id]` | Yes | User-scoped |
| `GET/POST /api/auth/[...nextauth]` | — | NextAuth handler |

Backend additionally validates `X-API-Key` on every request as a second layer.

---

## Database Schema

Managed by Alembic (`backend/alembic/`).

| Table | Key columns |
|---|---|
| `users` | `id` (UUID), `google_sub` (unique, indexed), `email`, `name`, `created_at` |
| `experiences` | `id`, `user_id` (FK, unique), `s3_key`, `filename`, `status` (pending/processing/ready/error), `extracted_profile` (JSON), `github_username`, `github_repos` (JSON), `uploaded_at`, `processed_at` |
| `jobs` | `id`, `user_id` (FK, nullable), `job_url`, `extracted_job` (JSON), `created_at` |
| `tailorings` | `id`, `user_id` (FK), `job_id` (FK), `generated_output`, `created_at` |

S3/Blob key pattern: `users/{google_sub}/{uuid}.{ext}`

---

## Environment Variables

### Frontend (set via Azure Key Vault + Container App env)

| Variable | Source |
|---|---|
| `NEXTAUTH_URL` | `https://tailord.app` (set in Terraform) |
| `NEXTAUTH_SECRET` | Key Vault secret |
| `GOOGLE_CLIENT_ID` | Key Vault secret |
| `GOOGLE_CLIENT_SECRET` | Key Vault secret |
| `API_BASE_URL` | Azure backend Container App internal FQDN |
| `API_KEY` | Key Vault secret |

### Backend (set via Azure Key Vault + Container App env)

| Variable | Source |
|---|---|
| `DATABASE_URL` | Key Vault secret (constructed from DB creds) |
| `API_KEY` | Key Vault secret |
| `STORAGE_PROVIDER` | `azure` (set in Terraform) |
| `AZURE_STORAGE_CONNECTION_STRING` | Key Vault secret |
| `AZURE_STORAGE_CONTAINER` | Set in Terraform |
| `LLM_MODEL` | Set in Terraform (`gpt-4o-mini`) |
| `LLM_API_KEY` | Key Vault secret |

---

## Known Issues / Outstanding Work

### Must fix before production-ready
- **`TF_VAR_llm_api_key=temp-key` in `.env.prod`** — placeholder. Set a real OpenAI API key before the next `terraform apply`. The backend will crash on startup without it (`validate_llm_config()` raises `RuntimeError`).
- **AWS infra incomplete** — `infra/providers/aws/` frontend container is missing all auth and API env vars. Either complete it or delete it to avoid confusion.

### Security
- `.env.prod` is gitignored (`.env.*` pattern in root `.gitignore`) — credentials are not in version control. Keep it this way.
- All production secrets live in Azure Key Vault, injected at runtime via managed identity. No hardcoded credentials in Terraform state beyond what Terraform requires.

### Infrastructure
- **Custom domain cert renewal** is managed by Azure automatically once bound. No action needed.
- **Cloudflare SSL/TLS must remain "Full (Strict)"** — "Flexible" causes an HTTP→HTTPS redirect loop at the Cloudflare→Azure leg.
- **Backend is not publicly exposed** — ingress is internal-only (`external_enabled = false`). Only the frontend container app can reach it.
- **Desired count is 2** in `prod.tfvars`. Both containers will have 2 replicas.

### Features
- Experience processing supports: PDF, DOC, DOCX, TXT upload + GitHub enrichment + manual text input
- Tailoring generation is wired end-to-end but depends on the LLM API key being set
- The `job_cache` in `app.state` is in-memory per-process — not shared across replicas. Fine for now, but worth noting as scale increases.

---

## Dev Setup

```sh
# Frontend
cd frontend && npm run dev        # http://localhost:3000

# Backend
cd backend && uv run uvicorn app.main:app --reload   # http://localhost:8000
```

Local backend requires `.env` file with at minimum:
```
DATABASE_URL=postgresql+psycopg://app:app@localhost:5432/app
LLM_PROVIDER=local
LLM_BASE_URL=http://localhost:1234/v1
```

---

## Deploy

```sh
cd infra/providers/azure
source .env.prod
export $(cat .env.prod | xargs)
terraform apply

# Build and push images separately via CI or manually:
# docker build + docker push to ACR
# az containerapp update --image ... to deploy new revision
```
