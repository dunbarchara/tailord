from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.core.deps_database import get_db
from app.core.deps_user import get_current_user
from app.models.database import Tailoring, User

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


@router.get("/users/public/{username_slug}")
def get_public_user(
    username_slug: str,
    _: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username_slug == username_slug).first()
    if not user:
        raise HTTPException(status_code=404, detail="Profile not found")

    public_tailorings = (
        db.query(Tailoring)
        .filter(
            Tailoring.user_id == user.id,
            (Tailoring.letter_public.is_(True) | Tailoring.posting_public.is_(True)),
        )
        .order_by(Tailoring.created_at.desc())
        .all()
    )

    return {
        "name": _display_name(user),
        "avatar_url": user.avatar_url,
        "username_slug": user.username_slug,
        "tailorings": [
            {
                "title": t.job.extracted_job.get("title") if t.job and t.job.extracted_job else None,
                "company": t.job.extracted_job.get("company") if t.job and t.job.extracted_job else None,
                "public_slug": t.public_slug,
                "letter_public": t.letter_public,
                "posting_public": t.posting_public,
                "created_at": t.created_at.isoformat(),
            }
            for t in public_tailorings
        ],
    }
