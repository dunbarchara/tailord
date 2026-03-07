from fastapi import APIRouter, Depends

from app.auth import require_api_key
from app.core.deps_user import get_current_user
from app.models.database import User

router = APIRouter()


@router.post("/users/me")
def upsert_user(
    _: str = Depends(require_api_key),
    user: User = Depends(get_current_user),
):
    """
    Upsert the current user from X-User-Id / X-User-Email / X-User-Name headers.
    Call this on first login to ensure the User record exists before other operations.
    """
    return {
        "id": str(user.id),
        "google_sub": user.google_sub,
        "email": user.email,
        "name": user.name,
        "status": user.status,
    }
