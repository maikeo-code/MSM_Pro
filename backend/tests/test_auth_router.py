"""Testes de integração para o router de auth usando FastAPI TestClient + SQLite."""
import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(test_engine):
    """AsyncClient com DB SQLite injetado."""
    factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _register(client, email="user@test.com", password="senha1234"):
    return await client.post("/api/v1/auth/register", json={"email": email, "password": password})


async def _login(client, email="user@test.com", password="senha1234"):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


async def _get_token(client, email="user@test.com", password="senha1234"):
    await _register(client, email, password)
    resp = await _login(client, email, password)
    return resp.json()["access_token"]


# ===========================================================================
# Registro
# ===========================================================================

@pytest.mark.asyncio
async def test_register_novo_usuario(client):
    resp = await _register(client, "novo@test.com", "senha12345")
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "novo@test.com"
    assert data["is_active"] is True
    assert "id" in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_email_duplicado_retorna_409(client):
    await _register(client, "dup@test.com", "senha12345")
    resp = await _register(client, "dup@test.com", "outrasenha")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_senha_curta_retorna_422(client):
    resp = await _register(client, "short@test.com", "abc")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_email_invalido_retorna_422(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "nao-e-email", "password": "senha1234"},
    )
    assert resp.status_code == 422


# ===========================================================================
# Login
# ===========================================================================

@pytest.mark.asyncio
async def test_login_credenciais_validas_retorna_jwt(client):
    await _register(client, "login@test.com", "senha12345")
    resp = await _login(client, "login@test.com", "senha12345")
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    assert data["user"]["email"] == "login@test.com"


@pytest.mark.asyncio
async def test_login_senha_errada_retorna_401(client):
    await _register(client, "errado@test.com", "correta123")
    resp = await _login(client, "errado@test.com", "errada999")
    assert resp.status_code == 401
    assert "inválidos" in resp.json()["detail"].lower() or "inv" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_email_inexistente_retorna_401(client):
    resp = await _login(client, "fantasma@test.com", "qualquer")
    assert resp.status_code == 401


# ===========================================================================
# GET /me
# ===========================================================================

@pytest.mark.asyncio
async def test_get_me_com_token_valido(client):
    token = await _get_token(client, "me@test.com", "senha1234")
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@test.com"


@pytest.mark.asyncio
async def test_get_me_sem_token_retorna_401(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_token_invalido_retorna_401(client):
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer token.invalido.aqui"},
    )
    assert resp.status_code == 401


# ===========================================================================
# POST /refresh (JWT)
# ===========================================================================

@pytest.mark.asyncio
async def test_refresh_jwt_retorna_novo_token(client):
    token = await _get_token(client, "refresh@test.com", "senha1234")
    resp = await client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    # Token retornado é uma string JWT válida (3 partes separadas por ponto)
    parts = data["access_token"].split(".")
    assert len(parts) == 3


# ===========================================================================
# GET /ml/connect
# ===========================================================================

@pytest.mark.asyncio
async def test_ml_connect_retorna_url_com_offline_access(client):
    token = await _get_token(client, "connect@test.com", "senha1234")
    resp = await client.get(
        "/api/v1/auth/ml/connect",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "auth_url" in data
    assert "offline_access" in data["auth_url"]
    assert "response_type=code" in data["auth_url"]


# ===========================================================================
# GET /ml/accounts
# ===========================================================================

@pytest.mark.asyncio
async def test_listar_contas_ml_vazio(client):
    token = await _get_token(client, "accounts@test.com", "senha1234")
    resp = await client.get(
        "/api/v1/auth/ml/accounts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ===========================================================================
# GET /preferences
# ===========================================================================

@pytest.mark.asyncio
async def test_get_preferences_default_retorna_null(client):
    token = await _get_token(client, "pref@test.com", "senha1234")
    resp = await client.get(
        "/api/v1/auth/preferences",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["active_ml_account_id"] is None


@pytest.mark.asyncio
async def test_update_preferences_conta_inexistente_retorna_404(client):
    token = await _get_token(client, "pref2@test.com", "senha1234")
    resp = await client.put(
        "/api/v1/auth/preferences",
        headers={"Authorization": f"Bearer {token}"},
        json={"active_ml_account_id": str(uuid4())},
    )
    assert resp.status_code == 404
