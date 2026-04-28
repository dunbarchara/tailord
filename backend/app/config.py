from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Environment ───────────────────────────────────────────────────────────
    environment: str = "local"  # local | staging | production
    log_level: str = "INFO"
    log_dir: str = "logs"

    # ── Auth ──────────────────────────────────────────────────────────────────
    # Shared secret between frontend and backend (X-API-Key header).
    api_key: str | None = None

    # ── Database ──────────────────────────────────────────────────────────────
    # Default matches docker-compose (user: app, pass: app, db: app).
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/app"

    # ── LLM ───────────────────────────────────────────────────────────────────
    # llm_base_url:    set for Azure AI Foundry or a local model; omit to use
    #                  OpenAI directly.
    # llm_api_version: required for Azure AI endpoints (e.g. 2024-05-01-preview);
    #                  omit for OpenAI / local.
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_api_version: str | None = None

    # ── Embeddings ────────────────────────────────────────────────────────────
    # embedding_base_url: falls back to llm_base_url if unset, then OpenAI default.
    # Allows embeddings and chat to hit different endpoints (e.g. real OpenAI
    # for embeddings, local model for chat).
    # embedding_api_key: deliberately NOT falling back to llm_api_key. Keeping
    # these keys separate ensures the LLM key is never sent to an embedding
    # endpoint (or vice versa). In staging/production managed identity is used
    # and neither key is set. Locally, set this to a personal OpenAI key.
    embedding_model: str = "text-embedding-3-small"
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None

    # ── Storage ───────────────────────────────────────────────────────────────
    # Switch providers by setting STORAGE_PROVIDER to "azure" or "aws".
    storage_provider: str = "azure"

    # Azure Blob Storage (active in staging and prod)
    # Production: set AZURE_STORAGE_ACCOUNT_NAME — Managed Identity handles auth.
    # Local dev: set AZURE_STORAGE_CONNECTION_STRING (Azurite) — takes priority over MI.
    azure_storage_account_name: str | None = None
    azure_storage_connection_string: str | None = None
    azure_storage_container: str = "uploads"

    # AWS S3 (inactive — kept so the codebase can switch providers without code
    # changes; see storage_aws.py and CLAUDE.md § Cloud Portability)
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-2"
    s3_uploads_bucket: str = "uploads"

    # ── Matching ──────────────────────────────────────────────────────────────
    # matching_mode: "vector" = cosine pre-selection → focused grouped context → LLM scores (default)
    #                "llm"    = full formatted profile passed to LLM scorer (legacy fallback)
    # vector_top_k: number of ExperienceChunk rows retrieved per JobChunk in vector mode.
    matching_mode: str = "vector"
    vector_top_k: int = 8

    # ── GitHub App ────────────────────────────────────────────────────────────
    # Authentication uses Installation Access Tokens — not personal PATs.
    # Provide PEM content directly (staging/prod via Key Vault) or a file path (local dev).
    github_app_id: str | None = None
    github_app_installation_id: str | None = None
    github_app_private_key: str | None = None  # PEM content
    github_app_private_key_path: str | None = None  # Path to .pem file

    # ── Notion OAuth ──────────────────────────────────────────────────────────
    notion_client_id: str | None = None
    notion_client_secret: str | None = None
    notion_redirect_uri: str = "http://localhost:3000/api/auth/notion/callback"

    class Config:
        env_file = ".env"


settings = Settings()
