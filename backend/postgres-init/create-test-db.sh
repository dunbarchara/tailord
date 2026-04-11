#!/bin/bash
# Creates the test database alongside the primary app database.
# Runs once on first container init via docker-entrypoint-initdb.d.
# If init has already ran, use to following commands to manually setup:
#   psql postgresql://app:app@localhost:5432/app -c "CREATE DATABASE app_test;"
#   psql postgresql://app:app@localhost:5432/app -c "GRANT ALL PRIVILEGES ON DATABASE app_test TO app;"
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -c "CREATE DATABASE app_test;"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -c "GRANT ALL PRIVILEGES ON DATABASE app_test TO $POSTGRES_USER;"
