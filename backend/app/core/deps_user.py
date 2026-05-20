import re
import unicodedata

import structlog
import structlog.contextvars
from fastapi import Depends, Header, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps_database import get_db
from app.models.database import User

logger = structlog.get_logger(__name__)


def _slugify(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = name.lower().strip()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s_]+", "-", name).strip("-")
    return name[:30]


def _generate_username_slug(name: str | None, db: Session) -> str:
    base = _slugify(name or "") or "user"
    slug = base
    counter = 2
    while db.query(User).filter(User.username_slug == slug).first():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def get_current_user(
    x_user_id: str = Header(...),
    x_user_email: str = Header(default=""),
    x_user_name: str | None = Header(default=None),
    x_user_image: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """
    Reads X-User-Id (google_sub) from request headers and upserts the User record.
    Also accepts optional X-User-Email, X-User-Name, X-User-Image for profile enrichment.
    Trusted because all routes already require X-API-Key.
    """
    user = db.query(User).filter(User.google_sub == x_user_id).first()
    if user:
        if x_user_email:
            user.email = x_user_email
        if x_user_name:
            user.name = x_user_name
        if x_user_image:
            user.avatar_url = x_user_image
        if not user.username_slug:
            display_name = (
                " ".join(filter(None, [user.preferred_first_name, user.preferred_last_name]))
                or user.name
            )
            user.username_slug = _generate_username_slug(display_name, db)
        db.commit()
        db.refresh(user)
    else:
        logger.info("user_created", email=x_user_email)
        user = User(
            google_sub=x_user_id,
            email=x_user_email or x_user_id,
            name=x_user_name,
            avatar_url=x_user_image,
        )
        db.add(user)
        try:
            db.flush()  # get id before generating slug
        except IntegrityError:
            # Another concurrent request inserted the same google_sub — re-query and continue.
            db.rollback()
            user = db.query(User).filter(User.google_sub == x_user_id).first()
            structlog.contextvars.bind_contextvars(user_id=str(user.id))
            return user
        display_name = x_user_name
        user.username_slug = _generate_username_slug(display_name, db)
        db.commit()
        db.refresh(user)

    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """
    Extends get_current_user with an admin gate.
    Raises 403 if the user does not have is_admin=True in the DB.
    Always reads from the DB — never trusts client-supplied claims.

    Async so that bind_contextvars runs in the event loop context and is
    visible to subsequent log calls — sync dependencies run in a thread pool
    and their context mutations do not propagate back.
    """
    structlog.contextvars.bind_contextvars(user_id=str(user.id))
    if not user.is_admin:
        logger.warning("require_admin_rejected")
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_approved_user(user: User = Depends(get_current_user)) -> User:
    """
    Extends get_current_user with an approval gate.
    Raises 403 if the user's status is not 'approved'.

    Async so that bind_contextvars runs in the event loop context and is
    visible to subsequent log calls — sync dependencies run in a thread pool
    and their context mutations do not propagate back.
    """
    structlog.contextvars.bind_contextvars(user_id=str(user.id))
    if user.status != "approved":
        logger.warning("require_approved_user_rejected", status=user.status)
        raise HTTPException(status_code=403, detail="Account pending approval")
    return user
