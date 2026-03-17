"""Tests for OAuth CSRF state generation and verification."""
import os
import time
import pytest
from uuid import uuid4

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

from app.auth.oauth_state import generate_oauth_state as _generate_oauth_state, verify_oauth_state as _verify_oauth_state, OAUTH_STATE_TTL as _OAUTH_STATE_TTL
from fastapi import HTTPException


def test_generate_state_format():
    uid = uuid4()
    state = _generate_oauth_state(uid)
    parts = state.split(":")
    assert len(parts) == 3
    assert parts[0] == str(uid)


def test_verify_state_roundtrip():
    uid = uuid4()
    state = _generate_oauth_state(uid)
    result = _verify_oauth_state(state)
    assert result == uid


def test_verify_state_invalid_signature():
    uid = uuid4()
    state = _generate_oauth_state(uid)
    # Tamper with signature
    parts = state.split(":")
    parts[2] = "0000000000000000"
    tampered = ":".join(parts)
    with pytest.raises(HTTPException) as exc_info:
        _verify_oauth_state(tampered)
    assert exc_info.value.status_code == 400


def test_verify_state_invalid_format():
    with pytest.raises(HTTPException):
        _verify_oauth_state("invalid")


def test_verify_state_missing_parts():
    with pytest.raises(HTTPException):
        _verify_oauth_state("only:two")


def test_verify_state_expired(monkeypatch):
    uid = uuid4()
    state = _generate_oauth_state(uid)
    # Simulate time passing beyond TTL
    future = time.time() + _OAUTH_STATE_TTL + 100
    monkeypatch.setattr(time, "time", lambda: future)
    with pytest.raises(HTTPException) as exc_info:
        _verify_oauth_state(state)
    assert "expirado" in exc_info.value.detail


def test_verify_state_tampered_user_id():
    uid = uuid4()
    state = _generate_oauth_state(uid)
    parts = state.split(":")
    parts[0] = str(uuid4())  # different user
    tampered = ":".join(parts)
    with pytest.raises(HTTPException):
        _verify_oauth_state(tampered)


def test_verify_state_tampered_timestamp():
    uid = uuid4()
    state = _generate_oauth_state(uid)
    parts = state.split(":")
    parts[1] = "9999999999"
    tampered = ":".join(parts)
    with pytest.raises(HTTPException):
        _verify_oauth_state(tampered)
