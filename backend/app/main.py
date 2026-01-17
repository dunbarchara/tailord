from fastapi import FastAPI
from app.api import router
from app.config import settings
from app.logging import setup_logging
from app.llm_client import validate_llm_config

def create_app() -> FastAPI:
    setup_logging()

    validate_llm_config()

    app = FastAPI(
        title="Tailord API",
        version="1.0.0",
    )

    app.include_router(router)
    return app

app = create_app()
