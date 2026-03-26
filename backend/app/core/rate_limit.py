"""Rate limiting configuration for MSM_Pro API using slowapi.

Global rate limits:
- /auth/login: 5 requests/minute per IP
- /auth/register: 3 requests/hour per IP
- /api/v1/*: 120 requests/minute per authenticated user OR IP (if anonymous)
- Webhook (/api/v1/notifications): 30 seconds per user_id+topic (already handled in main.py)

Rate limiting can be disabled via RATE_LIMIT_ENABLED=false environment variable.
"""

import logging
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize limiter with custom key_func
limiter = Limiter(key_func=get_remote_address)


def setup_rate_limiting(app: FastAPI) -> None:
    """Setup rate limiting middleware and exception handler.

    Args:
        app: FastAPI application instance

    If RATE_LIMIT_ENABLED=false, rate limiting is disabled for testing.
    """
    # Check if rate limiting is disabled
    rate_limit_enabled = getattr(settings, "rate_limit_enabled", True)

    if not rate_limit_enabled:
        logger.warning("Rate limiting is DISABLED (RATE_LIMIT_ENABLED=false)")
        return

    # Add exception handler for rate limit exceeded
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
        """Handle rate limit exceeded errors with custom response."""
        logger.warning(
            "Rate limit exceeded for %s %s (limit: %s)",
            request.method,
            request.url.path,
            exc.detail,
        )
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Too many requests. Please try again later.",
                "limit": exc.detail,
            },
        )

    # State limiter for app
    app.state.limiter = limiter
    logger.info("Rate limiting enabled for MSM_Pro API")


def get_rate_limit_key(request: Request) -> str:
    """Get the rate limit key for a request.

    For authenticated requests, use user_id (from JWT token).
    For anonymous requests, use IP address.

    Args:
        request: FastAPI Request object

    Returns:
        A string key for rate limiting (user_id or IP address)
    """
    # Try to extract user_id from JWT token in Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from app.core.security import decode_token

            token = auth_header.split(" ", 1)[1]
            payload = decode_token(token)
            if payload and "sub" in payload:
                user_id = payload["sub"]
                logger.debug("Rate limit key (user): %s", user_id)
                return f"user:{user_id}"
        except Exception:
            # If token decode fails, fall through to IP-based limiting
            pass

    # Fall back to IP address
    ip = get_remote_address(request)
    logger.debug("Rate limit key (ip): %s", ip)
    return ip


def rate_limit_auth_login() -> Optional[str]:
    """Get rate limit string for login endpoint.

    Returns:
        slowapi rate limit string (e.g., "5/minute") or None if disabled
    """
    if not getattr(settings, "rate_limit_enabled", True):
        return None
    return "5/minute"


def rate_limit_auth_register() -> Optional[str]:
    """Get rate limit string for register endpoint.

    Returns:
        slowapi rate limit string (e.g., "3/hour") or None if disabled
    """
    if not getattr(settings, "rate_limit_enabled", True):
        return None
    return "3/hour"


def rate_limit_api_general() -> Optional[str]:
    """Get rate limit string for general API endpoints.

    Returns:
        slowapi rate limit string (e.g., "120/minute") or None if disabled
    """
    if not getattr(settings, "rate_limit_enabled", True):
        return None
    return "120/minute"
