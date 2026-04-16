"""
Testes para métodos não cobertos de mercadolivre/client.py

Ciclo 15 do auto-learning — cobertura alvo:
- mercadolivre/client.py: 32.77% → 65%+

Estratégia: para cada método, mockar client._request com AsyncMock
e verificar que o método chama a URL correta e processa a resposta.
"""
import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


# ─── Helper ──────────────────────────────────────────────────────────────────


def _client(token="fake-token"):
    from app.mercadolivre.client import MLClient
    with patch("app.mercadolivre.client._distributed_rate_limit", new_callable=AsyncMock):
        return MLClient(access_token=token)


# ═══════════════════════════════════════════════════════════════════════════════
# get_item_orders
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetItemOrders:

    @pytest.mark.asyncio
    async def test_retorna_results(self):
        client = _client()
        client._request = AsyncMock(return_value={"results": [{"id": "ORD1"}]})
        result = await client.get_item_orders("MLB123", "SELLER99", days=1)
        assert result == [{"id": "ORD1"}]

    @pytest.mark.asyncio
    async def test_sem_results_retorna_vazio(self):
        client = _client()
        client._request = AsyncMock(return_value={})
        result = await client.get_item_orders("MLB123", "SELLER99")
        assert result == []

    @pytest.mark.asyncio
    async def test_normaliza_mlb_id(self):
        client = _client()
        client._request = AsyncMock(return_value={"results": []})
        await client.get_item_orders("mlb-123", "SELLER99")
        url = client._request.call_args[0][1]
        assert url == "/orders/search"

    @pytest.mark.asyncio
    async def test_sem_prefixo_adiciona_mlb(self):
        client = _client()
        client._request = AsyncMock(return_value={"results": []})
        await client.get_item_orders("456789", "SEL1")
        params = client._request.call_args[1]["params"]
        assert params["q"].startswith("MLB")


# ═══════════════════════════════════════════════════════════════════════════════
# get_full_stock
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetFullStock:

    @pytest.mark.asyncio
    async def test_retorna_dados_stock(self):
        client = _client()
        client._request = AsyncMock(return_value={"available": 10, "in_transit": 2})
        result = await client.get_full_stock("MLB123456789")
        assert result["available"] == 10

    @pytest.mark.asyncio
    async def test_mlclienterror_retorna_padrao(self):
        from app.mercadolivre.client import MLClientError
        client = _client()
        client._request = AsyncMock(side_effect=MLClientError("not found", 404))
        result = await client.get_full_stock("MLB123456789")
        assert result == {"available": 0, "in_transit": 0}

    @pytest.mark.asyncio
    async def test_url_correta(self):
        client = _client()
        client._request = AsyncMock(return_value={"available": 5})
        await client.get_full_stock("MLB999888777")
        url = client._request.call_args[0][1]
        assert "MLB999888777" in url
        assert "fulfillment" in url


