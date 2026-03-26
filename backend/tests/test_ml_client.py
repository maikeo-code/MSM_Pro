"""Testes unitários para o cliente ML (mercadolivre/client.py)."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-for-unit-tests!!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from app.mercadolivre.client import MLClient, MLClientError


@pytest.fixture(autouse=True)
def mock_redis_rate_limit():
    """Mocka _distributed_rate_limit globalmente."""
    with patch("app.mercadolivre.client._distributed_rate_limit", new_callable=AsyncMock):
        yield


class TestMLClientError:
    """Testa a classe MLClientError."""

    def test_error_with_status_code(self):
        """MLClientError deve armazenar status_code."""
        error = MLClientError("Token invalido", status_code=401)
        assert str(error) == "Token invalido"
        assert error.status_code == 401


class TestMLBNormalization:
    """Testa normalizacao de IDs MLB."""

    @pytest.mark.asyncio
    async def test_normalize_mlb_with_hyphen(self):
        """'MLB-123456789' -> 'MLB123456789'"""
        client = MLClient("dummy_token")
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": "MLB123456789"}
            mock_req.return_value = mock_response

            await client.get_item("MLB-123456789")
            call_args = mock_req.call_args
            assert "/items/MLB123456789" in call_args[0][1]


class TestSalePriceParsing:
    """Testa parsing de sale_price."""

    @pytest.mark.asyncio
    async def test_get_item_sale_price_with_amount(self):
        """get_item_sale_price retorna dict com amount."""
        client = MLClient("dummy_token")
        expected = {
            "price_id": "price-123",
            "amount": 150.50,
            "regular_amount": 200.00,
            "currency_id": "BRL",
        }
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = expected
            mock_req.return_value = mock_response

            result = await client.get_item_sale_price("MLB6205732214")
            assert result == expected
            assert result["amount"] == 150.50


class TestRateLimitHandling:
    """Testa rate limit (429) handling."""

    @pytest.mark.asyncio
    async def test_429_retry_after(self):
        """Status 429 com Retry-After header deve aguardar e tentar novamente."""
        client = MLClient("dummy_token")
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
            response_429 = MagicMock()
            response_429.status_code = 429
            response_429.headers.get.return_value = "2"

            response_200 = MagicMock()
            response_200.status_code = 200
            response_200.json.return_value = {"id": "MLB123"}

            mock_req.side_effect = [response_429, response_200]

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client._request("GET", "/items/MLB123")
                assert result == {"id": "MLB123"}
                assert mock_req.call_count == 2


class TestRetryLogic:
    """Testa retry com backoff exponencial."""

    @pytest.mark.asyncio
    async def test_500_retry_with_backoff(self):
        """Status 500+ deve tentar novamente com backoff."""
        client = MLClient("dummy_token")
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
            response_500 = MagicMock()
            response_500.status_code = 500

            response_200 = MagicMock()
            response_200.status_code = 200
            response_200.json.return_value = {"success": True}

            mock_req.side_effect = [response_500, response_500, response_200]

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                result = await client._request("GET", "/test", max_retries=3)
                assert result == {"success": True}
                assert mock_req.call_count == 3
                assert mock_sleep.call_count == 2


class TestTokenRefresh:
    """Testa refresh automatico de token em caso de 401."""

    @pytest.mark.asyncio
    async def test_401_triggers_token_refresh(self):
        """Status 401 deve tentar renovar o token."""
        client = MLClient("dummy_token", ml_account_id="account-123")

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
            response_401 = MagicMock()
            response_401.status_code = 401

            response_200 = MagicMock()
            response_200.status_code = 200
            response_200.json.return_value = {"result": "ok"}

            mock_req.side_effect = [response_401, response_200]

            with patch.object(
                client,
                "_refresh_token_and_retry",
                new_callable=AsyncMock,
                return_value=True,
            ):
                result = await client._request("GET", "/test")
                assert result == {"result": "ok"}
                assert mock_req.call_count == 2
