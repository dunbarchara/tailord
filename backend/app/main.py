from fastapi import FastAPI
from app.api import analyze, parse, job, profile, generate
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

    app.include_router(analyze.router)
    app.include_router(parse.router)
    
    app.include_router(job.router)
    app.include_router(profile.router)
    app.include_router(generate.router)
    return app

app = create_app()
