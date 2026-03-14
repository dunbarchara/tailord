from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Environment
    environment: str = "local"  # local | production

    # Logging
    log_level: str = "INFO"
    log_dir: str = "logs"

    # Database
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/app"

    # Auth
    api_key: str | None = None

    # LLM config
    # llm_base_url: set for Azure AI Foundry or local; omit to use OpenAI directly
    # llm_api_key: required for OpenAI and Azure AI Foundry
    # llm_api_version: required for Azure AI endpoints (e.g. 2024-05-01-preview); omit for OpenAI/local
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_api_version: str | None = None

    # Storage provider — switch between "azure" and "aws" via env var
    storage_provider: str = "azure"

    # AWS S3 (used when storage_provider = "aws")
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-2"
    s3_uploads_bucket: str = "tailord-uploads"

    # Azure Blob Storage (used when storage_provider = "azure")
    azure_storage_connection_string: str | None = None
    azure_storage_container: str = "tailord-uploads"

    # Notion OAuth
    notion_client_id: str | None = None
    notion_client_secret: str | None = None
    notion_redirect_uri: str = "http://localhost:3000/api/auth/notion/callback"

    class Config:
        env_file = ".env"

settings = Settings()
