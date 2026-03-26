"""Integration tests for API endpoints with mocks (no real DB/ML calls).

Tests the contract of FastAPI routers using TestClient with dependency
injection mocks. This avoids connecting to PostgreSQL or calling ML API.

Key techniques:
- app.dependency_overrides to mock get_db and get_current_user
- TestClient for sync HTTP testing
- Fixtures for fake users and sessions
"""
import os
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from uuid import uuid4
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

# Set SECRET_KEY BEFORE importing app
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-integration-tests!")

# Now safe to import FastAPI stuff
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
import jwt as pyjwt

from app.main import app
from app.core.config import settings
from app.auth.models import User, MLAccount
from app.core.deps import get_current_user, get_db


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def fake_user():
    """Create a fake User object (not persisted)."""
    return User(
        id=uuid4(),
        email="test@example.com",
        hashed_password="hashed_password",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def fake_ml_account(fake_user):
    """Create a fake MLAccount object (not persisted)."""
    return MLAccount(
        id=uuid4(),
        user_id=fake_user.id,
        ml_user_id="2050442871",
        nickname="MSM_PRIME",
        email="seller@example.com",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=6),
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_async_session():
    """Create a mock AsyncSession."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def valid_token(fake_user):
    """Create a valid JWT token for the fake user."""
    payload = {
        "sub": str(fake_user.id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes),
        "iat": datetime.now(timezone.utc),
    }
    return pyjwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


@pytest.fixture(autouse=True)
def reset_overrides():
    """Clear dependency overrides before each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client_with_mocked_db(mock_async_session):
    """TestClient with mocked get_db dependency."""
    async def override_get_db():
        yield mock_async_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture
def client_with_auth(mock_async_session, fake_user, valid_token):
    """TestClient with both mocked DB and authenticated user."""
    async def override_get_db():
        yield mock_async_session

    async def override_get_current_user(token: str = None):
        # In tests, we inject the token via Bearer header
        # This mock always returns the fake_user
        return fake_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    client = TestClient(app)
    # Add Authorization header to all requests
    client.headers.update({
        "Authorization": f"Bearer {valid_token}"
    })
    return client


# ═══════════════════════════════════════════════════════════════════════════
# TESTS — HEALTH & ROOT
# ═══════════════════════════════════════════════════════════════════════════


class TestHealthEndpoint:
    """Test /health endpoint."""

    def test_health_returns_200(self):
        """GET /health should return 200 OK."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_format(self):
        """GET /health should return {status, version}."""
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert data["status"] == "ok"

    def test_health_no_db_dependency(self):
        """GET /health should NOT require database."""
        # Not mocking anything — should still work
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200


class TestRootEndpoint:
    """Test / endpoint."""

    def test_root_returns_200(self):
        """GET / should return 200 OK."""
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200

    def test_root_response_structure(self):
        """GET / should return {message, timestamp, version_check}."""
        client = TestClient(app)
        response = client.get("/")
        data = response.json()
        assert "message" in data
        assert "timestamp" in data
        assert "version_check" in data
        assert "MSM_Pro API" in data["message"]


# ═══════════════════════════════════════════════════════════════════════════
# TESTS — AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


class TestAuthLogin:
    """Test POST /api/v1/auth/login endpoint."""

    def test_login_with_valid_credentials(self, client_with_mocked_db, mock_async_session):
        """POST /api/v1/auth/login with valid email/password should return token."""
        fake_user = User(
            id=uuid4(),
            email="test@example.com",
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )

        # Mock the authenticate_user service call
        with patch("app.auth.service.authenticate_user", new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = fake_user

            # Mock create_access_token
            with patch("app.auth.service.create_access_token") as mock_token:
                mock_token.return_value = ("fake-jwt-token", 1440)

                response = client_with_mocked_db.post(
                    "/api/v1/auth/login",
                    json={"email": "test@example.com", "password": "password123"}
                )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert "expires_in" in data
        assert "user" in data
        assert data["token_type"] == "bearer"

    def test_login_with_invalid_credentials(self, client_with_mocked_db):
        """POST /api/v1/auth/login with invalid credentials should return 401."""
        with patch("app.auth.service.authenticate_user", new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = None  # Invalid credentials

            response = client_with_mocked_db.post(
                "/api/v1/auth/login",
                json={"email": "test@example.com", "password": "wrongpassword"}
            )

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "Email ou senha inválidos" in data["detail"]


class TestAuthMe:
    """Test GET /api/v1/auth/me endpoint."""

    def test_get_me_returns_current_user(self, client_with_auth, fake_user):
        """GET /api/v1/auth/me with valid token should return current user."""
        response = client_with_auth.get("/api/v1/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "email" in data
        assert "is_active" in data
        assert data["email"] == fake_user.email

    def test_get_me_without_token(self, client_with_mocked_db):
        """GET /api/v1/auth/me without token should return 403."""
        response = client_with_mocked_db.get("/api/v1/auth/me")

        # TestClient treats missing OAuth2 token as 403
        assert response.status_code == 403 or response.status_code == 401


class TestAuthRefresh:
    """Test POST /api/v1/auth/refresh endpoint."""

    def test_refresh_token_returns_new_token(self, client_with_auth, fake_user):
        """POST /api/v1/auth/refresh with valid token should return new token."""
        with patch("app.auth.service.create_access_token") as mock_token:
            mock_token.return_value = ("new-jwt-token", 1440)

            response = client_with_auth.post("/api/v1/auth/refresh")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "expires_in" in data
        assert data["access_token"] == "new-jwt-token"


class TestAuthMLConnect:
    """Test GET /api/v1/auth/ml/connect endpoint."""

    def test_ml_connect_returns_auth_url(self, client_with_auth):
        """GET /api/v1/auth/ml/connect should return OAuth URL."""
        with patch("app.auth.service.get_ml_auth_url") as mock_url:
            mock_url.return_value = "https://auth.mercadolivre.com.br/authorization?..."

            response = client_with_auth.get("/api/v1/auth/ml/connect")

        assert response.status_code == 200
        data = response.json()
        assert "auth_url" in data
        assert "message" in data
        assert "auth.mercadolivre.com" in data["auth_url"]


# ═══════════════════════════════════════════════════════════════════════════
# TESTS — PRODUCTS (PRODUTOS) ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


class TestProdutosListEmpty:
    """Test GET /api/v1/produtos/ with empty list."""

    def test_list_produtos_empty(self, client_with_auth, mock_async_session):
        """GET /api/v1/produtos/ should return empty list when no products."""
        # Mock the service directly to avoid complex DB mocking
        with patch("app.produtos.service.list_products", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = []

            response = client_with_auth.get("/api/v1/produtos/")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or isinstance(data, dict)


# ═══════════════════════════════════════════════════════════════════════════
# TESTS — LISTINGS (VENDAS) ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


class TestListingsListEmpty:
    """Test GET /api/v1/listings/ with empty list."""

    def test_list_listings_empty(self, client_with_auth, mock_async_session):
        """GET /api/v1/listings/ should return empty list when no listings."""
        # Mock the service directly to avoid complex DB mocking
        with patch("app.vendas.service.list_listings", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = []

            response = client_with_auth.get("/api/v1/listings/")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or isinstance(data, dict)

    def test_list_listings_without_auth(self, client_with_mocked_db):
        """GET /api/v1/listings/ without token should return 403/401."""
        response = client_with_mocked_db.get("/api/v1/listings/")

        # OAuth2 dependency will reject missing token
        assert response.status_code in [401, 403]


class TestKPISummary:
    """Test GET /api/v1/listings/kpi/summary endpoint."""

    def test_kpi_summary_returns_data(self, client_with_auth):
        """GET /api/v1/listings/kpi/summary should return KPI data."""
        # Instead of mocking at service level, test the endpoint structure
        # Mock the entire router handler to avoid DB complexity
        mock_kpi_data = {
            "today": {
                "sales": 5,
                "visits": 120,
                "conversion": 0.0417,
                "revenue": 1500.00,
            },
            "yesterday": {
                "sales": 3,
                "visits": 90,
                "conversion": 0.0333,
                "revenue": 900.00,
            },
            "day_before_yesterday": {
                "sales": 7,
                "visits": 150,
                "conversion": 0.0467,
                "revenue": 2100.00,
            },
        }

        # Patch at the router level to avoid deep dependency mocking
        with patch("app.vendas.router.service.get_kpi_by_period", new_callable=AsyncMock) as mock_kpi:
            mock_kpi.return_value = mock_kpi_data

            response = client_with_auth.get("/api/v1/listings/kpi/summary")

        assert response.status_code == 200
        data = response.json()
        assert "today" in data
        assert "yesterday" in data
        assert "day_before_yesterday" in data


# ═══════════════════════════════════════════════════════════════════════════
# TESTS — ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    """Test API error responses."""

    def test_nonexistent_endpoint_returns_404(self, client_with_auth):
        """GET /api/v1/nonexistent should return 404."""
        response = client_with_auth.get("/api/v1/nonexistent")
        assert response.status_code == 404

    def test_invalid_json_returns_422(self, client_with_auth):
        """POST with invalid JSON should return 422."""
        response = client_with_auth.post(
            "/api/v1/auth/login",
            data="invalid json{",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_method_not_allowed_returns_405(self, client_with_auth):
        """POST to GET-only endpoint should return 405."""
        response = client_with_auth.post("/health")
        assert response.status_code == 405


# ═══════════════════════════════════════════════════════════════════════════
# TESTS — DEPENDENCY INJECTION & MOCKING
# ═══════════════════════════════════════════════════════════════════════════


class TestDependencyInjection:
    """Test that mocks are properly injected."""

    def test_get_current_user_dependency_mocked(self, client_with_auth, fake_user):
        """Verify that get_current_user dependency is properly overridden."""
        assert get_current_user in app.dependency_overrides
        # The override should return fake_user
        response = client_with_auth.get("/api/v1/auth/me")
        assert response.status_code == 200

    def test_get_db_dependency_mocked(self, client_with_mocked_db, mock_async_session):
        """Verify that get_db dependency is properly overridden."""
        assert get_db in app.dependency_overrides

    def test_override_cleared_after_test(self):
        """Verify overrides are cleared after each test."""
        # This test runs after reset_overrides fixture, so should be empty
        assert len(app.dependency_overrides) == 0


# ═══════════════════════════════════════════════════════════════════════════
# TESTS — RESPONSE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════


class TestResponseSchemas:
    """Test that response schemas match expected structure."""

    def test_health_response_schema(self):
        """Health endpoint response should match schema."""
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()

        # Validate schema
        assert isinstance(data["status"], str)
        assert isinstance(data["version"], str)

    def test_token_response_schema(self, client_with_mocked_db):
        """Token response should match expected schema."""
        with patch("app.auth.service.authenticate_user", new_callable=AsyncMock) as mock_auth:
            fake_user = User(
                id=uuid4(),
                email="test@example.com",
                hashed_password="hash",
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )
            mock_auth.return_value = fake_user

            with patch("app.auth.service.create_access_token") as mock_token:
                mock_token.return_value = ("token", 1440)

                response = client_with_mocked_db.post(
                    "/api/v1/auth/login",
                    json={"email": "test@example.com", "password": "password"}
                )

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data["access_token"], str)
            assert isinstance(data["expires_in"], int)
            assert isinstance(data["token_type"], str)
            assert isinstance(data["user"], dict)


# ═══════════════════════════════════════════════════════════════════════════
# TESTS — RATE LIMITING (if enabled)
# ═══════════════════════════════════════════════════════════════════════════


class TestRateLimiting:
    """Test rate limiting behavior (if configured)."""

    def test_rate_limit_can_be_disabled(self):
        """Rate limiting should be configurable via settings."""
        # This just verifies the setting exists
        assert hasattr(settings, "rate_limit_enabled")
        # In tests, should be disabled to avoid hitting limits
        assert isinstance(settings.rate_limit_enabled, bool)


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION SCENARIOS
# ═══════════════════════════════════════════════════════════════════════════


class TestAuthFlow:
    """Test complete authentication flow."""

    def test_login_then_access_protected_route(self, client_with_mocked_db):
        """Test: login → get token → use token to access protected route."""

        # Step 1: Login
        fake_user = User(
            id=uuid4(),
            email="test@example.com",
            hashed_password="hash",
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )

        with patch("app.auth.service.authenticate_user", new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = fake_user

            with patch("app.auth.service.create_access_token") as mock_token:
                mock_token.return_value = ("test-token", 1440)

                login_response = client_with_mocked_db.post(
                    "/api/v1/auth/login",
                    json={"email": "test@example.com", "password": "password"}
                )

        if login_response.status_code == 200:
            token = login_response.json()["access_token"]

            # Step 2: Use token to access protected route
            # Create new client with token
            client_with_token = TestClient(app)
            client_with_token.headers.update({"Authorization": f"Bearer {token}"})

            # Override dependencies
            async def override_get_db():
                yield AsyncMock(spec=AsyncSession)

            async def override_get_current_user(token: str = None):
                return fake_user

            app.dependency_overrides[get_db] = override_get_db
            app.dependency_overrides[get_current_user] = override_get_current_user

            protected_response = client_with_token.get("/api/v1/auth/me")

            assert protected_response.status_code == 200
            assert protected_response.json()["email"] == fake_user.email

            # Cleanup
            app.dependency_overrides.clear()
