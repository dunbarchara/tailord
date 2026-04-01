import logging
import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Literal

from app.auth import require_api_key
from app.config import settings
from app.core.deps_database import get_db
from app.core.deps_user import get_current_user, require_approved_user
from app.models.database import JobChunk, Tailoring, User
from app.services.notion_export import (
    NotionAuthError,
    chunks_to_notion_markdown,
    create_notion_page,
    get_or_create_parent_page,
    get_or_create_tailoring_container,
    update_notion_page,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/notion/auth-url")
def get_notion_auth_url(
    _: str = Depends(require_api_key),
    _user: User = Depends(get_current_user),
):
    if not settings.notion_client_id:
        raise HTTPException(status_code=503, detail="Notion integration not configured")
    url = (
        "https://api.notion.com/v1/oauth/authorize"
        f"?client_id={settings.notion_client_id}"
        f"&response_type=code"
        f"&owner=user"
        f"&redirect_uri={settings.notion_redirect_uri}"
    )
    return {"url": url}


@router.post("/notion/callback")
def notion_callback(
    body: dict,
    _: str = Depends(require_api_key),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    code = body.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")

    if not settings.notion_client_id or not settings.notion_client_secret:
        raise HTTPException(status_code=503, detail="Notion integration not configured")

    response = requests.post(
        "https://api.notion.com/v1/oauth/token",
        auth=(settings.notion_client_id, settings.notion_client_secret),
        json={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.notion_redirect_uri,
        },
    )

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Notion token exchange failed")

    data = response.json()
    user.notion_access_token = data.get("access_token")
    user.notion_bot_id = data.get("bot_id")
    workspace = data.get("workspace_id") or data.get("workspace", {}).get("id")
    user.notion_workspace_id = workspace
    user.notion_workspace_name = data.get("workspace_name") or data.get("workspace", {}).get("name")
    db.commit()

    return {
        "notion_workspace_name": user.notion_workspace_name,
        "notion_workspace_id": user.notion_workspace_id,
    }


@router.delete("/notion/disconnect")
def notion_disconnect(
    _: str = Depends(require_api_key),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user.notion_access_token = None
    user.notion_bot_id = None
    user.notion_workspace_id = None
    user.notion_workspace_name = None
    db.commit()
    return {"ok": True}


@router.post("/notion/export/{tailoring_id}")
def export_tailoring_to_notion(
    tailoring_id: str,
    view: Literal["letter", "posting"] = Query(default="letter"),
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    if not user.notion_access_token:
        raise HTTPException(status_code=403, detail="Notion not connected")

    tailoring = db.query(Tailoring).filter(
        Tailoring.id == tailoring_id,
        Tailoring.user_id == user.id,
    ).first()
    if not tailoring:
        raise HTTPException(status_code=404, detail="Tailoring not found")

    job = tailoring.job
    job_title = job.extracted_job.get("title") if job and job.extracted_job else None
    company = job.extracted_job.get("company") if job and job.extracted_job else None
    container_title = " — ".join(p for p in [job_title, company] if p) or "Tailoring"

    if view == "letter":
        markdown = tailoring.generated_output
        existing_page_id = tailoring.notion_page_id
    else:
        chunks = (
            db.query(JobChunk)
            .filter(
                JobChunk.job_id == tailoring.job_id,
                JobChunk.should_render.is_(True),
                JobChunk.match_score != 0,
            )
            .order_by(JobChunk.position)
            .all()
        )
        if not chunks:
            raise HTTPException(status_code=422, detail="No enriched chunks available for posting export")
        markdown = chunks_to_notion_markdown(chunks)
        existing_page_id = tailoring.notion_posting_page_id

    page_title = "Advocacy Letter" if view == "letter" else "Job Posting"

    try:
        if existing_page_id:
            updated = update_notion_page(
                access_token=user.notion_access_token,
                page_id=existing_page_id,
                title=page_title,
                markdown=markdown,
            )
            if updated:
                logger.info("Updated Notion %s page %s for tailoring %s", view, existing_page_id, tailoring_id)
                page_url = tailoring.notion_page_url if view == "letter" else tailoring.notion_posting_page_url
                return {"page_url": page_url}

        # Lock user and tailoring rows before container creation to prevent
        # concurrent exports racing to create duplicate parent/container pages.
        user = db.query(User).filter(User.id == user.id).with_for_update().first()
        tailoring = db.query(Tailoring).filter(Tailoring.id == tailoring_id).with_for_update().first()

        # Ensure workspace-level and per-tailoring container pages exist
        parent_page_id = get_or_create_parent_page(
            access_token=user.notion_access_token,
            existing_parent_page_id=user.notion_parent_page_id,
        )
        if parent_page_id != user.notion_parent_page_id:
            user.notion_parent_page_id = parent_page_id

        is_new_container = not tailoring.notion_container_page_id

        container_page_id = get_or_create_tailoring_container(
            access_token=user.notion_access_token,
            parent_page_id=parent_page_id,
            existing_container_id=tailoring.notion_container_page_id,
            title=container_title,
            tailoring_id=tailoring_id,
            job_title=job_title,
            company=company,
            job_url=job.job_url if job else None,
        )
        if container_page_id != tailoring.notion_container_page_id:
            tailoring.notion_container_page_id = container_page_id

        # Enforce page order: Posting must be created before Letter so it
        # holds the top position in the Notion sidebar. If this is a new
        # container and we're exporting the Letter first, create an empty
        # Posting placeholder first so the ordering is preserved.
        if is_new_container and view == "letter" and not tailoring.notion_posting_page_id:
            stub_id, stub_url = create_notion_page(
                access_token=user.notion_access_token,
                parent_page_id=container_page_id,
                title="Job Posting",
                markdown="*Export the Job Posting view from Tailord to populate this page.*",
            )
            tailoring.notion_posting_page_id = stub_id
            tailoring.notion_posting_page_url = stub_url
            logger.info("Created Posting stub %s to reserve top position for tailoring %s", stub_id, tailoring_id)

        page_id, page_url = create_notion_page(
            access_token=user.notion_access_token,
            parent_page_id=container_page_id,
            title=page_title,
            markdown=markdown,
        )
    except NotionAuthError:
        logger.warning("Notion access revoked for user %s — clearing token", user.id)
        user.notion_access_token = None
        user.notion_bot_id = None
        user.notion_workspace_id = None
        user.notion_workspace_name = None
        user.notion_parent_page_id = None
        db.commit()
        raise HTTPException(status_code=403, detail="notion_disconnected")
    except ValueError as e:
        logger.error("Notion export failed for tailoring %s (%s): %s", tailoring_id, view, e)
        raise HTTPException(status_code=502, detail=str(e))

    if view == "letter":
        tailoring.notion_page_id = page_id
        tailoring.notion_page_url = page_url
    else:
        tailoring.notion_posting_page_id = page_id
        tailoring.notion_posting_page_url = page_url
    db.commit()

    logger.info("Exported tailoring %s (%s) to Notion page %s for user %s", tailoring_id, view, page_id, user.id)
    return {"page_url": page_url}
