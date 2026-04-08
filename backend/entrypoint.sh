#!/bin/sh
set -e

echo "Running database migrations..."

# After a migration squash, an existing database may hold a revision ID that no
# longer exists in the migration chain. Detect this and stamp at head so that
# alembic upgrade head treats the DB as current (the schema is already correct —
# we only replaced the migration history, not the schema itself).
# On a fresh database alembic upgrade head works normally without stamping.
CURRENT=$(uv run alembic current 2>&1 || true)
if echo "$CURRENT" | grep -q "Can't locate revision"; then
    echo "Unknown revision detected (post-squash) — stamping at head..."
    uv run alembic stamp --purge 0408beae0390
fi
uv run alembic upgrade head

echo "Starting server..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
