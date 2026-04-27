-- Enable pgvector extension.
-- This runs automatically on first container start via /docker-entrypoint-initdb.d.
-- The Alembic migration also runs CREATE EXTENSION IF NOT EXISTS vector so this is
-- belt-and-suspenders: whichever runs first wins, the other is a no-op.
CREATE EXTENSION IF NOT EXISTS vector;
