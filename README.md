# Tailord

Tailord generates structured, role-specific **Tailorings** — AI-produced documents that map a candidate's professional experience to a specific job description. It doesn't rewrite resumes generically. It answers a single question: *"Why is this candidate a strong fit for this role?"*

Each Tailoring is produced by a multi-stage LLM pipeline: scrape the job posting with a headless browser, extract structured requirements, score the candidate's experience against those requirements source-by-source, generate a targeted advocacy letter, and persist the result as a shareable document. The pipeline streams progress to the client over SSE so the user sees each stage as it completes.

---

## Architecture

```
tailord/
├── frontend/   Next.js 16 (App Router), TypeScript, Tailwind CSS 4
├── backend/    FastAPI, SQLAlchemy, PostgreSQL, OpenAI-compatible LLM
└── infra/      Terraform — Azure Container Apps (active), AWS (reference)
```

**Frontend** is a Next.js App Router application. All authenticated routes live under `/dashboard`. Next.js API routes are thin server-side proxies to the FastAPI backend — they inject the API key and user identity headers, so neither ever reaches the browser. Public profile and tailoring pages (`/u/[slug]`, `/t/[slug]`) are server-rendered.

**Backend** is a FastAPI service with internal-only ingress — it is not reachable from the internet. It owns the LLM pipeline, file processing, job scraping, database writes, and Notion OAuth. Every route requires an `X-API-Key` header; user identity arrives via `X-User-Id` / `X-User-Email` / `X-User-Name` headers set by the Next.js proxy.

**Auth** is Google OAuth via NextAuth.js. No credentials provider. Sessions are JWE-encrypted (not just signed) — the payload is opaque to the browser.

---

## LLM Pipeline

A Tailoring is produced in five sequential stages, each streamed to the client as it completes:

1. **Job extraction** — Playwright loads the job URL in a headless browser (necessary for JS-heavy ATS pages), extracts the page content, and an LLM call produces a structured `extracted_job` object: title, company, requirements list.
2. **Profile formatting** — The candidate's multi-source experience (resume, GitHub repos, manual input) is formatted into a labeled plaintext block. Pre-computed signals (total years of experience, role timeline) are injected so the LLM doesn't waste tokens on date arithmetic.
3. **Requirement matching** — Each extracted job requirement is scored against the candidate's experience: `STRONG` (directly evidenced), `PARTIAL` (adjacent evidence), or absent. The source of each match is tracked (Resume / GitHub / Direct Input).
4. **Tailoring generation** — The formatted profile + ranked matches feed a generation prompt. Output is a structured markdown document: an advocacy letter with inline source tags, a job posting summary, and a candidate footer.
5. **Chunk scoring** — Post-generation, each section of the tailoring is scored independently against the job requirements. Results populate the Analysis tab.

The pipeline is LLM-agnostic: the OpenAI SDK's configurable `base_url` means the same code runs against OpenAI, Azure AI Foundry, Ollama, or any OpenAI-compatible endpoint. Locally, no API key is required — point it at LM Studio or Ollama.

---

## Tech Stack

### Frontend

| Library | Why |
|---------|-----|
| Next.js 16 (App Router) | Server components for zero-JS auth checks; SSE pass-through without buffering; `output: 'standalone'` for Docker/Azure |
| React 19 | Required by Next.js 16 |
| TypeScript 6 (strict) | Catches API contract drift between frontend and backend at compile time |
| NextAuth.js 4 | Google OAuth in ~10 lines; JWE-encrypted sessions; `withAuth` middleware integration |
| Tailwind CSS 4 | CSS variable tokens without a JS config file; works correctly with SSR |
| shadcn/ui (New York) | Unstyled Radix primitives + Tailwind — full control over appearance, no fighting a component library |
| Lucide React | Consistent icon set, tree-shakeable |
| Sonner | Lightweight toast notifications |

### Backend

| Library | Why |
|---------|-----|
| FastAPI | Async-native (Playwright requires it); automatic OpenAPI docs; clean dependency injection for auth |
| SQLAlchemy 2 + Alembic | Backend-agnostic ORM with migration tooling; Prisma was ruled out (Python backend, no shared schema with frontend) |
| psycopg 3 | Modern async-capable PostgreSQL driver |
| OpenAI SDK | Configurable `base_url` makes it work with any OpenAI-compatible endpoint — no code changes to switch providers |
| Playwright | JS-heavy ATS pages (Greenhouse, Lever, Workday) require a real browser; BeautifulSoup alone fails on SPAs |
| pypdf + python-docx | PDF and DOCX text extraction for resume processing |
| slowapi | In-process rate limiting (leaky bucket) without Redis — sufficient at this scale |
| boto3 + azure-storage-blob | Both kept as dependencies so the same Docker image runs on either cloud; provider selected at runtime via `STORAGE_PROVIDER` env var |
| uv | 10–100× faster than pip; lockfile + virtualenv in one tool |

### Infrastructure

