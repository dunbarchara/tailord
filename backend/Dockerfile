# ---------- Base image ----------
FROM python:3.11-slim AS base

# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# ---------- Install uv ----------
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:${PATH}"

# ---------- App directory ----------
WORKDIR /app

# ---------- Copy dependency files ----------
COPY pyproject.toml uv.lock ./

# ---------- Install Python dependencies ----------
RUN uv sync --frozen --no-dev

# ---------- Install Playwright browsers ----------
RUN uv run playwright install --with-deps chromium

# ---------- Copy application code ----------
COPY app ./app

# ---------- Runtime ----------
EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
