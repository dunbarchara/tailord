from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.core.deps_database import get_db
from app.core.deps_user import get_current_user
from app.models.database import User

router = APIRouter()


def _user_response(user: User) -> dict:
    return {
        "id": str(user.id),
        "google_sub": user.google_sub,
        "email": user.email,
        "name": user.name,
        "preferred_first_name": user.preferred_first_name,
        "preferred_last_name": user.preferred_last_name,
        "status": user.status,
        "notion_workspace_name": user.notion_workspace_name,
    }


@router.post("/users/me")
def upsert_user(
    _: str = Depends(require_api_key),
    user: User = Depends(get_current_user),
):
    """Upsert the current user from X-User-* headers. Called on every login."""
    return _user_response(user)


@router.get("/users/me")
def get_user(
    _: str = Depends(require_api_key),
    user: User = Depends(get_current_user),
):
    return _user_response(user)


class PreferredNameUpdate(BaseModel):
    preferred_first_name: str | None = None
    preferred_last_name: str | None = None


@router.patch("/users/me")
def update_user(
    body: PreferredNameUpdate,
    _: str = Depends(require_api_key),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user.preferred_first_name = body.preferred_first_name or None
    user.preferred_last_name = body.preferred_last_name or None
    db.commit()
    db.refresh(user)
    return _user_response(user)