| Component | Detail |
|-----------|--------|
| Compute | Azure Container Apps — frontend (port 3000, external) + backend (port 8000, internal only) |
| Database | Azure PostgreSQL Flexible Server v16 (B_Standard_B1ms) |
| Storage | Azure Blob Storage — separate accounts for prod and staging |
| Secrets | Azure Key Vault — all secrets injected at runtime via managed identity |
| Registry | Azure Container Registry (ACR) — RBAC-only, no admin user |
| DNS / TLS | Cloudflare (proxied CNAMEs, Full Strict TLS) |
| IaC | Terraform in `infra/providers/azure/` |
| CI/CD | GitHub Actions — OIDC auth, blue/green deployments, staging gate before prod |

---

## Local Dev Setup

### Prerequisites

- Node.js 20+, npm
- Python 3.14+, [uv](https://github.com/astral-sh/uv)
- PostgreSQL (local instance or any accessible server)
- An OpenAI-compatible LLM endpoint — [LM Studio](https://lmstudio.ai/) or [Ollama](https://ollama.com/) on `:1234` works out of the box, no API key needed

### Frontend

```bash
cd frontend
cp .env.example .env.local
# Required: NEXTAUTH_SECRET, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, API_BASE_URL, API_KEY
npm install
npm run dev          # http://localhost:3000
```

### Backend

```bash
cd backend
docker compose up -d          # PostgreSQL :5432 + Azurite blob storage :10000
cp .env.example .env
# Required: DATABASE_URL, API_KEY, AZURE_STORAGE_CONNECTION_STRING, AZURE_STORAGE_CONTAINER
# Optional for local LLM: LLM_BASE_URL=http://localhost:1234/v1, LLM_MODEL=<your-model>
uv sync
uv run alembic upgrade head   # apply migrations (requires db container to be up)
uv run uvicorn app.main:app --reload   # http://localhost:8000
```

The `docker compose` stack starts two services: Postgres 16 and [Azurite](https://github.com/Azure/Azurite) (Azure Blob Storage emulator). A third `storage-init` container runs once on first start to create the `uploads` container and configure CORS. Local Azurite values for `.env`:

```bash
STORAGE_PROVIDER=azure
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1; # gitleaks:allow — Azurite well-known public key, not a real secret (same for all installs)
AZURE_STORAGE_CONTAINER=uploads
```

The Azurite account key above is the well-known public default shipped with every Azurite install — it is not a real secret.

### Key environment variables

| Variable | Service | Purpose |
|----------|---------|---------|
| `NEXTAUTH_SECRET` | frontend | Session signing key (`openssl rand -base64 32`) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | frontend | Google OAuth credentials |
| `API_BASE_URL` | frontend | Backend URL (`http://localhost:8000` locally) |
| `API_KEY` | frontend + backend | Shared secret — injected server-side, never reaches the browser |
| `DATABASE_URL` | backend | PostgreSQL connection string |
| `LLM_BASE_URL` | backend | OpenAI-compatible endpoint (omit to use OpenAI directly) |
| `LLM_API_KEY` | backend | LLM API key (omit for local models) |
| `LLM_MODEL` | backend | Model name (`gpt-4o-mini`, `qwen2.5-72b`, etc.) |
| `STORAGE_PROVIDER` | backend | `azure` or `aws` |

---

## Quality Checks

The `Makefile` mirrors CI locally:

```bash
make check             # run all checks
make check-backend     # ruff → bandit → pip-audit → pytest
make check-frontend    # eslint → build → jest → npm audit
make check-infra       # checkov static analysis on Terraform
```

---

## Security

**Deployment**
- GitHub Actions authenticates to Azure via **OIDC federated credentials** — no long-lived service principal secrets stored in GitHub.
- All secrets live in **Azure Key Vault**, injected at runtime via managed identity. No credentials in environment variables baked into the image or in Terraform state.
- **Backend ingress is internal-only** (`external_enabled = false`). The backend Container App is unreachable from the internet — only the frontend container can call it.
- Prod and staging use **isolated databases and storage accounts** — no shared data between environments.

**Application**
- **NextAuth JWE sessions** — encrypted, not just signed. The session payload is opaque to the browser; tampering invalidates the session.
- **`X-API-Key` is server-side only** — injected by Next.js API routes, never sent from the browser or exposed in client-side code.
- **Admin access** is gated by `is_admin` on the `User` model (DB-authoritative), verified on every request by a FastAPI dependency — not by client claims or a shared env var.

**CI pipeline**
- Trivy container scanning (CRITICAL severity, blocks deployment)
- Bandit (Python SAST) + ruff + pip-audit + npm audit + eslint-plugin-security
- checkov for Terraform security analysis
- gitleaks for secret scanning (history scan clean)

---

## Deployment

Deployments run automatically on merge to `main` via `.github/workflows/deploy-azure.yml`:

1. Build frontend + backend Docker images, tag with `YYYYMMDD.run_number`
2. Trivy scan
3. Push to ACR
4. Deploy to **staging** (blue/green revision swap), smoke test
5. Deploy to **prod** (same pattern), smoke test
6. Prune ACR (keep last 3 images)

See `infra/providers/azure/` for Terraform configuration and `infra/providers/azure/BOOTSTRAP.md` for first-time environment setup.

---

## Codebase Conventions

See [CLAUDE.md](./CLAUDE.md) — written for Claude Code but useful for any contributor. Covers routing architecture, data models, design system tokens, cloud portability constraints, and naming conventions.
