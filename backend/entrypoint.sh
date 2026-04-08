#!/bin/sh
set -e

echo "Initializing database..."
IS_FRESH=$(uv run python -c "
from sqlalchemy import inspect
from app.clients.database import engine
print('fresh' if not inspect(engine).has_table('alembic_version') else 'existing')
")

if [ "$IS_FRESH" = "fresh" ]; then
    echo "Fresh database detected — creating schema from ORM models..."
    uv run python init_db.py
    uv run alembic stamp head
    echo "Schema created and stamped at head."
else
    echo "Running database migrations..."
    uv run alembic upgrade head
fi

echo "Starting server..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