# ═══════════════════════════════════════════════════════════════════════════════
# get_item_promotions
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetItemPromotions:

    @pytest.mark.asyncio
    async def test_resposta_lista(self):
        client = _client()
        client._request = AsyncMock(return_value=[{"type": "PRICE_DISCOUNT"}])
        result = await client.get_item_promotions("MLB123")
        assert result == [{"type": "PRICE_DISCOUNT"}]

    @pytest.mark.asyncio
    async def test_resposta_dict_com_results(self):
        client = _client()
        client._request = AsyncMock(return_value={"results": [{"type": "DEAL"}]})
        result = await client.get_item_promotions("MLB123")
        assert result == [{"type": "DEAL"}]

    @pytest.mark.asyncio
    async def test_resposta_dict_com_type(self):
        """dict com 'type' direto → wraps em lista."""
        client = _client()
        client._request = AsyncMock(return_value={"type": "DEAL", "price": 99.0})
        result = await client.get_item_promotions("MLB123")
        assert isinstance(result, list)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_mlclienterror_retorna_vazio(self):
        from app.mercadolivre.client import MLClientError
        client = _client()
        client._request = AsyncMock(side_effect=MLClientError("error"))
        result = await client.get_item_promotions("MLB123")
        assert result == []

    @pytest.mark.asyncio
    async def test_resposta_invalida_retorna_vazio(self):
        client = _client()
        client._request = AsyncMock(return_value="string-invalida")
        result = await client.get_item_promotions("MLB123")
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# get_advertiser_id
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetAdvertiserId:

    @pytest.mark.asyncio
    async def test_lista_com_advertiser(self):
        client = _client()
        client._request = AsyncMock(return_value=[{"advertiser_id": "ADV123"}])
        result = await client.get_advertiser_id()
        assert result == "ADV123"

    @pytest.mark.asyncio
    async def test_dict_com_advertisers(self):
        client = _client()
        client._request = AsyncMock(return_value={"advertisers": [{"advertiser_id": "ADV456"}]})
        result = await client.get_advertiser_id()
        assert result == "ADV456"

    @pytest.mark.asyncio
    async def test_dict_direto_advertiser_id(self):
        client = _client()
        client._request = AsyncMock(return_value={"advertiser_id": "ADV789"})
        result = await client.get_advertiser_id()
        assert result == "ADV789"

    @pytest.mark.asyncio
    async def test_mlclienterror_retorna_none(self):
        from app.mercadolivre.client import MLClientError
        client = _client()
        client._request = AsyncMock(side_effect=MLClientError("no ads"))
        result = await client.get_advertiser_id()
        assert result is None

    @pytest.mark.asyncio
    async def test_lista_vazia_retorna_none(self):
        client = _client()
        client._request = AsyncMock(return_value=[])
        result = await client.get_advertiser_id()
        assert result is None

    @pytest.mark.asyncio
    async def test_dict_sem_advertiser_retorna_none(self):
        client = _client()
        client._request = AsyncMock(return_value={"advertisers": []})
        result = await client.get_advertiser_id()
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# get_product_ads_campaigns
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetProductAdsCampaigns:

    @pytest.mark.asyncio
    async def test_retorna_results_de_dict(self):
        client = _client()
        client._request = AsyncMock(return_value={"results": [{"campaign_id": "C1"}]})
        result = await client.get_product_ads_campaigns("ADV1", "2026-04-01", "2026-04-15")
        assert result == [{"campaign_id": "C1"}]

    @pytest.mark.asyncio
    async def test_resposta_lista(self):
        client = _client()
        client._request = AsyncMock(return_value=[{"campaign_id": "C2"}])
        result = await client.get_product_ads_campaigns("ADV1", "2026-04-01", "2026-04-15")
        assert result == [{"campaign_id": "C2"}]

    @pytest.mark.asyncio
    async def test_mlclienterror_retorna_vazio(self):
        from app.mercadolivre.client import MLClientError
        client = _client()
        client._request = AsyncMock(side_effect=MLClientError("ads error"))
        result = await client.get_product_ads_campaigns("ADV1", "2026-04-01", "2026-04-15")
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# get_product_ads_items
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetProductAdsItems:

    @pytest.mark.asyncio
    async def test_retorna_items(self):
        client = _client()
        client._request = AsyncMock(return_value={"results": [{"item_id": "MLB1"}]})
        result = await client.get_product_ads_items("ADV1", "2026-04-01", "2026-04-15")
        assert result == [{"item_id": "MLB1"}]

    @pytest.mark.asyncio
    async def test_com_item_id_filtro(self):
        client = _client()
        client._request = AsyncMock(return_value={"results": []})
        await client.get_product_ads_items("ADV1", "2026-04-01", "2026-04-15", item_id="MLB123")
        params = client._request.call_args[1]["params"]
        assert params["item_id"] == "MLB123"

    @pytest.mark.asyncio
    async def test_sem_item_id_sem_param(self):
        client = _client()
        client._request = AsyncMock(return_value={"results": []})
        await client.get_product_ads_items("ADV1", "2026-04-01", "2026-04-15")
        params = client._request.call_args[1]["params"]
        assert "item_id" not in params

    @pytest.mark.asyncio
    async def test_mlclienterror_retorna_vazio(self):
        from app.mercadolivre.client import MLClientError
        client = _client()
        client._request = AsyncMock(side_effect=MLClientError("error"))
        result = await client.get_product_ads_items("ADV1", "2026-04-01", "2026-04-15")
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# get_item_ads
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetItemAds:

    @pytest.mark.asyncio
    async def test_retorna_dados(self):
        client = _client()
        client._request = AsyncMock(return_value={"clicks": 100, "roas": 3.5})
        result = await client.get_item_ads("MLB123456789")
        assert result["clicks"] == 100

    @pytest.mark.asyncio
    async def test_mlclienterror_retorna_vazio(self):
        from app.mercadolivre.client import MLClientError
        client = _client()
        client._request = AsyncMock(side_effect=MLClientError("ads error"))
        result = await client.get_item_ads("MLB123456789")
        assert result == {}

    @pytest.mark.asyncio
    async def test_none_retorna_vazio(self):
        client = _client()
        client._request = AsyncMock(return_value=None)
        result = await client.get_item_ads("MLB123456789")
        assert result == {}


