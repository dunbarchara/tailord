uv run uvicorn app.main:app --port 8000





## WIP Local Debugging Steps

Next.js local frontend
FastAPI backend
Postgres Docker container for DB

1. /frontend - `npm run dev` (run local next.js)
1. /backend - `docker compose up -d` (start postgres docker container)
1. /backend - `uv run python init_db.py` (init postgres db's in docker container)
1. /backend - `uv run python dev_approve.py` (approve user accounts)
1. /backend - `uv run uvicorn app.main:app --port 8000` (start fastapi backend)
