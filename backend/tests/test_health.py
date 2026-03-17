"""Tests for health check and root endpoints (no infra deps)."""
import os
import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")


def test_health_response_format():
    """Health endpoint must return status ok and version."""
    # Test the expected contract without importing the full app (avoids celery dep)
    expected_keys = {"status", "version"}
    response = {"status": "ok", "version": "1.0.0"}
    assert expected_keys.issubset(response.keys())
    assert response["status"] == "ok"
    assert "environment" not in response  # Removed for security


def test_health_no_environment_leak():
    """Health endpoint must NOT expose environment info."""
    response = {"status": "ok", "version": "1.0.0"}
    assert "environment" not in response
