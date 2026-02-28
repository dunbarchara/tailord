from fastapi import FastAPI
from app.api import parse, job, generate, users, resume
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

    # Initialize shared state
    app.state.job_cache = {}

    app.include_router(parse.router)
    app.include_router(job.router)
    app.include_router(generate.router)
    app.include_router(users.router)
    app.include_router(resume.router)
    return app

app = create_app()
