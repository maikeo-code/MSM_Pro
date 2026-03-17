"""Tests for JWT creation and validation (PyJWT migration)."""
import os
import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

import jwt as pyjwt
from jwt.exceptions import PyJWTError as JWTError
from app.core.config import settings


def _create_token(user_id, **overrides):
    """Create a JWT without importing auth.service (avoids bcrypt dep)."""
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes),
        "iat": datetime.now(timezone.utc),
        **overrides,
    }
    return pyjwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def test_create_and_decode_jwt():
    user_id = uuid4()
    token = _create_token(user_id)

    assert isinstance(token, str)
    assert len(token) > 50

    payload = pyjwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    assert payload["sub"] == str(user_id)
    assert "exp" in payload
    assert "iat" in payload


def test_invalid_token_raises_error():
    with pytest.raises(JWTError):
        pyjwt.decode("invalid.token.here", settings.secret_key, algorithms=[settings.algorithm])


def test_wrong_secret_raises_error():
    token = _create_token(uuid4())
    with pytest.raises(JWTError):
        pyjwt.decode(token, "wrong-secret-key-that-is-long-enough!!", algorithms=["HS256"])


def test_expired_token_raises_error():
    payload = {
        "sub": str(uuid4()),
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
    }
    token = pyjwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    with pytest.raises(JWTError):
        pyjwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def test_algorithm_mismatch_raises_error():
    token = _create_token(uuid4())
    with pytest.raises(JWTError):
        pyjwt.decode(token, settings.secret_key, algorithms=["HS384"])
