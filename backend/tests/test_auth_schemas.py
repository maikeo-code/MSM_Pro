"""Tests for auth schemas validation."""
import os
import pytest
from uuid import uuid4

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

from pydantic import ValidationError
from app.auth.schemas import UserCreate, UserLogin, Token, UserOut, MLAccountOut


def test_user_create_valid():
    u = UserCreate(email="test@example.com", password="12345678")
    assert u.email == "test@example.com"


def test_user_create_short_password():
    with pytest.raises(ValidationError):
        UserCreate(email="test@example.com", password="short")


def test_user_create_invalid_email():
    with pytest.raises(ValidationError):
        UserCreate(email="not-an-email", password="12345678")


def test_user_login_no_min_length():
    # Login allows any password (validation happens at auth layer)
    u = UserLogin(email="test@example.com", password="x")
    assert u.password == "x"


def test_token_schema():
    user = UserOut(id=uuid4(), email="t@t.com", is_active=True, created_at="2026-01-01T00:00:00Z")
    t = Token(access_token="abc", expires_in=3600, user=user)
    assert t.token_type == "bearer"


def test_ml_account_out_nullable_email():
    a = MLAccountOut(
        id=uuid4(), ml_user_id="123", nickname="test",
        email=None, token_expires_at=None, is_active=True,
        created_at="2026-01-01T00:00:00Z",
    )
    assert a.email is None
