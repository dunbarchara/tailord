import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.clients.storage_client import get_storage_client
from app.core.deps_database import get_db
from app.core.deps_user import get_current_user
from app.models.database import ExperienceSource, Job, Tailoring, User, UserProfile

logger = logging.getLogger(__name__)

_USERNAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
_RESERVED = frozenset(
    [
        "dashboard",
        "admin",
        "api",
        "settings",
        "login",
        "register",
        "u",
        "t",
        "auth",
        "notion",
        "help",
        "about",
        "pricing",
        "terms",
        "privacy",
        "careers",
        "blog",
        "tailord",
        "me",
        "public",
    ]
)

router = APIRouter()


def _notion_workspace_name(user: User) -> str | None:
    notion = next((i for i in user.integrations if i.provider == "notion"), None)
    if notion and notion.provider_metadata:
        return notion.provider_metadata.get("workspace_name")
    return None


def _user_response(user: User) -> dict:
    profile = user.profile
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "preferred_first_name": profile.preferred_first_name if profile else None,
        "preferred_last_name": profile.preferred_last_name if profile else None,
        "username_slug": profile.username_slug if profile else None,
        "avatar_url": profile.avatar_url if profile else None,
        "pronouns": profile.pronouns if profile else None,
        "profile_public": profile.profile_public if profile else False,
        "communication_email": profile.communication_email if profile else None,
        "status": user.status,
        "is_admin": user.is_admin,
        "notion_workspace_name": _notion_workspace_name(user),
    }


def _display_name(user: User) -> str | None:
    if user.profile:
        parts = [user.profile.preferred_first_name, user.profile.preferred_last_name]
        preferred = " ".join(p for p in parts if p).strip()
        return preferred or user.name or None
    return user.name or None


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
    pronouns: str | None = None
    communication_email: str | None = None

    @field_validator("username_slug")
    @classmethod
    def validate_username_slug(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if len(v) < 3 or len(v) > 30:
            raise ValueError("Username must be between 3 and 30 characters")
        if not _USERNAME_RE.match(v):
            raise ValueError(
                "Username may only contain lowercase letters, numbers, and hyphens, and cannot start or end with a hyphen"
            )
        if v in _RESERVED:
            raise ValueError("That username is reserved")
        return v


@router.patch("/users/me")
def update_user(
    body: UserUpdate,
    _: str = Depends(require_api_key),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = user.profile
    if profile is None:
        raise HTTPException(status_code=500, detail="User profile not found")

    if "preferred_first_name" in body.model_fields_set:
        profile.preferred_first_name = body.preferred_first_name or None
    if "preferred_last_name" in body.model_fields_set:
        profile.preferred_last_name = body.preferred_last_name or None
    if body.profile_public is not None:
        profile.profile_public = body.profile_public
    if "pronouns" in body.model_fields_set:
        profile.pronouns = body.pronouns or None
    if "communication_email" in body.model_fields_set:
        profile.communication_email = body.communication_email or None
    if "username_slug" in body.model_fields_set:
        new_slug = body.username_slug or None
        if new_slug is not None:
            existing = (
                db.query(UserProfile)
                .filter(UserProfile.username_slug == new_slug, UserProfile.user_id != user.id)
                .first()
            )
            if existing:
                raise HTTPException(status_code=409, detail="That username is already taken")
        profile.username_slug = new_slug
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
    taken = db.query(UserProfile.id).filter(UserProfile.username_slug == slug).first()
    return {"available": taken is None}


@router.get("/users/public/{username_slug}")
def get_public_user(
    username_slug: str,
    _: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    profile = db.query(UserProfile).filter(UserProfile.username_slug == username_slug).first()
    if not profile or not profile.profile_public:
        raise HTTPException(status_code=404, detail="Profile not found")

    user = profile.user
    resume_profile = None
    github_username = None
    for src in user.experience_sources:
        if src.source_type == "resume" and src.source_data:
            resume_profile = src.source_data.get("extracted")
        elif src.source_type == "github" and src.config:
            github_username = src.config.get("username")

    return {
        "name": _display_name(user),
        "avatar_url": profile.avatar_url,
        "username_slug": profile.username_slug,
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
    Permanently delete user data and leave a tombstone row with deleted_at set.
    PII (email, name) is cleared from the tombstone. The row is kept for
    platform metrics (account lifetime, churn cohorts).

    Order: storage file → tailorings → jobs → experience → claims → groups →
           integrations → identities → tombstone users row.
    """
    # 1. Delete uploaded resume file from storage
    for src in user.experience_sources:
        if src.source_type == "resume":
            storage_key = (src.config or {}).get("storage_key")
            if storage_key:
                try:
                    get_storage_client().delete_object(storage_key)
                except Exception:
                    logger.warning(
                        "Failed to delete storage object %s for user %s — continuing",
                        storage_key,
                        user.id,
                    )

    # 2. Delete tailorings (must precede jobs due to FK)
    db.query(Tailoring).filter(Tailoring.user_id == user.id).delete()

    # 3. Delete jobs (job_chunks cascade via ondelete="CASCADE")
    db.query(Job).filter(Job.user_id == user.id).delete()

    # 4. Delete experience_sources (cascade via user relationship, but delete explicitly
    #    since we're keeping the user row as tombstone)
    db.query(ExperienceSource).filter(ExperienceSource.user_id == user.id).delete()
    db.flush()

    # 5. Delete claims and groups (cascade from user but we delete explicitly
    #    since we're keeping the user row as tombstone)
    for claim in list(user.claims):
        db.delete(claim)
    for group in list(user.groups):
        db.delete(group)
    db.flush()

    # 6. Delete integrations and identities
    for integration in list(user.integrations):
        db.delete(integration)
    for identity in list(user.auth_identities):
        db.delete(identity)

    # 7. Delete profile
    if user.profile:
        db.delete(user.profile)
    db.flush()

    # 8. Tombstone: clear PII, set deleted_at — keep the row
    user.email = None
    user.name = None
    user.deleted_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("User %s deleted (tombstone preserved)", user.id)
