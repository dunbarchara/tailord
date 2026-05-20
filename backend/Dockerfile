# ---------- Base image ----------
FROM debian:bookworm-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies (curl for healthchecks, build-essential for native extensions)
# 20260519 – adding `&& apt-get upgrade -y ` to patch 'CVE-2026-33845' 'CVE-2026-42010' and unblock trivy CI scan
RUN apt-get update && apt-get upgrade -y && apt-get install -y \
    curl \
    ca-certificates \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# ---------- Install uv ----------
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# ---------- App directory ----------
WORKDIR /app

# ---------- Install Python dependencies ----------
# uv will automatically download the Python version required by pyproject.toml
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# ---------- Install Playwright browsers ----------
RUN uv run playwright install --with-deps chromium

# ---------- Copy application code ----------
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh

# ---------- Runtime ----------
EXPOSE 8000

CMD ["./entrypoint.sh"]
