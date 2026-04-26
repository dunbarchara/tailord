---
name: new-backend-endpoint
description: Add a new FastAPI endpoint to the Tailord backend.
---

Add a new FastAPI endpoint to the Tailord backend.

Steps:
1. Add to the correct router in `backend/app/api/` (or create a new file)
2. Dependencies — always include:
   - `api_key: str = Depends(require_api_key)`
   - `current_user: User = Depends(get_current_user)` (user-scoped routes)
   - `db: Session = Depends(get_db)`
3. Define request/response Pydantic schemas in `backend/app/schemas/` if needed
4. New router file → register in `backend/app/main.py` with `app.include_router()`
5. New DB column → `uv run alembic revision --autogenerate -m "description"`, then `uv run alembic upgrade head`

Reference: `backend/app/api/tailorings.py`.
