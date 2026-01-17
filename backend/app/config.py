from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 🔐 Backend API auth
    api_key: str | None = None

    # 🤖 LLM config
    llm_provider: str = "openai"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"

    class Config:
        env_file = ".env"

settings = Settings()
