# Tailord

Tailord generates structured, role-specific documents that map a candidate's experience to a specific job description. It doesn't rewrite resumes generically — it answers *"Why is this candidate a strong fit for this role?"*

Each **Tailoring** is produced by an LLM pipeline that scrapes the job posting, extracts structured requirements, scores the candidate's experience against those requirements, and generates a targeted advocacy letter and posting summary. Tailorings are persisted, shareable via public link, and exportable to Notion.

---

## Architecture

```
tailord/
├── frontend/   Next.js 16 (App Router), TypeScript, Tailwind CSS 4
├── backend/    FastAPI, SQLAlchemy, PostgreSQL, OpenAI-compatible LLM
└── infra/      Terraform — Azure Container Apps (active), AWS (reference)
```

**Frontend** is a Next.js App Router app. Authenticated routes live under `/dashboard`. API routes are thin proxies to the FastAPI backend, injecting auth headers server-side. Public profile and tailoring pages (`/u/[slug]`, `/t/[slug]`) are server-rendered.

**Backend** is a FastAPI service, not publicly exposed. It handles the LLM pipeline, file processing, database writes, and Notion OAuth. All routes require an `X-API-Key` header; user identity is passed via `X-User-Id` / `X-User-Email` / `X-User-Name` headers set by the frontend proxy.

**Auth** is Google OAuth via NextAuth.js. No credentials provider.

---

## Running locally

### Prerequisites
- Node.js 20+, `npm`
- Python 3.14+, [`uv`](https://github.com/astral-sh/uv)
- PostgreSQL (local or remote)
- An OpenAI-compatible LLM endpoint (OpenAI, Ollama, LM Studio, etc.)

### Frontend

```bash
cd frontend
cp .env.example .env.local   # fill in NEXTAUTH_SECRET, GOOGLE_CLIENT_ID/SECRET, API_BASE_URL, API_KEY
npm install
npm run dev                  # http://localhost:3000
```

### Backend

```bash
cd backend
cp .env.example .env         # fill in DATABASE_URL, LLM_BASE_URL, LLM_MODEL, API_KEY, STORAGE_PROVIDER, etc.
uv sync
uv run alembic upgrade head  # run migrations
uv run uvicorn app.main:app --reload  # http://localhost:8000
```

### Key environment variables

| Variable | Where | Purpose |
|----------|-------|---------|
| `NEXTAUTH_SECRET` | frontend | NextAuth session signing |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | frontend | Google OAuth |
| `API_BASE_URL` | frontend | Backend URL (e.g. `http://localhost:8000`) |
| `API_KEY` | frontend + backend | Shared secret for frontend→backend requests |
| `DATABASE_URL` | backend | PostgreSQL connection string |
| `LLM_BASE_URL` | backend | OpenAI-compatible endpoint |
| `LLM_MODEL` | backend | Model name (e.g. `gpt-4o`, `qwen2.5-72b`) |
| `STORAGE_PROVIDER` | backend | `azure` or `aws` |

---

## Key concepts

- **Experience** — a user's professional background, sourced from a resume upload, GitHub profile, or manual input. Reusable across all Tailorings.
- **Tailoring** — an AI-generated document produced from Experience + a job posting URL. Includes a cover letter, job posting summary, and scored experience matching.
- **Public profile** (`/u/[slug]`) — an optional shareable profile page rendered from the user's extracted Experience.

---

## Deployment

Deployed on **Azure Container Apps** via GitHub Actions (`.github/workflows/deploy-azure.yml`). Frontend on port 3000, backend on port 8000 (internal ingress only). See `infra/providers/azure/` for Terraform configuration.
