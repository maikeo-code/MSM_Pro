"""Testes unitários para app.auth.service — sem banco real (SQLite in-memory)."""
import os
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.database import Base
from app.auth.models import User, MLAccount
from app.auth import service


# ---------------------------------------------------------------------------
# Fixtures de banco SQLite in-memory
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db(db_engine):
    factory = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_user(db, email="test@example.com", password="senha1234"):
    return await service.create_user(db, email, password)


# ===========================================================================
# Testes de senha
# ===========================================================================

def test_hash_password_is_bcrypt():
    hashed = service.hash_password("minhasenha123")
    assert hashed.startswith("$2b$")


def test_verify_password_correct():
    hashed = service.hash_password("correta123")
    assert service.verify_password("correta123", hashed) is True


def test_verify_password_incorrect():
    hashed = service.hash_password("correta123")
    assert service.verify_password("errada999", hashed) is False


# ===========================================================================
# Testes de JWT
# ===========================================================================

def test_create_access_token_returns_tuple():
    user_id = uuid4()
    token, expires_in = service.create_access_token(user_id)
    assert isinstance(token, str)
    assert len(token) > 40
    assert isinstance(expires_in, int)
    assert expires_in > 0


def test_create_access_token_decodable():
    import jwt as pyjwt
    from app.core.config import settings

    user_id = uuid4()
    token, _ = service.create_access_token(user_id)
    payload = pyjwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    assert payload["sub"] == str(user_id)


def test_expired_token_is_rejected():
    import jwt as pyjwt
    from app.core.config import settings

    payload = {
        "sub": str(uuid4()),
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
    }
    token = pyjwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    with pytest.raises(Exception):
        pyjwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


# ===========================================================================
# Testes de CRUD de usuário
# ===========================================================================

@pytest.mark.asyncio
async def test_create_user_success(db):
    user = await _create_user(db, "novo@test.com", "senha12345")
    assert user.id is not None
    assert user.email == "novo@test.com"
    assert user.is_active is True
    # senha não salva em plaintext
    assert user.hashed_password != "senha12345"


@pytest.mark.asyncio
async def test_create_user_duplicate_email_raises_409(db):
    from fastapi import HTTPException
    await _create_user(db, "dup@test.com", "senha12345")
    with pytest.raises(HTTPException) as exc_info:
        await _create_user(db, "dup@test.com", "outrasenha")
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_authenticate_user_valid(db):
    await _create_user(db, "auth@test.com", "senha12345")
    user = await service.authenticate_user(db, "auth@test.com", "senha12345")
    assert user is not None
    assert user.email == "auth@test.com"


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password(db):
    await _create_user(db, "wrongpw@test.com", "correta123")
    user = await service.authenticate_user(db, "wrongpw@test.com", "errada999")
    assert user is None


@pytest.mark.asyncio
async def test_authenticate_user_email_not_found(db):
    user = await service.authenticate_user(db, "naoexiste@test.com", "qualquer")
    assert user is None


# ===========================================================================
# Testes de OAuth — get_ml_auth_url
# ===========================================================================

def test_get_ml_auth_url_contains_required_params():
    url = service.get_ml_auth_url(state="meu_estado")
    assert "response_type=code" in url
    assert "redirect_uri" in url
    assert "scope" in url
    assert "offline_access" in url
    assert "state=meu_estado" in url


def test_get_ml_auth_url_no_state():
    url = service.get_ml_auth_url()
    assert "response_type=code" in url
    assert "state" not in url


def test_get_ml_auth_url_uses_ml_auth_domain():
    url = service.get_ml_auth_url()
    # Deve usar o domínio de auth do ML
    assert "mercadolivre.com.br" in url or "mercadolibre.com" in url


def test_get_ml_auth_url_includes_write_scope():
    url = service.get_ml_auth_url()
    assert "write" in url


# ===========================================================================
# Testes de exchange_code_for_token — mock httpx
# ===========================================================================

@pytest.mark.asyncio
async def test_exchange_code_for_token_success():
    token_payload = {
        "access_token": "APP_USR-xxx",
        "refresh_token": "TG-yyy",
        "expires_in": 21600,
        "user_id": 123456,
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = token_payload

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await service.exchange_code_for_token("valid_code_123")

    assert result["access_token"] == "APP_USR-xxx"
    assert result["refresh_token"] == "TG-yyy"


@pytest.mark.asyncio
async def test_exchange_code_for_token_invalid_code_raises_502():
    from fastapi import HTTPException

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "invalid_grant"

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        with pytest.raises(HTTPException) as exc_info:
            await service.exchange_code_for_token("codigo_invalido")

    assert exc_info.value.status_code == 502


# ===========================================================================
# Testes de _exchange_refresh_token (helper interno)
# ===========================================================================

@pytest.mark.asyncio
async def test_exchange_refresh_token_success():
    token_payload = {
        "access_token": "APP_USR-new",
        "refresh_token": "TG-new",
        "expires_in": 21600,
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = token_payload

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await service._exchange_refresh_token("valid_refresh_token")

    assert result is not None
    assert result["access_token"] == "APP_USR-new"


@pytest.mark.asyncio
async def test_exchange_refresh_token_expired_returns_none():
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "invalid_grant: refresh_token expired"

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await service._exchange_refresh_token("expired_refresh")

    assert result is None


@pytest.mark.asyncio
async def test_exchange_refresh_token_network_error_returns_none():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("Network error"))
        mock_client_cls.return_value = mock_client

        result = await service._exchange_refresh_token("qualquer_token")

    assert result is None
