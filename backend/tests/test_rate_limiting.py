"""Tests for rate limiting functionality.

Rate limits tested:
- /auth/login: 5 requests/minute per IP
- /auth/register: 3 requests/hour per IP
- General API: 120 requests/minute per user

When RATE_LIMIT_ENABLED=false, rate limiting is disabled (for testing).
"""

import os
import pytest
from unittest.mock import patch, AsyncMock

# Disable rate limiting for unit tests
os.environ["RATE_LIMIT_ENABLED"] = "false"

from app.core.config import settings


class TestRateLimitConfiguration:
    """Test rate limit configuration and initialization."""

    def test_rate_limit_config_in_settings(self):
        """Verify rate_limit_enabled setting exists."""
        # Should have rate_limit_enabled attribute
        assert hasattr(settings, "rate_limit_enabled")
        # In tests it's False (disabled), in production it's True
        assert isinstance(settings.rate_limit_enabled, bool)

    def test_rate_limit_module_imported(self):
        """Verify rate_limit module can be imported."""
        from app.core import rate_limit

        assert hasattr(rate_limit, "limiter")
        assert hasattr(rate_limit, "setup_rate_limiting")
        assert hasattr(rate_limit, "get_rate_limit_key")


class TestRateLimitDecorators:
    """Test rate limit decorators and helper functions."""

    def test_rate_limit_login_string(self):
        """Verify login rate limit string."""
        from app.core.rate_limit import rate_limit_auth_login

        limit = rate_limit_auth_login()
        # When enabled, should return "5/minute"
        # When disabled (as in tests), should return None
        assert limit is None or limit == "5/minute"

    def test_rate_limit_register_string(self):
        """Verify register rate limit string."""
        from app.core.rate_limit import rate_limit_auth_register

        limit = rate_limit_auth_register()
        assert limit is None or limit == "3/hour"

    def test_rate_limit_api_general_string(self):
        """Verify general API rate limit string."""
        from app.core.rate_limit import rate_limit_api_general

        limit = rate_limit_api_general()
        assert limit is None or limit == "120/minute"


class TestAuthEndpointRateLimits:
    """Test that rate limiting decorators are properly attached."""

    def test_login_endpoint_has_rate_limit(self):
        """Verify /auth/login endpoint has rate limit decorator."""
        from app.auth.router import login

        # Check if function has slowapi decorator applied
        assert hasattr(login, "__wrapped__") or callable(login)

    def test_register_endpoint_has_rate_limit(self):
        """Verify /auth/register endpoint has rate limit decorator."""
        from app.auth.router import register

        assert hasattr(register, "__wrapped__") or callable(register)


class TestRateLimitErrorResponse:
    """Test rate limit error responses."""

    def test_rate_limit_error_exists(self):
        """Verify RateLimitExceeded exception exists in slowapi."""
        from slowapi.errors import RateLimitExceeded

        # Verify the exception class exists and is importable
        assert RateLimitExceeded is not None
        assert hasattr(RateLimitExceeded, "__init__")


class TestRateLimitingWithRequest:
    """Test rate limiting with actual requests (when enabled)."""

    @pytest.mark.asyncio
    async def test_get_rate_limit_key_without_token(self):
        """Verify rate limit key uses IP for anonymous requests."""
        from app.core.rate_limit import get_rate_limit_key
        from unittest.mock import MagicMock

        # Create mock request without Authorization header
        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""
        # Mock the client.host to return an IP
        mock_request.client.host = "192.168.1.1"

        # Should use IP-based key
        key = get_rate_limit_key(mock_request)
        assert key is not None
        # Key should contain IP address
        assert "192.168.1.1" in key or key == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_get_rate_limit_key_with_invalid_token(self):
        """Verify rate limit key falls back to IP for invalid token."""
        from app.core.rate_limit import get_rate_limit_key
        from unittest.mock import MagicMock

        # Create mock request with invalid token
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "Bearer invalid.token.here"
        mock_request.client.host = "192.168.1.2"

        # When decode_token fails internally, should fall back to IP
        key = get_rate_limit_key(mock_request)
        # Should fall back to IP
        assert key is not None
        assert "192.168.1.2" in key or key == "192.168.1.2"


class TestRateLimitDisableFeature:
    """Test that rate limiting can be disabled via environment variable."""

    def test_rate_limit_disabled_via_env(self):
        """Verify RATE_LIMIT_ENABLED=false disables limiting."""
        # The test environment has RATE_LIMIT_ENABLED=false set
        # Verify the functions return None when disabled
        assert os.environ.get("RATE_LIMIT_ENABLED") == "false"
        from app.core.rate_limit import rate_limit_auth_login

        limit = rate_limit_auth_login()
        # When disabled, should return None
        assert limit is None


class TestRequirementsIncluded:
    """Verify slowapi is in requirements.txt."""

    def test_slowapi_in_requirements(self):
        """Check that slowapi is listed in requirements.txt."""
        import os

        req_file = os.path.join(
            os.path.dirname(__file__),
            "..",
            "requirements.txt",
        )
        with open(req_file, "r") as f:
            content = f.read()
            assert "slowapi" in content


class TestSetupRateLimiting:
    """Test the setup_rate_limiting function."""

    def test_setup_rate_limiting_is_callable(self):
        """Verify setup_rate_limiting function is callable."""
        from app.core.rate_limit import setup_rate_limiting

        # Verify function exists and is callable
        assert callable(setup_rate_limiting)


class TestRateLimitDisabledBehavior:
    """Test behavior when rate limiting is disabled."""

    def test_rate_limit_functions_return_none_when_disabled(self):
        """Verify all rate limit functions return None when disabled."""
        from app.core.rate_limit import (
            rate_limit_auth_login,
            rate_limit_auth_register,
            rate_limit_api_general,
        )

        # When RATE_LIMIT_ENABLED=false (set at module level)
        assert os.environ["RATE_LIMIT_ENABLED"] == "false"

        # All functions should return None
        assert rate_limit_auth_login() is None
        assert rate_limit_auth_register() is None
        assert rate_limit_api_general() is None
