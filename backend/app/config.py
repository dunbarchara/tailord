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
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"

    # Storage provider
    storage_provider: str = "azure"

    # Azure Blob Storage
    azure_storage_connection_string: str | None = None
    azure_storage_container: str = "tailord-uploads"

    class Config:
        env_file = ".env"

settings = Settings()
