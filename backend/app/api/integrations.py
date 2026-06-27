"""
integrations.py — GitHub App installation callback and webhook handler.

GET  /integrations/github/callback  — stores installation_id in UserIntegration+ExperienceSource
POST /integrations/github/webhook   — HMAC-verified PR event handler; enqueues background processing
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.auth import require_api_key
from app.config import settings
from app.core.deps_database import get_db
from app.core.deps_user import require_approved_user
from app.models.database import (
    CaptureSignal,
    ExperienceClaim,
    ExperienceSource,
    User,
    UserIntegration,
)
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

    # Per-repo config from ExperienceSource (loaded via selectin)
    source = next((s for s in user.experience_sources if s.source_type == "github"), None)
    repos_raw = (source.source_data or {}).get("repos", []) if source else []
    repos = [
        {
            "name": r.get("name", ""),
            "full_name": r.get("full_name", ""),
            "private": r.get("private", False),
            "default_branch": r.get("default_branch", "main"),
        }
        for r in repos_raw
    ]
    watch_branch = (source.config or {}).get("watch_branch") if source else None
    repo_config = (source.config or {}).get("repo_config", {}) if source else {}

    installation_id = (
        (github_integration.provider_metadata or {}).get("installation_id")
        if github_integration
        else None
    )

    return {
        "install_url": install_url,
        "connected": github_integration is not None,
        "login": login,
        "installation_id": installation_id,
        "repos": repos,
        "watch_branch": watch_branch,
        "repo_config": repo_config,
    }


# ── Config update ──────────────────────────────────────────────────────────────


class GithubConfigPatch(BaseModel):
    repo_full_name: str | None = None
    enabled: bool | None = None  # whether the repo is an active experience source
    pr_capture: bool | None = None  # whether to capture signals from merged PRs
    delete_claims: bool = False  # when enabled=False: also delete captured claims


@router.patch("/integrations/github/config", status_code=200)
def github_update_config(
    body: GithubConfigPatch,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """Update GitHub capture config: per-repo enabled/pr_capture toggles."""
    source = (
        db.query(ExperienceSource)
        .filter(
            ExperienceSource.user_id == user.id,
            ExperienceSource.source_type == "github",
        )
        .first()
    )
    if not source:
        raise HTTPException(status_code=404, detail="GitHub source not found")

    config = dict(source.config or {})

    if body.repo_full_name is not None:
        repo_config = dict(config.get("repo_config", {}))
        rc = dict(repo_config.get(body.repo_full_name, {}))

        if body.enabled is not None:
            rc["enabled"] = body.enabled
            if not body.enabled and body.delete_claims:
                pr_prefix = f"https://github.com/{body.repo_full_name}/pull/"
                db.query(ExperienceClaim).filter(
                    ExperienceClaim.user_id == user.id,
                    ExperienceClaim.source_type == "github_pr",
                    ExperienceClaim.source_ref.like(f"{pr_prefix}%"),
                ).delete(synchronize_session=False)

        if body.pr_capture is not None:
            rc["pr_capture"] = body.pr_capture

        repo_config[body.repo_full_name] = rc
        config["repo_config"] = repo_config

    source.config = config
    flag_modified(source, "config")
    db.commit()

    logger.info(
        "github_config_updated",
        user_id=str(user.id),
        repo_full_name=body.repo_full_name,
        enabled=body.enabled,
        pr_capture=body.pr_capture,
        delete_claims=body.delete_claims,
    )

    # When enabling a repo, run the lightweight content scan:
    # languages + README + manifests → LLM → experience claims/chunks.
    if body.enabled and body.repo_full_name:
        from app.services.github_enricher import enrich_github_repos

        github_username = (source.config or {}).get("username", "")
        repo_short_name = body.repo_full_name.split("/", 1)[-1]
        if github_username and source.id:
            background_tasks.add_task(
                enrich_github_repos,
                github_username=github_username,
                source_id=source.id,
                repo_names=[repo_short_name],
                merge_with_existing=True,
                user_id=str(user.id),
            )

    return {"ok": True}


class GithubScanRepoRequest(BaseModel):
    repo_full_name: str


@router.post("/integrations/github/scan-repo", status_code=202)
def github_scan_repo(
    body: GithubScanRepoRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """Manually trigger a content scan for an enabled repo.

    Re-runs languages + README + manifests → LLM → experience claims/chunks.
    Merges into existing data so other repos are unaffected.
    """
    from app.services.github_enricher import enrich_github_repos

    source = (
        db.query(ExperienceSource)
        .filter(
            ExperienceSource.user_id == user.id,
            ExperienceSource.source_type == "github",
        )
        .first()
    )
    if not source:
        raise HTTPException(status_code=404, detail="GitHub source not found")

    github_username = (source.config or {}).get("username", "")
    if not github_username:
        raise HTTPException(status_code=400, detail="GitHub username not configured")

    repo_cfg = (source.config or {}).get("repo_config", {}).get(body.repo_full_name, {})
    if not repo_cfg.get("enabled"):
        raise HTTPException(status_code=400, detail="Repo is not enabled")

    repo_short_name = body.repo_full_name.split("/", 1)[-1]
    background_tasks.add_task(
        enrich_github_repos,
        github_username=github_username,
        source_id=source.id,
        repo_names=[repo_short_name],
        merge_with_existing=True,
        user_id=str(user.id),
    )

    logger.info(
        "github_scan_repo_triggered",
        user_id=str(user.id),
        repo_full_name=body.repo_full_name,
    )
    return {"ok": True}


@router.post("/integrations/github/refresh-repos", status_code=200)
def github_refresh_repos(
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """Re-fetch the list of installed repos from GitHub and update source_data.repos.

    Synchronous — fast (one GitHub API call). Does not re-run enrichment.
    """
    from app.clients.github_client import get_github_client

    source = (
        db.query(ExperienceSource)
        .filter(
            ExperienceSource.user_id == user.id,
            ExperienceSource.source_type == "github",
        )
        .first()
    )
    if not source:
        raise HTTPException(status_code=404, detail="GitHub source not found")

    installation_id = (source.config or {}).get("installation_id")
    if not installation_id:
        raise HTTPException(status_code=400, detail="No installation_id found")

    try:
        all_repos = get_github_client().get_installation_repositories(installation_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch repos from GitHub: {exc}")

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

    existing_data = source.source_data or {}
    source.source_data = {**existing_data, "repos": repos}
    flag_modified(source, "source_data")
    db.commit()

    logger.info(
        "github_repos_refreshed",
        user_id=str(user.id),
        repo_count=len(repos),
    )
    return [
        {
            "name": r.get("name", ""),
            "full_name": r.get("full_name", ""),
            "private": r.get("private", False),
            "default_branch": r.get("default_branch", "main"),
        }
        for r in repos
    ]


# ── Disconnect ─────────────────────────────────────────────────────────────────


@router.delete("/integrations/github", status_code=204)
def github_disconnect(
    cascade: bool = True,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """Disconnect the GitHub App integration.

    Uninstalls the App from the user's GitHub account via the GitHub API, then
    removes our DB records. After this call, no combination of our private key
    and any credentials can restore access — the installation no longer exists
    on GitHub's side.

    cascade=true (default): hard-deletes all derived GitHub claims and groups.
    cascade=false: keeps claims and groups; they become independent of the source.
    """
    from app.clients.github_client import get_github_client
    from app.services.experience_chunker import (
        delete_github_chunks,
        delete_github_groups,
        delete_github_pr_chunks,
    )

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

    if cascade:
        delete_github_chunks(db, user.id)
        delete_github_pr_chunks(db, user.id)
        delete_github_groups(db, user.id)

    if integration:
        db.delete(integration)

    github_src = next((s for s in user.experience_sources if s.source_type == "github"), None)
    if github_src:
        github_src.config = {}
        github_src.source_data = {}
        github_src.connection_status = "disconnected"
        github_src.sync_status = "idle"
        github_src.last_synced_at = None
        flag_modified(github_src, "config")
        flag_modified(github_src, "source_data")

    db.commit()
    logger.info("github_app_disconnected", user_id=str(user.id), cascade=cascade)


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
    flag_modified(source, "config")

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

    # 8b. Per-repo gate — repo must be enabled AND have PR capture on
    repo_full_name = payload.get("repository", {}).get("full_name", "")
    repo_cfg = (source.config or {}).get("repo_config", {}).get(repo_full_name, {})
    if not repo_cfg.get("enabled"):
        logger.info(
            "github_webhook: repo not enabled",
            repo=repo_full_name,
            installation_id=installation_id,
        )
        return Response(status_code=204)
    if not repo_cfg.get("pr_capture", True):
        logger.info(
            "github_webhook: PR capture disabled for repo",
            repo=repo_full_name,
            installation_id=installation_id,
        )
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

    # 10. Insert CaptureSignal + track last_webhook_at for this repo
    signal = CaptureSignal(
        user_id=source.user_id,
        source_type="github_pr",
        source_ref=pr_url,
        raw_data=payload,
        status="pending",
    )
    db.add(signal)

    if repo_full_name:
        config = dict(source.config or {})
        rc_map = dict(config.get("repo_config", {}))
        rc = dict(rc_map.get(repo_full_name, {}))
        rc["last_webhook_at"] = datetime.now(timezone.utc).isoformat()
        rc_map[repo_full_name] = rc
        config["repo_config"] = rc_map
        source.config = config
        flag_modified(source, "config")

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
