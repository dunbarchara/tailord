import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.config import settings
from app.core.deps_database import get_db
from app.core.deps_user import get_current_user
from app.models.database import User

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
