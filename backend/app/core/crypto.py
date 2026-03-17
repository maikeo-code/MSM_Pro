"""Transparent Fernet encryption for SQLAlchemy columns.

Usage in models:
    from app.core.crypto import EncryptedString
    access_token: Mapped[str | None] = mapped_column(EncryptedString(2000), nullable=True)

All existing code that reads/writes the column continues to work unchanged.
Plaintext values from before encryption are handled gracefully (decrypt falls back to raw value).
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from app.core.config import settings

logger = logging.getLogger(__name__)

_fernet_instance: Fernet | None = None


def _get_fernet() -> Fernet:
    """Get or create a Fernet instance from the encryption key."""
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    key = getattr(settings, "token_encryption_key", "") or ""
    if not key:
        # Derive a key from SECRET_KEY if no explicit encryption key is set
        key_bytes = hashlib.sha256(settings.secret_key.encode()).digest()
        key = base64.urlsafe_b64encode(key_bytes).decode()

    # Ensure the key is valid Fernet format (32 url-safe base64 bytes)
    try:
        _fernet_instance = Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        # If the key is not valid Fernet format, derive one
        key_bytes = hashlib.sha256(key.encode()).digest()
        derived = base64.urlsafe_b64encode(key_bytes)
        _fernet_instance = Fernet(derived)

    return _fernet_instance


class EncryptedString(TypeDecorator):
    """A SQLAlchemy type that transparently encrypts/decrypts string values using Fernet.

    On write: encrypts the plaintext value before storing.
    On read: decrypts the stored value. If decryption fails (legacy plaintext data),
    returns the raw value unchanged — it will be encrypted on next write.
    """

    impl = String
    cache_ok = True

    def __init__(self, length: int = 2000, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.impl = String(length)

    def process_bind_param(self, value, dialect):
        """Encrypt before writing to DB."""
        if value is None:
            return None
        try:
            f = _get_fernet()
            return f.encrypt(value.encode("utf-8")).decode("utf-8")
        except Exception:
            logger.warning("Failed to encrypt token, storing as-is")
            return value

    def process_result_value(self, value, dialect):
        """Decrypt after reading from DB. Falls back to raw value for legacy plaintext."""
        if value is None:
            return None
        try:
            f = _get_fernet()
            return f.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            # Legacy plaintext token — return as-is, will be encrypted on next write
            return value
        except Exception:
            logger.warning("Failed to decrypt token, returning as-is")
            return value
