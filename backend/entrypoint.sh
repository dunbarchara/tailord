#!/bin/sh
set -e

echo "Initializing database..."
IS_FRESH=$(uv run python -c "
from sqlalchemy import inspect, text
from app.clients.database import engine
with engine.connect() as conn:
    if not inspect(engine).has_table('alembic_version'):
        print('fresh')
    else:
        row = conn.execute(text('SELECT version_num FROM alembic_version LIMIT 1')).fetchone()
        print('fresh' if row is None else 'existing')
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
