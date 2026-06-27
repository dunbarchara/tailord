"""
integrations.py — GitHub App installation callback and webhook handler.

GET  /integrations/github/callback  — stores installation_id in UserIntegration+ExperienceSource
POST /integrations/github/webhook   — HMAC-verified PR event handler; enqueues background processing
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.config import settings
from app.core.deps_database import get_db
from app.core.deps_user import require_approved_user
from app.models.database import CaptureSignal, ExperienceSource, User, UserIntegration
from app.services.github_app_scanner import scan_repos_for_installation
from app.services.github_pr_processor import process_github_pr_signal

logger = structlog.get_logger(__name__)
router = APIRouter()


# ── OAuth callback ─────────────────────────────────────────────────────────────


@router.get("/integrations/github/callback")
def github_installation_callback(
    background_tasks: BackgroundTasks,
    installation_id: str = Query(...),
    setup_action: str = Query(default="install"),
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """Handle the GitHub App callback after installation.

    Stores the installation_id scoped to this user and enqueues the initial
    light scan. Access is limited to repos the user explicitly granted during
    installation — no broader OAuth scope is requested or stored.
    """
    from app.clients.github_client import get_github_client

    now = datetime.now(timezone.utc)
    github_login = None

    # Resolve the GitHub account login via App JWT (no user OAuth required)
    try:
        account = get_github_client().get_installation_account(str(installation_id))
        github_login = account.get("login")
    except Exception:
        logger.warning(
            "github_installation_callback: could not resolve login via App JWT",
            user_id=str(user.id),
            installation_id=str(installation_id),
        )

    # Upsert UserIntegration(provider="github")
    integration = (
        db.query(UserIntegration)
        .filter(UserIntegration.user_id == user.id, UserIntegration.provider == "github")
        .first()
    )
    if integration is None:
        integration = UserIntegration(
            id=uuid.uuid4(),
            user_id=user.id,
            provider="github",
            connected_at=now,
        )
        db.add(integration)

    integration.provider_metadata = {
        "installation_id": str(installation_id),
        "login": github_login,
    }
    integration.updated_at = now

    # Upsert ExperienceSource(source_type="github")
    source = (
        db.query(ExperienceSource)
        .filter(
            ExperienceSource.user_id == user.id,
            ExperienceSource.source_type == "github",
        )
        .first()
    )
    if source is None:
        source = ExperienceSource(
            user_id=user.id,
            source_type="github",
            connection_status="connected",
            sync_status="idle",
            config={"installation_id": str(installation_id)},
        )
        db.add(source)
    else:
        existing_config = dict(source.config or {})
        existing_config["installation_id"] = str(installation_id)
        source.config = existing_config

    db.commit()

    logger.info(
        "github_oauth_callback_complete",
        user_id=str(user.id),
        installation_id=str(installation_id),
        github_login=github_login,
    )

    # Enqueue initial light scan — runs even if login is unknown; scanner will
    # skip enrichment gracefully if github_login is empty
    background_tasks.add_task(
        scan_repos_for_installation,
        user_id=user.id,
        installation_id=str(installation_id),
        github_login=github_login or "",
        source_id=source.id,
    )

    return {"ok": True, "installation_id": str(installation_id)}


# ── App info ───────────────────────────────────────────────────────────────────


@router.get("/integrations/github/app-info")
def github_app_info(
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
):
    """Return the GitHub App install URL and the current user's connection state."""
    install_url = (
        f"https://github.com/apps/{settings.github_app_slug}/installations/new"
        if settings.github_app_slug
        else None
    )
    github_integration = next((i for i in user.integrations if i.provider == "github"), None)
    login = (
        (github_integration.provider_metadata or {}).get("login") if github_integration else None
    )
    return {
        "install_url": install_url,
        "connected": github_integration is not None,
        "login": login,
    }


# ── Disconnect ─────────────────────────────────────────────────────────────────


