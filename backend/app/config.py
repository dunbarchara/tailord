from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Environment
    environment: str = "local"  # local | production

    # Logging
    log_level: str = "INFO"
    log_dir: str = "logs"

    # Auth
    api_key: str | None = None

    # LLM config
    llm_provider: str = "openai"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"

    # AWS / S3
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-2"
    s3_uploads_bucket: str = "tailord-uploads"

    class Config:
        env_file = ".env"

settings = Settings()
