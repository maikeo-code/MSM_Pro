"""
OAuth CSRF state generation and verification.

The state parameter in OAuth flows must be an unguessable nonce to prevent CSRF attacks.
This module generates HMAC-signed state tokens with TTL expiration.

State format: user_id:timestamp:hmac_signature
"""
import hashlib
import hmac
import time
from uuid import UUID

from fastapi import HTTPException

from app.core.config import settings

# OAuth state timeout (10 minutes)
OAUTH_STATE_TTL = 600


def generate_oauth_state(user_id: UUID) -> str:
    """Generate a CSRF-safe OAuth state: user_id:timestamp:hmac_signature."""
    ts = str(int(time.time()))
    payload = f"{user_id}:{ts}"
    sig = hmac.new(
        settings.secret_key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()[:16]
    return f"{payload}:{sig}"


def verify_oauth_state(state: str) -> UUID:
    """Verify and extract user_id from OAuth state. Raises HTTPException on failure."""
    parts = state.split(":")
    if len(parts) < 3:
        raise HTTPException(status_code=400, detail="State inválido")

    user_id_str, ts_str, sig = parts[0], parts[1], parts[2]

    # Verify HMAC
    payload = f"{user_id_str}:{ts_str}"
    expected_sig = hmac.new(
        settings.secret_key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()[:16]
    if not hmac.compare_digest(sig, expected_sig):
        raise HTTPException(status_code=400, detail="State inválido (assinatura)")

    # Verify TTL
    try:
        ts = int(ts_str)
        if time.time() - ts > OAUTH_STATE_TTL:
            raise HTTPException(status_code=400, detail="State expirado")
    except ValueError:
        raise HTTPException(status_code=400, detail="State inválido (timestamp)")

    try:
        return UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="State inválido (user_id)")
