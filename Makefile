# ─── Tailord monorepo — local check targets ────────────────────────────────────
#
# Mirrors the four jobs in .github/workflows/ci.yml so you can run the same
# checks locally before pushing. CI is still the source of truth — use this
# for fast iteration, not as a substitute for watching the CI run.
#
# ── Common usage ───────────────────────────────────────────────────────────────
#
#   make check                  Run all checks sequentially (default)
#   make check-backend          ruff → bandit → pip-audit → pytest
#   make check-frontend         eslint → build → jest → npm audit
#   make check-infra            checkov on infra/providers/azure/
#   make check-pre-commit       pre-commit hooks across all tracked files
#
#   make -j2 check-backend check-frontend   Backend + frontend in parallel
#                                           (output interleaves — use for speed,
#                                            not readability)
#
# ── Prerequisites ──────────────────────────────────────────────────────────────
#
#   Backend tests:   Requires a running PostgreSQL with an app_test database.
#                    Create it once: psql -c "CREATE DATABASE app_test;"
#
#   Frontend build:  Reads frontend/.env.local if present. If absent, set:
#                    NEXTAUTH_SECRET, NEXTAUTH_URL, GOOGLE_CLIENT_ID,
#                    GOOGLE_CLIENT_SECRET, API_BASE_URL, API_KEY.
#
#   Checkov:         Install once with: uv tool install checkov
#
# ── Dependency management (not in CI, but useful to have alongside) ────────────
#
#   make install                Install all deps (backend + frontend)
#   make install-backend        uv sync --dev
#   make install-frontend       npm install

.PHONY: check check-backend check-frontend check-infra check-pre-commit \
        install install-backend install-frontend

# ─── Install ───────────────────────────────────────────────────────────────────

install-backend:
	cd backend && uv sync --dev

install-frontend:
	cd frontend && npm install

install: install-backend install-frontend

# ─── Individual check targets ──────────────────────────────────────────────────

# pre-commit: gitleaks secret scan, ruff lint + format, whitespace/EOF/YAML/JSON,
# and frontend ESLint (via the local eslint-frontend hook).
check-pre-commit:
	pre-commit run --all-files

# Backend: linting, SAST, dependency CVE scan, and the full test suite.
# Runs each tool independently so a failure in one doesn't skip the others
# (ruff/bandit/pip-audit are informational checks; only pytest gates a release).
check-backend:
	@echo ""
	@echo "── ruff (lint) ──────────────────────────────────────────────────"
	cd backend && uv run ruff check .
	@echo ""
	@echo "── bandit (SAST) ────────────────────────────────────────────────"
	cd backend && uv run bandit -r app/ -ll -q
	@echo ""
	@echo "── pip-audit (CVE scan) ─────────────────────────────────────────"
	cd backend && uv run pip-audit --ignore-vuln CVE-2026-3219  # pip 26.1 not yet released; tar+ZIP interpretation conflict, no exploit path via uv.lock
	@echo ""
	@echo "── pytest ───────────────────────────────────────────────────────"
	cd backend && uv run pytest

# Frontend: ESLint, Next.js build (also type-checks TypeScript), Jest, and
# npm audit scoped to production deps only (--omit=dev).
check-frontend:
	@echo ""
	@echo "── eslint ───────────────────────────────────────────────────────"
	cd frontend && npm run lint
	@echo ""
	@echo "── build (type-check + compile) ─────────────────────────────────"
	cd frontend && npm run build
	@echo ""
	@echo "── jest ─────────────────────────────────────────────────────────"
	cd frontend && npm test -- --ci
	@echo ""
	@echo "── npm audit (production deps, high+) ───────────────────────────"
	cd frontend && npm audit --audit-level=high --omit=dev

# Infra: Checkov IaC scan against the active Azure Terraform config.
# Skip list is documented in infra/providers/azure/.checkov.yaml.
check-infra:
	@echo ""
	@echo "── checkov ──────────────────────────────────────────────────────"
	uvx checkov \
		-d infra/providers/azure/ \
		--framework terraform \
		--compact \
		--quiet \
		--config-file infra/providers/azure/.checkov.yaml

# ─── Run everything ────────────────────────────────────────────────────────────

# Runs all four check targets sequentially in the same order as CI jobs.
# Stops at the first failing target — fix that layer, then re-run.
check: check-pre-commit check-backend check-frontend check-infra
