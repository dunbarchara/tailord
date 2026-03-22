from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.core.deps_database import get_db
from app.core.deps_user import get_current_user
from app.models.database import Experience, User

router = APIRouter()


def _user_response(user: User) -> dict:
    return {
        "id": str(user.id),
        "google_sub": user.google_sub,
        "email": user.email,
        "name": user.name,
        "preferred_first_name": user.preferred_first_name,
        "preferred_last_name": user.preferred_last_name,
        "username_slug": user.username_slug,
        "avatar_url": user.avatar_url,
        "profile_public": user.profile_public,
        "status": user.status,
        "notion_workspace_name": user.notion_workspace_name,
    }


def _display_name(user: User) -> str | None:
    parts = [user.preferred_first_name, user.preferred_last_name]
    preferred = " ".join(p for p in parts if p).strip()
    return preferred or user.name or None


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


class UserUpdate(BaseModel):
    preferred_first_name: str | None = None
    preferred_last_name: str | None = None
    profile_public: bool | None = None


@router.patch("/users/me")
def update_user(
    body: UserUpdate,
    _: str = Depends(require_api_key),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if "preferred_first_name" in body.model_fields_set:
        user.preferred_first_name = body.preferred_first_name or None
    if "preferred_last_name" in body.model_fields_set:
        user.preferred_last_name = body.preferred_last_name or None
    if body.profile_public is not None:
        user.profile_public = body.profile_public
    db.commit()
    db.refresh(user)
    return _user_response(user)


@router.get("/users/public/{username_slug}")
def get_public_user(
    username_slug: str,
    _: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username_slug == username_slug).first()
    if not user or not user.profile_public:
        raise HTTPException(status_code=404, detail="Profile not found")

    experience = db.query(Experience).filter(Experience.user_id == user.id).first()
    resume_profile = None
    github_username = None
    if experience:
        if experience.extracted_profile:
            resume_profile = experience.extracted_profile.get("resume")
        github_username = experience.github_username

    return {
        "name": _display_name(user),
        "avatar_url": user.avatar_url,
        "username_slug": user.username_slug,
        "github_username": github_username,
        "profile": resume_profile,
    }
