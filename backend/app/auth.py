from fastapi import Header, HTTPException

from app.config import settings


def require_api_key(x_api_key: str = Header(...)):
    """FastAPI dependency: validates the X-API-Key header against settings.api_key.

    Used on every route to ensure only the trusted frontend (or other internal
    callers with the shared secret) can reach the backend. Not a user auth check —
    that's handled by get_current_user / require_approved_user.
    """
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
