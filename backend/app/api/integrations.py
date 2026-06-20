"""
integrations.py — GitHub App OAuth callback and webhook handler.

GET  /integrations/github/callback  — exchanges OAuth code, stores UserIntegration+ExperienceSource
POST /integrations/github/webhook   — HMAC-verified PR event handler; enqueues background processing
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

import requests
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.config import settings
from app.core.deps_database import get_db
from app.core.deps_user import require_approved_user
from app.models.database import CaptureSignal, ExperienceSource, User, UserIntegration
from app.services.github_pr_processor import process_github_pr_signal

logger = structlog.get_logger(__name__)
router = APIRouter()


# ── OAuth callback ─────────────────────────────────────────────────────────────


@router.get("/integrations/github/callback")
def github_oauth_callback(
    code: str = Query(...),
    installation_id: str = Query(...),
    setup_action: str = Query(default="install"),
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """Handle the GitHub App OAuth callback after installation.

    Exchanges the authorization code for user tokens, stores them in UserIntegration,
    and upserts the github ExperienceSource with the installation_id.
    """
    from app.clients.github_client import get_github_client

    # Exchange code for tokens
    try:
        token_data = get_github_client().exchange_oauth_code(code)
    except Exception:
        logger.exception("github_oauth_callback: token exchange failed", user_id=str(user.id))
        raise HTTPException(status_code=502, detail="GitHub token exchange failed")

    access_token = token_data.get("access_token")
    if not access_token:
        logger.error(
            "github_oauth_callback: no access_token in response",
            user_id=str(user.id),
            response_keys=list(token_data.keys()),
        )
        raise HTTPException(
            status_code=502, detail="GitHub token exchange returned no access_token"
        )

    # Fetch GitHub username via user token
    github_login = None
    try:
        user_resp = requests.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=10,
        )
        user_resp.raise_for_status()
        github_login = user_resp.json().get("login")
    except Exception:
        logger.warning(
            "github_oauth_callback: could not fetch GitHub login",
            user_id=str(user.id),
        )

    # Compute token expiry timestamps
    now = datetime.now(timezone.utc)
    expires_in = token_data.get("expires_in")
    refresh_expires_in = token_data.get("refresh_token_expires_in")
    token_expires_at = (
        datetime.fromtimestamp(now.timestamp() + expires_in, tz=timezone.utc).isoformat()
        if expires_in
        else None
    )
    refresh_token_expires_at = (
        datetime.fromtimestamp(now.timestamp() + refresh_expires_in, tz=timezone.utc).isoformat()
        if refresh_expires_in
        else None
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

    integration.credentials = {
        "access_token": access_token,
        "refresh_token": token_data.get("refresh_token"),
        "token_expires_at": token_expires_at,
        "refresh_token_expires_at": refresh_token_expires_at,
        "token_type": token_data.get("token_type"),
        "scope": token_data.get("scope"),
    }
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
    return {"ok": True, "installation_id": str(installation_id)}


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
    if event != "pull_request":
        return Response(status_code=204)

    # 4. Parse payload
    try:
        payload = json.loads(body)
    except Exception:
        logger.warning("github_webhook: failed to parse JSON body")
        return Response(status_code=400)

    # 5. Only process merged closes
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
