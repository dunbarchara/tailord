import logging
import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.config import settings
from app.core.deps_database import get_db
from app.core.deps_user import get_current_user, require_approved_user
from app.models.database import Tailoring, User
from app.services.notion_export import create_notion_page, get_or_create_parent_page, update_notion_page

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/notion/auth-url")
def get_notion_auth_url(
    _: str = Depends(require_api_key),
    user: User = Depends(get_current_user),
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
    title = job.extracted_job.get("title") if job and job.extracted_job else None
    company = job.extracted_job.get("company") if job and job.extracted_job else None
    title_parts = [p for p in [title, company] if p]
    page_title = " — ".join(title_parts) if title_parts else "Tailoring"

    markdown = tailoring.generated_output

    try:
        # Update existing page if we have one, otherwise create
        if tailoring.notion_page_id:
            updated = update_notion_page(
                access_token=user.notion_access_token,
                page_id=tailoring.notion_page_id,
                title=page_title,
                markdown=markdown,
            )
            if updated:
                logger.info("Updated Notion page %s for tailoring %s", tailoring.notion_page_id, tailoring_id)
                return {"page_url": tailoring.notion_page_url}

        # Ensure the container page exists before creating a sub-page
        parent_page_id = get_or_create_parent_page(
            access_token=user.notion_access_token,
            existing_parent_page_id=user.notion_parent_page_id,
        )
        if parent_page_id != user.notion_parent_page_id:
            user.notion_parent_page_id = parent_page_id

        # Create new page (first export or previous page was deleted)
        page_id, page_url = create_notion_page(
            access_token=user.notion_access_token,
            parent_page_id=parent_page_id,
            title=page_title,
            markdown=markdown,
        )
    except ValueError as e:
        logger.error("Notion export failed for tailoring %s: %s", tailoring_id, e)
        raise HTTPException(status_code=502, detail=str(e))

    tailoring.notion_page_id = page_id
    tailoring.notion_page_url = page_url
    db.commit()

    logger.info("Exported tailoring %s to Notion page %s for user %s", tailoring_id, page_id, user.id)
    return {"page_url": page_url}
