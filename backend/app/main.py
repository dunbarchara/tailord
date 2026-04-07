from fastapi import FastAPI

from app.api import experience, notion, tailorings, users
from app.clients.llm_client import validate_llm_config
from app.logging import setup_logging


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
    app.include_router(notion.router)
    return app


app = create_app()
