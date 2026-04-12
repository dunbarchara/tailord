import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.core.deps_database import get_db
from app.core.deps_user import require_admin
from app.models.database import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _user_row(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "status": user.status,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat(),
    }


@router.get("/users")
def list_users(
    _: str = Depends(require_api_key),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    logger.info("admin list_users: requested by admin_id=%s, total=%d", admin.id, len(users))
    return [_user_row(u) for u in users]


@router.post("/users/{user_id}/approve")
def approve_user(
    user_id: str,
    _: str = Depends(require_api_key),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.status = "approved"
    db.commit()
    logger.info("admin approve_user: user_id=%s approved by admin_id=%s", user.id, admin.id)
    return _user_row(user)


@router.post("/users/{user_id}/revoke")
def revoke_user(
    user_id: str,
    _: str = Depends(require_api_key),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Cannot revoke admin accounts")

    user.status = "pending"
    db.commit()
    logger.info("admin revoke_user: user_id=%s revoked by admin_id=%s", user.id, admin.id)
    return _user_row(user)
