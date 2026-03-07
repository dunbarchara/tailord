from fastapi import FastAPI
from app.api import users, experience, tailorings
from app.config import settings
from app.logging import setup_logging
from app.clients.llm_client import validate_llm_config

def create_app() -> FastAPI:
    setup_logging()

    validate_llm_config()

    app = FastAPI(
        title="Tailord API",
        version="1.0.0",
    )

    app.include_router(users.router)
    app.include_router(experience.router)
    app.include_router(tailorings.router)
    return app

app = create_app()
