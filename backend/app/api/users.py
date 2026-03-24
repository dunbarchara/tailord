import logging
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.clients.storage_client import get_storage_client
from app.core.deps_database import get_db
from app.core.deps_user import get_current_user
from app.models.database import Experience, Job, Tailoring, User

logger = logging.getLogger(__name__)

_USERNAME_RE = re.compile(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$')
_RESERVED = frozenset([
    'dashboard', 'admin', 'api', 'settings', 'login', 'register',
    'u', 't', 'auth', 'notion', 'help', 'about', 'pricing', 'terms',
    'privacy', 'careers', 'blog', 'tailord', 'me', 'public',
])

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
    username_slug: str | None = None

    @field_validator('username_slug')
    @classmethod
    def validate_username_slug(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if len(v) < 3 or len(v) > 30:
            raise ValueError('Username must be between 3 and 30 characters')
        if not _USERNAME_RE.match(v):
            raise ValueError('Username may only contain lowercase letters, numbers, and hyphens, and cannot start or end with a hyphen')
        if v in _RESERVED:
            raise ValueError('That username is reserved')
        return v


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
    if 'username_slug' in body.model_fields_set:
        new_slug = body.username_slug or None
        if new_slug is not None:
            existing = db.query(User).filter(User.username_slug == new_slug, User.id != user.id).first()
            if existing:
                raise HTTPException(status_code=409, detail='That username is already taken')
        user.username_slug = new_slug
    db.commit()
    db.refresh(user)
    return _user_response(user)


@router.get("/users/check-username/{slug}")
def check_username(
    slug: str,
    _: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    if len(slug) < 3 or len(slug) > 30 or not _USERNAME_RE.match(slug) or slug in _RESERVED:
        return {"available": False}
    taken = db.query(User.id).filter(User.username_slug == slug).first()
    return {"available": taken is None}


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


@router.delete("/users/me", status_code=204)
def delete_user(
    _: str = Depends(require_api_key),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Permanently delete the current user and all associated data.
    Order: storage file → tailorings → jobs → experience → user.
    """
    # 1. Delete uploaded resume file from storage
    experience = db.query(Experience).filter(Experience.user_id == user.id).first()
    if experience and experience.s3_key:
        try:
            get_storage_client().delete_object(experience.s3_key)
        except Exception:
            logger.warning("Failed to delete storage object %s for user %s — continuing", experience.s3_key, user.id)

    # 2. Delete tailorings (must precede jobs due to FK)
    db.query(Tailoring).filter(Tailoring.user_id == user.id).delete()

    # 3. Delete jobs (job_chunks cascade via ondelete="CASCADE")
    db.query(Job).filter(Job.user_id == user.id).delete()

    # 4. Delete experience
    if experience:
        db.delete(experience)
        db.flush()

    # 5. Delete user
    db.delete(user)
    db.commit()
    logger.info("User %s deleted", user.id)