@router.delete("/integrations/github", status_code=204)
def github_disconnect(
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """Disconnect the GitHub App integration.

    Uninstalls the App from the user's GitHub account via the GitHub API, then
    removes our DB records. After this call, no combination of our private key
    and any credentials can restore access — the installation no longer exists
    on GitHub's side.

    Manual scan data (repos, enrichment, claims) is preserved.
    """
    from app.clients.github_client import get_github_client

    integration = (
        db.query(UserIntegration)
        .filter(UserIntegration.user_id == user.id, UserIntegration.provider == "github")
        .first()
    )

    # Uninstall at GitHub level before touching our DB records.
    # This revokes all access tokens and stops all webhook delivery immediately.
    # If this fails (e.g. already uninstalled), log and continue — DB cleanup
    # still removes our ability to generate tokens through normal code paths.
    installation_id = (
        (integration.provider_metadata or {}).get("installation_id") if integration else None
    )
    if installation_id:
        try:
            get_github_client().delete_installation(installation_id)
            logger.info(
                "github_app_uninstalled",
                user_id=str(user.id),
                installation_id=installation_id,
            )
        except Exception as exc:
            logger.warning(
                "github_app_uninstall_failed",
                user_id=str(user.id),
                installation_id=installation_id,
                error=str(exc),
            )

    if integration:
        db.delete(integration)

    github_src = next((s for s in user.experience_sources if s.source_type == "github"), None)
    if github_src and github_src.config:
        config = dict(github_src.config)
        config.pop("installation_id", None)
        github_src.config = config

    db.commit()
    logger.info("github_app_disconnected", user_id=str(user.id))


# ── Helpers ────────────────────────────────────────────────────────────────────


def _cleanup_disconnected_installation(installation_id: str, db: Session) -> None:
    """Remove DB records for an installation that no longer exists on GitHub.

    Called when GitHub sends an installation.deleted event (user uninstalled
    the App directly from their GitHub settings page). Mirrors what the
    /integrations/github DELETE endpoint does, minus the GitHub API call
    (GitHub already did the uninstall — this is just our cleanup).
    """
    if not installation_id:
        return

    source = (
        db.query(ExperienceSource)
        .filter(
            ExperienceSource.source_type == "github",
            ExperienceSource.config["installation_id"].astext == installation_id,
        )
        .first()
    )
    if not source:
        return

    integration = (
        db.query(UserIntegration)
        .filter(
            UserIntegration.user_id == source.user_id,
            UserIntegration.provider == "github",
        )
        .first()
    )
    if integration:
        db.delete(integration)

    config = dict(source.config or {})
    config.pop("installation_id", None)
    source.config = config

    db.commit()
    logger.info(
        "github_installation_deleted_webhook_cleanup",
        installation_id=installation_id,
        user_id=str(source.user_id),
    )


# ── Webhook handler ────────────────────────────────────────────────────────────


@router.post("/integrations/github/webhook")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Receive and process GitHub App webhook events.

    HMAC-SHA256 verified against GITHUB_APP_WEBHOOK_SECRET. Only processes
    pull_request events with action=closed and merged=true.
    """
    # 1. Read raw bytes before any JSON parsing (required for HMAC verification)
    body = await request.body()

    # 2. HMAC-SHA256 verification
    if not settings.github_app_webhook_secret:
        logger.error("github_webhook: GITHUB_APP_WEBHOOK_SECRET not configured")
        return Response(status_code=500)

    sig_header = request.headers.get("X-Hub-Signature-256", "")
    expected_sig = (
        "sha256="
        + hmac.new(
            settings.github_app_webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
    )
    if not hmac.compare_digest(sig_header, expected_sig):
        logger.warning("github_webhook: invalid signature")
        return Response(status_code=401)

    # 3. Filter by event type
    event = request.headers.get("X-GitHub-Event", "")
    if event not in ("pull_request", "installation"):
        return Response(status_code=204)

    # 4. Parse payload
    try:
        payload = json.loads(body)
    except Exception:
        logger.warning("github_webhook: failed to parse JSON body")
        return Response(status_code=400)

    # 5a. Handle installation deleted — user uninstalled the App from GitHub settings
    if event == "installation" and payload.get("action") == "deleted":
        installation_id = str(payload.get("installation", {}).get("id", ""))
        _cleanup_disconnected_installation(installation_id, db)
        return Response(status_code=204)

    # 5b. Only process merged pull_request closes
    action = payload.get("action")
    pr = payload.get("pull_request", {})
    if action != "closed" or not pr.get("merged"):
        return Response(status_code=204)

    # 6. Skip bot-authored PRs
    if pr.get("user", {}).get("type") == "Bot":
        return Response(status_code=204)

    # 7. Resolve user by installation_id
    installation_id = str(payload.get("installation", {}).get("id", ""))
    source = (
        db.query(ExperienceSource)
        .filter(
            ExperienceSource.source_type == "github",
            ExperienceSource.config["installation_id"].astext == installation_id,
        )
        .first()
    )
    if not source:
        logger.info(
            "github_webhook: no ExperienceSource for installation",
            installation_id=installation_id,
        )
        return Response(status_code=204)

    # 8. Branch filter
    watch_branch = (source.config or {}).get("watch_branch")
    if watch_branch and pr.get("base", {}).get("ref") != watch_branch:
        return Response(status_code=204)

    # 9. Idempotency check
    pr_url = pr.get("html_url", "")
    existing = (
        db.query(CaptureSignal)
        .filter(
            CaptureSignal.user_id == source.user_id,
            CaptureSignal.source_type == "github_pr",
            CaptureSignal.source_ref == pr_url,
        )
        .first()
    )
    if existing:
        logger.info(
            "github_webhook: duplicate delivery, signal already exists",
            pr_url=pr_url,
            signal_id=str(existing.id),
        )
        return Response(status_code=204)

    # 10. Insert CaptureSignal
    signal = CaptureSignal(
        user_id=source.user_id,
        source_type="github_pr",
        source_ref=pr_url,
        raw_data=payload,
        status="pending",
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)

    logger.info(
        "github_webhook: signal created",
        signal_id=str(signal.id),
        pr_url=pr_url,
        installation_id=installation_id,
    )

    # 11. Enqueue background processing
    background_tasks.add_task(process_github_pr_signal, signal.id)

    return Response(status_code=202)
