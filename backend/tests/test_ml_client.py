"""Testes unitários para o cliente ML (mercadolivre/client.py)."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-for-unit-tests!!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from app.mercadolivre.client import ML_API_BASE, MLClient, MLClientError


@pytest.fixture(autouse=True)
def mock_redis_rate_limit():
    """Mocka _distributed_rate_limit globalmente para todos os testes."""
    with patch("app.mercadolivre.client._distributed_rate_limit", new_callable=AsyncMock):
        yield


# ============================================================================
# Teste 1: Base URL correta
# ============================================================================


class TestBaseURL:
    """Garante que a URL base é api.mercadolibre.com (sem acento)."""

    def test_base_url_is_mercadolibre_not_mercadolivre(self):
        """ML_API_BASE deve ser api.mercadolibre.com (sem acento, sem /livre/)."""
        assert ML_API_BASE == "https://api.mercadolibre.com"
        assert "mercadolibre" in ML_API_BASE
        assert "mercadolivre" not in ML_API_BASE

    def test_client_uses_correct_base_url(self):
        """O cliente httpx deve ser inicializado com a URL correta."""
        client = MLClient("dummy_token")
        assert str(client._client.base_url) == "https://api.mercadolibre.com"


# ============================================================================
# Teste 2: get_item retorna dados do item
# ============================================================================


class TestGetItem:
    """Testa get_item — busca dados de um anúncio."""

    @pytest.mark.asyncio
    async def test_get_item_returns_item_data(self):
        """get_item deve retornar o dict com dados do anúncio."""
        client = MLClient("dummy_token")
        expected = {"id": "MLB123456789", "title": "Produto Teste", "price": 150.0}

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = expected
            mock_req.return_value = mock_response

            result = await client.get_item("MLB123456789")
            assert result["id"] == "MLB123456789"
            assert result["price"] == 150.0

    @pytest.mark.asyncio
    async def test_get_item_includes_attributes_param(self):
        """get_item deve incluir include_attributes=all para buscar SKU."""
        client = MLClient("dummy_token")

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": "MLB123"}
            mock_req.return_value = mock_response

            await client.get_item("MLB123")
            call_kwargs = mock_req.call_args[1]
            assert call_kwargs.get("params", {}).get("include_attributes") == "all"


# ============================================================================
# Teste 3: get_item_sale_price retorna preço correto
# ============================================================================


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

    @pytest.mark.asyncio
    async def test_get_item_sale_price_endpoint_path(self):
        """get_item_sale_price deve chamar /items/{id}/sale_price."""
        client = MLClient("dummy_token")

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"amount": 57.38}
            mock_req.return_value = mock_response

            await client.get_item_sale_price("MLB6205732214")
            url_called = mock_req.call_args[0][1]
            assert "/items/MLB6205732214/sale_price" in url_called


# ============================================================================
# Teste 4: get_user_listings retorna lista paginada
# ============================================================================


class TestGetUserListings:
    """Testa get_user_listings — lista paginada de anúncios."""

    @pytest.mark.asyncio
    async def test_get_user_listings_returns_dict(self):
        """get_user_listings deve retornar dict com results e paging."""
        client = MLClient("dummy_token")
        expected = {
            "results": ["MLB111", "MLB222", "MLB333"],
            "paging": {"total": 3, "offset": 0, "limit": 50},
        }

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = expected
            mock_req.return_value = mock_response

            result = await client.get_user_listings("2050442871")
            assert "results" in result
            assert len(result["results"]) == 3

    @pytest.mark.asyncio
    async def test_get_user_listings_passes_offset_and_limit(self):
        """get_user_listings deve passar offset e limit como params."""
        client = MLClient("dummy_token")

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"results": []}
            mock_req.return_value = mock_response

            await client.get_user_listings("2050442871", offset=50, limit=100)
            call_params = mock_req.call_args[1]["params"]
            assert call_params["offset"] == 50
            assert call_params["limit"] == 100
            assert call_params["status"] == "active"


# ============================================================================
# Teste 5: get_item_visits retorna visitas
# ============================================================================


class TestGetItemVisits:
    """Testa get_item_visits — visitas de um anúncio."""

    @pytest.mark.asyncio
    async def test_get_item_visits_returns_list(self):
        """get_item_visits deve retornar lista de visitas."""
        client = MLClient("dummy_token")
        api_response = {
            "results": [{"date": "2026-04-01", "total": 42}]
        }

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = api_response
            mock_req.return_value = mock_response

            result = await client.get_item_visits("MLB123456789", days=1)
            assert isinstance(result, list)
            assert result[0]["total"] == 42

    @pytest.mark.asyncio
    async def test_get_item_visits_uses_time_window_endpoint(self):
        """get_item_visits deve usar o endpoint /time_window (não histórico total)."""
        client = MLClient("dummy_token")

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"results": []}
            mock_req.return_value = mock_response

            await client.get_item_visits("MLB123456789", days=1)
            url_called = mock_req.call_args[0][1]
            assert "/visits/time_window" in url_called


# ============================================================================
# Teste 6: get_item_orders_by_status aceita date_from e date_to
# ============================================================================


class TestGetOrders:
    """Testa get_item_orders_by_status — bug corrigido: aceita date_from e date_to."""

    @pytest.mark.asyncio
    async def test_get_orders_sends_date_from_and_date_to(self):
        """get_item_orders_by_status deve incluir order.date_created.from e .to nos params."""
        client = MLClient("dummy_token")

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"results": []}
            mock_req.return_value = mock_response

            await client.get_item_orders_by_status("MLB123", "seller_999", days=1)
            call_params = mock_req.call_args[1]["params"]
            assert "order.date_created.from" in call_params
            assert "order.date_created.to" in call_params

    @pytest.mark.asyncio
    async def test_get_orders_with_status_filter(self):
        """Quando status='paid', deve incluir order.status=paid nos params."""
        client = MLClient("dummy_token")

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"results": []}
            mock_req.return_value = mock_response

            await client.get_item_orders_by_status("MLB123", "seller_999", days=1, status="paid")
            call_params = mock_req.call_args[1]["params"]
            assert call_params.get("order.status") == "paid"

    @pytest.mark.asyncio
    async def test_get_orders_returns_list(self):
        """get_item_orders_by_status deve retornar lista de pedidos."""
        client = MLClient("dummy_token")
        orders = [{"id": "123", "status": "paid"}, {"id": "456", "status": "paid"}]

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"results": orders}
            mock_req.return_value = mock_response

            result = await client.get_item_orders_by_status("MLB123", "seller_999", days=1)
            assert isinstance(result, list)
            assert len(result) == 2


# ============================================================================
# Teste 7: refresh_token — renovação de token
# ============================================================================


class TestTokenRefreshMethod:
    """Testa o refresh automático de token via _refresh_token_and_retry."""

    @pytest.mark.asyncio
    async def test_refresh_token_requires_ml_account_id(self):
        """Sem ml_account_id, _refresh_token_and_retry deve retornar False."""
        client = MLClient("dummy_token", ml_account_id=None)
        result = await client._refresh_token_and_retry()
        assert result is False

    @pytest.mark.asyncio
    async def test_refresh_token_updates_header_on_success(self):
        """Após refresh bem-sucedido, header Authorization deve ser atualizado."""
        client = MLClient("old_token", ml_account_id="account-abc")

        with patch(
            "app.auth.service.refresh_ml_token_by_id",
            new_callable=AsyncMock,
            return_value="new_token_xyz",
        ):
            result = await client._refresh_token_and_retry()
            assert result is True
            assert client.access_token == "new_token_xyz"
            assert "new_token_xyz" in client._client.headers["Authorization"]

    @pytest.mark.asyncio
    async def test_refresh_token_returns_false_on_service_error(self):
        """Quando o serviço de refresh lança exceção, deve retornar False."""
        client = MLClient("dummy_token", ml_account_id="account-abc")

        with patch(
            "app.auth.service.refresh_ml_token_by_id",
            new_callable=AsyncMock,
            side_effect=Exception("refresh service down"),
        ):
            result = await client._refresh_token_and_retry()
            assert result is False


# ============================================================================
# Teste 8: Rate limiting — distribuído via Redis
# ============================================================================


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

    @pytest.mark.asyncio
    async def test_distributed_rate_limit_is_called_before_request(self):
        """_distributed_rate_limit deve ser chamado antes de cada requisição."""
        client = MLClient("dummy_token")

        with patch("app.mercadolivre.client._distributed_rate_limit", new_callable=AsyncMock) as mock_rl:
            with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {}
                mock_req.return_value = mock_response

                await client._request("GET", "/test")
                mock_rl.assert_called_once()


# ============================================================================
# Teste 9: Retry com backoff em erro 5xx
# ============================================================================


class TestRetryLogic:
    """Testa retry com backoff exponencial em erros de servidor."""

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

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_raises_error(self):
        """Quando todas as tentativas falham com 500, deve levantar MLClientError."""
        client = MLClient("dummy_token")
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
            response_500 = MagicMock()
            response_500.status_code = 500
            mock_req.return_value = response_500

            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(MLClientError):
                    await client._request("GET", "/test", max_retries=2)


# ============================================================================
# Teste 10: Timeout handling
# ============================================================================


class TestTimeoutHandling:
    """Testa tratamento de timeout."""

    @pytest.mark.asyncio
    async def test_timeout_triggers_retry(self):
        """TimeoutException deve disparar retry com backoff."""
        import httpx

        client = MLClient("dummy_token")
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
            response_200 = MagicMock()
            response_200.status_code = 200
            response_200.json.return_value = {"ok": True}

            mock_req.side_effect = [httpx.TimeoutException("timeout"), response_200]

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client._request("GET", "/test", max_retries=2)
                assert result == {"ok": True}
                assert mock_req.call_count == 2

    @pytest.mark.asyncio
    async def test_all_timeouts_raises_ml_client_error(self):
        """Quando todos os timeouts ocorrem, deve levantar MLClientError."""
        import httpx

        client = MLClient("dummy_token")
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = httpx.TimeoutException("timeout")

            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(MLClientError) as exc_info:
                    await client._request("GET", "/test", max_retries=2)
                assert "Falha após" in str(exc_info.value)


# ============================================================================
# Teste 11: Token expirado retorna 401
# ============================================================================


class TestTokenRefresh:
    """Testa refresh automático de token em caso de 401."""

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

    @pytest.mark.asyncio
    async def test_401_without_account_raises_ml_client_error(self):
        """Sem ml_account_id, 401 deve levantar MLClientError com status_code=401."""
        client = MLClient("dummy_token", ml_account_id=None)

        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
            response_401 = MagicMock()
            response_401.status_code = 401
            mock_req.return_value = response_401

            with pytest.raises(MLClientError) as exc_info:
                await client._request("GET", "/test")
            assert exc_info.value.status_code == 401


# ============================================================================
# Teste 12: MLB ID normalização
# ============================================================================


class TestMLBNormalization:
    """Testa normalização de IDs MLB."""

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

    @pytest.mark.asyncio
    async def test_normalize_mlb_lowercase(self):
        """'mlb123' deve ser normalizado para 'MLB123'."""
        client = MLClient("dummy_token")
        with patch.object(client._client, "request", new_callable=AsyncMock) as mock_req:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": "MLB123"}
            mock_req.return_value = mock_response

            await client.get_item("mlb123")
            call_args = mock_req.call_args
            assert "/items/MLB123" in call_args[0][1]


# ============================================================================
# Teste 13: MLClientError
# ============================================================================


class TestMLClientError:
    """Testa a classe MLClientError."""

    def test_error_with_status_code(self):
        """MLClientError deve armazenar status_code."""
        error = MLClientError("Token invalido", status_code=401)
        assert str(error) == "Token invalido"
        assert error.status_code == 401

    def test_error_without_status_code(self):
        """MLClientError sem status_code deve ter None."""
        error = MLClientError("Erro genérico")
        assert error.status_code is None
