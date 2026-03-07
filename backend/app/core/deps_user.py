from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.core.deps_database import get_db
from app.models.database import User


def get_current_user(
    x_user_id: str = Header(...),
    x_user_email: str = Header(default=""),
    x_user_name: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """
    Reads X-User-Id (google_sub) from request headers and upserts the User record.
    Also accepts optional X-User-Email and X-User-Name for profile enrichment.
    Trusted because all routes already require X-API-Key.
    """
    user = db.query(User).filter(User.google_sub == x_user_id).first()
    if user:
        if x_user_email:
            user.email = x_user_email
        if x_user_name:
            user.name = x_user_name
        db.commit()
    else:
        user = User(
            google_sub=x_user_id,
            email=x_user_email or x_user_id,
            name=x_user_name,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def require_approved_user(user: User = Depends(get_current_user)) -> User:
    """
    Extends get_current_user with an approval gate.
    Raises 403 if the user's status is not 'approved'.
    """
    if user.status != "approved":
        raise HTTPException(status_code=403, detail="Account pending approval")
    return user
