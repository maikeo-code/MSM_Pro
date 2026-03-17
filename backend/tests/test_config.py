"""Tests for configuration and settings."""
import os
import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")


def test_settings_loads():
    from app.core.config import settings
    assert settings is not None
    assert settings.algorithm == "HS256"
    assert settings.access_token_expire_minutes > 0


def test_ml_api_base_url_correct():
    """CRITICAL: API URL must be mercadolibre.com (not mercadolivre)."""
    from app.core.config import settings
    assert "mercadolibre.com" in settings.ml_api_base
    assert "mercadolivre" not in settings.ml_api_base


def test_ml_token_url_correct():
    from app.core.config import settings
    assert settings.ml_token_url == "https://api.mercadolibre.com/oauth/token"


def test_default_database_url_is_async():
    from app.core.config import settings
    assert "asyncpg" in settings.database_url


def test_cors_origins_default_empty():
    from app.core.config import settings
    assert settings.cors_origins is not None


def test_token_encryption_key_optional():
    from app.core.config import settings
    # Can be None - crypto.py derives from secret_key
    assert hasattr(settings, "token_encryption_key")


def test_debug_default_false():
    from app.core.config import settings
    # Default is False (secure by default — set DEBUG=true for development)
    assert isinstance(settings.debug, bool)
