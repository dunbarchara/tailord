import json
import logging
import warnings

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

logger = logging.getLogger(__name__)


class EncryptedJSON(TypeDecorator):
    """Stores a dict as Fernet-encrypted text. Falls back to plaintext when
    FIELD_ENCRYPTION_KEY is unset (local dev only) or on read of legacy rows."""

    impl = Text
    cache_ok = True

    def _fernet(self):
        from app.config import settings

        if not settings.field_encryption_key:
            return None
        from cryptography.fernet import Fernet

        return Fernet(settings.field_encryption_key.encode())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        raw = json.dumps(value)
        f = self._fernet()
        if f is None:
            warnings.warn(
                "FIELD_ENCRYPTION_KEY not set — storing credentials as plaintext",
                stacklevel=2,
            )
            return raw
        return f.encrypt(raw.encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        f = self._fernet()
        if f is not None:
            try:
                from cryptography.fernet import InvalidToken

                return json.loads(f.decrypt(value.encode()))
            except (InvalidToken, Exception):
                pass  # fall through to plaintext for legacy rows
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            logger.error("Failed to decrypt or parse credentials column value")
            return None
