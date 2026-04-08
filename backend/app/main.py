from fastapi import FastAPI
from fastapi.responses import JSONResponse

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

    @app.get("/health", include_in_schema=False)
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    app.include_router(users.router)
    app.include_router(experience.router)
    app.include_router(tailorings.router)
    app.include_router(notion.router)
    return app


app = create_app()