# ═══════════════════════════════════════════════════════════════════════════════
# get_received_questions
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetReceivedQuestions:

    @pytest.mark.asyncio
    async def test_retorna_dados(self):
        client = _client()
        payload = {"total": 2, "questions": [{"id": 1}, {"id": 2}]}
        client._request = AsyncMock(return_value=payload)
        result = await client.get_received_questions()
        assert result["total"] == 2

    @pytest.mark.asyncio
    async def test_url_correta(self):
        client = _client()
        client._request = AsyncMock(return_value={})
        await client.get_received_questions(status="ANSWERED", limit=10)
        url = client._request.call_args[0][1]
        assert "received_questions" in url

    @pytest.mark.asyncio
    async def test_params_incluem_status(self):
        client = _client()
        client._request = AsyncMock(return_value={})
        await client.get_received_questions(status="UNANSWERED")
        params = client._request.call_args[1]["params"]
        assert params["status"] == "UNANSWERED"


# ═══════════════════════════════════════════════════════════════════════════════
# answer_question
# ═══════════════════════════════════════════════════════════════════════════════


class TestAnswerQuestion:

    @pytest.mark.asyncio
    async def test_responde_pergunta(self):
        client = _client()
        client._request = AsyncMock(return_value={"status": "created"})
        result = await client.answer_question(12345, "Sim, tem garantia de 1 ano!")
        assert result == {"status": "created"}

    @pytest.mark.asyncio
    async def test_url_e_body_corretos(self):
        client = _client()
        client._request = AsyncMock(return_value={})
        await client.answer_question(99, "Resposta")
        call = client._request.call_args
        assert call[0][1] == "/answers"
        assert call[1]["json"]["question_id"] == 99
        assert call[1]["json"]["text"] == "Resposta"


# ═══════════════════════════════════════════════════════════════════════════════
# search_items
# ═══════════════════════════════════════════════════════════════════════════════


class TestSearchItems:

    @pytest.mark.asyncio
    async def test_retorna_resultados(self):
        client = _client()
        payload = {"results": [{"id": "MLB1"}, {"id": "MLB2"}], "paging": {"total": 2}}
        client._request = AsyncMock(return_value=payload)
        result = await client.search_items("notebook samsung")
        assert len(result["results"]) == 2

    @pytest.mark.asyncio
    async def test_url_sites_mlb(self):
        client = _client()
        client._request = AsyncMock(return_value={})
        await client.search_items("iphone")
        url = client._request.call_args[0][1]
        assert "/sites/MLB/search" in url

    @pytest.mark.asyncio
    async def test_params_query(self):
        client = _client()
        client._request = AsyncMock(return_value={})
        await client.search_items("cadeira ergonomica", offset=50, limit=25)
        params = client._request.call_args[1]["params"]
        assert params["q"] == "cadeira ergonomica"
        assert params["offset"] == 50
        assert params["limit"] == 25


