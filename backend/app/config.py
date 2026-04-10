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

    # ── Storage ───────────────────────────────────────────────────────────────
    # Switch providers by setting STORAGE_PROVIDER to "azure" or "aws".
    storage_provider: str = "azure"

    # Azure Blob Storage (active in staging and prod)
    # Use Azurite's well-known connection string for local development.
    azure_storage_connection_string: str | None = None
    azure_storage_container: str = "uploads"

    # AWS S3 (inactive — kept so the codebase can switch providers without code
    # changes; see storage_aws.py and CLAUDE.md § Cloud Portability)
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-2"
    s3_uploads_bucket: str = "uploads"

    # ── Notion OAuth ──────────────────────────────────────────────────────────
    notion_client_id: str | None = None
    notion_client_secret: str | None = None
    notion_redirect_uri: str = "http://localhost:3000/api/auth/notion/callback"

    class Config:
        env_file = ".env"


settings = Settings()
