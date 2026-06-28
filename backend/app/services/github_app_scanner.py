"""
github_app_scanner.py — initial light scan triggered on GitHub App installation.

Called from the OAuth callback as a BackgroundTask. Fetches repos accessible to
the installation, stores them in ExperienceSource, then enqueues the standard
enrichment pipeline (unauthenticated — works for public repos; private repo
enrichment via installation token is deferred to Phase 4b).
"""

import uuid
from datetime import datetime, timedelta, timezone

import structlog

logger = structlog.get_logger(__name__)


def scan_repos_for_installation(
    user_id: uuid.UUID,
    installation_id: str,
    github_login: str,
    source_id: uuid.UUID,
) -> None:
    """Background task: fetch repos for a new App installation and trigger light scan.

    Creates its own database session — safe to run after the request context closes.
    """
    from app.clients.database import SessionLocal
    from app.clients.github_client import get_github_client
    from app.models.database import ExperienceSource

    db = SessionLocal()
    try:
        client = get_github_client()

        try:
            all_repos = client.get_installation_repositories(installation_id)
        except Exception:
            logger.exception(
                "github_app_scanner: failed to fetch installation repos",
                installation_id=installation_id,
                user_id=str(user_id),
            )
            return

        # Apply same filters as get_user_repos: non-fork, non-archived, recent
        cutoff = datetime.now(timezone.utc) - timedelta(days=730)
        repos = []
        for r in all_repos:
            if r.get("fork") or r.get("archived"):
                continue
            pushed = r.get("pushed_at")
            if pushed and datetime.fromisoformat(pushed.replace("Z", "+00:00")) < cutoff:
                continue
            repos.append(r)
        repos = repos[:20]

        if not repos:
            logger.info(
                "github_app_scanner: no qualifying repos found",
                installation_id=installation_id,
            )
            return

        # Store repos in ExperienceSource so the frontend can display them immediately
        source = db.get(ExperienceSource, source_id)
        if not source:
            logger.warning(
                "github_app_scanner: ExperienceSource not found",
                source_id=str(source_id),
            )
            return

        existing_data = source.source_data or {}
        source.source_data = {**existing_data, "repos": repos}

        # Ensure username in config so legacy code paths (get_experience, enricher) work
        existing_config = dict(source.config or {})
        if not existing_config.get("username"):
            existing_config["username"] = github_login
            source.config = existing_config

        db.commit()

        logger.info(
            "github_app_scanner: repos stored, awaiting user opt-in to trigger enrichment",
            repo_count=len(repos),
            installation_id=installation_id,
            user_id=str(user_id),
        )
    finally:
        db.close()