# ═══════════════════════════════════════════════════════════════════════════════
# get_claims
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetClaims:

    @pytest.mark.asyncio
    async def test_retorna_dados(self):
        client = _client()
        client._request = AsyncMock(return_value={"data": [{"id": 1}], "paging": {"total": 1}})
        result = await client.get_claims("SEL1")
        assert "data" in result

    @pytest.mark.asyncio
    async def test_mlclienterror_retorna_padrao(self):
        from app.mercadolivre.client import MLClientError
        client = _client()
        client._request = AsyncMock(side_effect=MLClientError("error"))
        result = await client.get_claims("SEL1")
        assert result == {"data": [], "paging": {"total": 0}}

    @pytest.mark.asyncio
    async def test_url_v1_claims(self):
        client = _client()
        client._request = AsyncMock(return_value={})
        await client.get_claims("SEL1", status="closed")
        url = client._request.call_args[0][1]
        assert "/v1/claims/search" in url


# ═══════════════════════════════════════════════════════════════════════════════
# get_claim_detail
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetClaimDetail:

    @pytest.mark.asyncio
    async def test_retorna_detalhe(self):
        client = _client()
        client._request = AsyncMock(return_value={"id": 9999, "status": "open"})
        result = await client.get_claim_detail(9999)
        assert result["id"] == 9999

    @pytest.mark.asyncio
    async def test_url_com_id(self):
        client = _client()
        client._request = AsyncMock(return_value={})
        await client.get_claim_detail(12345)
        url = client._request.call_args[0][1]
        assert "/v1/claims/12345" in url


# ═══════════════════════════════════════════════════════════════════════════════
# send_claim_message
# ═══════════════════════════════════════════════════════════════════════════════


class TestSendClaimMessage:

    @pytest.mark.asyncio
    async def test_envia_mensagem(self):
        client = _client()
        client._request = AsyncMock(return_value={"status": "sent"})
        result = await client.send_claim_message(9999, "Olá, estamos resolvendo!")
        assert result == {"status": "sent"}

    @pytest.mark.asyncio
    async def test_url_e_body(self):
        client = _client()
        client._request = AsyncMock(return_value={})
        await client.send_claim_message(888, "Mensagem teste")
        call = client._request.call_args
        assert "/v1/claims/888/messages" in call[0][1]
        assert call[1]["json"]["message"] == "Mensagem teste"


# ═══════════════════════════════════════════════════════════════════════════════
# get_messages
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetMessages:

    @pytest.mark.asyncio
    async def test_com_pack_id_e_seller_id(self):
        client = _client()
        client._request = AsyncMock(return_value={"messages": [{"text": "oi"}]})
        result = await client.get_messages(pack_id="PACK1", seller_id="SEL1")
        url = client._request.call_args[0][1]
        assert "PACK1" in url
        assert "SEL1" in url

    @pytest.mark.asyncio
    async def test_com_order_id(self):
        client = _client()
        client._request = AsyncMock(return_value={"messages": []})
        await client.get_messages(order_id="ORD999")
        url = client._request.call_args[0][1]
        assert "ORD999" in url

    @pytest.mark.asyncio
    async def test_sem_parametros_retorna_vazio(self):
        client = _client()
        result = await client.get_messages()
        assert result == {"messages": []}

    @pytest.mark.asyncio
    async def test_mlclienterror_retorna_vazio(self):
        from app.mercadolivre.client import MLClientError
        client = _client()
        client._request = AsyncMock(side_effect=MLClientError("error"))
        result = await client.get_messages(pack_id="P1", seller_id="S1")
        assert result == {"messages": []}


# ═══════════════════════════════════════════════════════════════════════════════
# send_message
# ═══════════════════════════════════════════════════════════════════════════════


class TestSendMessage:

    @pytest.mark.asyncio
    async def test_envia_mensagem(self):
        client = _client()
        client._request = AsyncMock(return_value={"id": "MSG1"})
        result = await client.send_message("PACK99", "Olá tudo bem?", "SEL1")
        assert result["id"] == "MSG1"

    @pytest.mark.asyncio
    async def test_url_e_body(self):
        client = _client()
        client._request = AsyncMock(return_value={})
        await client.send_message("PACK99", "texto", "SEL123")
        call = client._request.call_args
        assert "PACK99" in call[0][1]
        assert "SEL123" in call[0][1]
        assert call[1]["json"]["text"] == "texto"


# ═══════════════════════════════════════════════════════════════════════════════
# get_message_packs
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetMessagePacks:

    @pytest.mark.asyncio
    async def test_retorna_dados(self):
        client = _client()
        client._request = AsyncMock(return_value={"data": [{"pack_id": "P1"}], "paging": {"total": 1}})
        result = await client.get_message_packs("SEL1")
        assert "data" in result

    @pytest.mark.asyncio
    async def test_mlclienterror_retorna_padrao(self):
        from app.mercadolivre.client import MLClientError
        client = _client()
        client._request = AsyncMock(side_effect=MLClientError("error"))
        result = await client.get_message_packs("SEL1")
        assert result == {"data": [], "paging": {"total": 0}}

    @pytest.mark.asyncio
    async def test_url_messages_search(self):
        client = _client()
        client._request = AsyncMock(return_value={})
        await client.get_message_packs("SEL99", offset=10)
        url = client._request.call_args[0][1]
        assert "/messages/search" in url


# ═══════════════════════════════════════════════════════════════════════════════
# get_returns
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetReturns:

    @pytest.mark.asyncio
    async def test_retorna_dados(self):
        client = _client()
        client._request = AsyncMock(return_value={"data": [], "paging": {"total": 0}})
        result = await client.get_returns("SEL1")
        assert "data" in result

    @pytest.mark.asyncio
    async def test_mlclienterror_retorna_padrao(self):
        from app.mercadolivre.client import MLClientError
        client = _client()
        client._request = AsyncMock(side_effect=MLClientError("error"))
        result = await client.get_returns("SEL1")
        assert result == {"data": [], "paging": {"total": 0}}


# ═══════════════════════════════════════════════════════════════════════════════
# get_shipment
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetShipment:

    @pytest.mark.asyncio
    async def test_retorna_dados_envio(self):
        client = _client()
        client._request = AsyncMock(return_value={"id": 12345, "status": "delivered"})
        result = await client.get_shipment(12345)
        assert result["status"] == "delivered"

    @pytest.mark.asyncio
    async def test_url_com_shipment_id(self):
        client = _client()
        client._request = AsyncMock(return_value={})
        await client.get_shipment(99999)
        url = client._request.call_args[0][1]
        assert "/shipments/99999" in url


# ═══════════════════════════════════════════════════════════════════════════════
# get_listing
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetListing:

    @pytest.mark.asyncio
    async def test_retorna_listing(self):
        client = _client()
        client._request = AsyncMock(return_value={"id": "MLB123", "title": "Produto"})
        result = await client.get_listing("MLB123")
        assert result["id"] == "MLB123"

    @pytest.mark.asyncio
    async def test_url_items(self):
        client = _client()
        client._request = AsyncMock(return_value={})
        await client.get_listing("MLB999")
        url = client._request.call_args[0][1]
        assert "/items/MLB999" in url


# ═══════════════════════════════════════════════════════════════════════════════
# get_listing_visits
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetListingVisits:

    @pytest.mark.asyncio
    async def test_retorna_visitas(self):
        from datetime import date
        client = _client()
        client._request = AsyncMock(return_value={"results": [{"date": "2026-04-15", "total": 55}]})
        result = await client.get_listing_visits("MLB123", date(2026, 4, 1), date(2026, 4, 15))
        assert isinstance(result, (list, dict))

    @pytest.mark.asyncio
    async def test_url_visits(self):
        from datetime import date
        client = _client()
        client._request = AsyncMock(return_value={"results": []})
        await client.get_listing_visits("MLB123", date(2026, 4, 1), date(2026, 4, 15))
        url = client._request.call_args[0][1]
        assert "visits" in url or "MLB123" in url


# ═══════════════════════════════════════════════════════════════════════════════
# get_item_prices
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetItemPrices:

    @pytest.mark.asyncio
    async def test_retorna_lista(self):
        client = _client()
        client._request = AsyncMock(return_value=[{"price": 99.0, "type": "standard"}])
        result = await client.get_item_prices("MLB123")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_url_prices(self):
        client = _client()
        client._request = AsyncMock(return_value=[])
        await client.get_item_prices("MLB456")
        url = client._request.call_args[0][1]
        assert "MLB456" in url
