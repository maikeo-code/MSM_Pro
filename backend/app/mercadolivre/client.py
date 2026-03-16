import asyncio
import time
from datetime import date

import httpx

from app.core.config import settings

ML_API_BASE = "https://api.mercadolibre.com"

# ---------------------------------------------------------------------------
# Distributed rate limiter via Redis SETNX
# Garante 1 req/seg GLOBAL (entre todos os workers Celery + API)
# ---------------------------------------------------------------------------
_RATE_LIMIT_KEY = "ml:rate_limit:last_request"
_RATE_LIMIT_DELAY = 1.0  # segundos


async def _get_redis():
    """Retorna conexão Redis (lazy singleton)."""
    import redis.asyncio as aioredis
    if not hasattr(_get_redis, "_pool"):
        _get_redis._pool = aioredis.from_url(
            settings.redis_url, decode_responses=True
        )
    return _get_redis._pool


async def _distributed_rate_limit():
    """
    Rate limiter distribuído usando Redis.
    Usa um key com TTL de 1s — se o SETNX falhar, espera o TTL restante.
    """
    redis = await _get_redis()
    max_attempts = 10
    for _ in range(max_attempts):
        # Tenta adquirir o slot: SET NX com TTL de 1 segundo
        acquired = await redis.set(
            _RATE_LIMIT_KEY, "1", nx=True, px=int(_RATE_LIMIT_DELAY * 1000)
        )
        if acquired:
            return  # Slot adquirido — pode fazer a request

        # Slot ocupado — espera o TTL restante + pequena margem
        ttl_ms = await redis.pttl(_RATE_LIMIT_KEY)
        if ttl_ms > 0:
            await asyncio.sleep(ttl_ms / 1000 + 0.05)
        else:
            await asyncio.sleep(0.1)


class MLClientError(Exception):
    """Erro genérico do cliente ML."""
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class MLClient:
    """
    Cliente HTTP para a API do Mercado Livre.
    Respeita rate limit de 1 req/seg e implementa retry com backoff exponencial.
    """

    def __init__(self, access_token: str):
        self.access_token = access_token
        self._client = httpx.AsyncClient(
            base_url=ML_API_BASE,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()

    async def _rate_limit(self):
        """Rate limit distribuído via Redis SETNX — seguro entre múltiplos workers."""
        await _distributed_rate_limit()

    async def _request(
        self,
        method: str,
        url: str,
        max_retries: int = 3,
        **kwargs,
    ) -> dict:
        """
        Executa requisição com retry e backoff exponencial.
        Respeita rate limit de 1 req/seg.
        """
        await self._rate_limit()

        last_exception = None
        for attempt in range(max_retries):
            try:
                response = await self._client.request(method, url, **kwargs)

                if response.status_code == 429:
                    # Rate limit atingido — aguarda e tenta novamente
                    retry_after = int(response.headers.get("Retry-After", 5))
                    await asyncio.sleep(retry_after)
                    continue

                if response.status_code == 401:
                    raise MLClientError("Token ML expirado ou inválido", status_code=401)

                if response.status_code >= 500:
                    # Erro do servidor — tenta novamente com backoff
                    backoff = 2 ** attempt
                    await asyncio.sleep(backoff)
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.TimeoutException as e:
                last_exception = e
                backoff = 2 ** attempt
                await asyncio.sleep(backoff)
            except MLClientError:
                raise
            except httpx.HTTPStatusError as e:
                raise MLClientError(
                    f"HTTP {e.response.status_code}: {e.response.text[:500]}",
                    status_code=e.response.status_code,
                )

        raise MLClientError(
            f"Falha após {max_retries} tentativas: {last_exception}",
        )

    async def get_item(self, mlb_id: str) -> dict:
        """
        Busca dados de um anúncio pelo ID MLB.
        GET /items/{id}
        Retorna: título, preço, estoque, status, seller_id, etc.
        """
        item_id = mlb_id.upper().replace("-", "")
        if not item_id.startswith("MLB"):
            item_id = f"MLB{item_id}"

        return await self._request("GET", f"/items/{item_id}")

    async def update_item_price(self, mlb_id: str, price: float) -> dict:
        """
        Altera o preço de um anúncio.
        PUT /items/{id}
        """
        item_id = mlb_id.upper().replace("-", "")
        if not item_id.startswith("MLB"):
            item_id = f"MLB{item_id}"

        return await self._request(
            "PUT",
            f"/items/{item_id}",
            json={"price": price},
        )

    async def get_item_visits(self, mlb_id: str, days: int = 30) -> list[dict]:
        """
        Busca visitas de um anúncio nos últimos N dias.
        GET /items/{id}/visits/time_window?last={days}&unit=day
        """
        item_id = mlb_id.upper().replace("-", "")
        if not item_id.startswith("MLB"):
            item_id = f"MLB{item_id}"

        response = await self._request(
            "GET",
            f"/items/{item_id}/visits/time_window",
            params={"last": days, "unit": "day"},
        )
        return response.get("results", [])

    async def get_item_orders_by_status(
        self, mlb_id: str, seller_id: str, days: int = 1, status: str | None = None
    ) -> list[dict]:
        """
        Busca pedidos de um anúncio com filtro opcional de status.

        Args:
            mlb_id: ID do anúncio MLB
            seller_id: ID do vendedor ML
            days: Número de dias para buscar (retroativos a partir de hoje)
            status: Status do pedido (ex: "paid", "cancelled"). None = todos os status.

        NOTA: o parâmetro "q" é uma busca textual — a API do ML não oferece filtro exato
        por item_id em /orders/search. A validação exata (garantir que o item no pedido
        realmente corresponde ao mlb_id desejado) é responsabilidade do código chamador,
        que deve comparar order_items[].item.id após normalizar ambos os lados
        (upper + remover hífens).
        """
        from datetime import date as date_type, timedelta as td

        item_id = mlb_id.upper().replace("-", "")
        if not item_id.startswith("MLB"):
            item_id = f"MLB{item_id}"

        date_from = date_type.today() - td(days=days - 1)
        date_from_str = f"{date_from.isoformat()}T00:00:00.000-03:00"
        date_to = date_type.today()
        date_to_str = f"{date_to.isoformat()}T23:59:59.000-03:00"

        params = {
            "seller": seller_id,
            "q": item_id,
            "order.date_created.from": date_from_str,
            "order.date_created.to": date_to_str,
            "sort": "date_desc",
            "limit": 50,
        }
        if status:
            params["order.status"] = status

        response = await self._request(
            "GET",
            "/orders/search",
            params=params,
        )
        return response.get("results", [])

    async def get_item_orders(self, mlb_id: str, seller_id: str, days: int = 1) -> list[dict]:
        """
        Busca vendas/orders de um anúncio filtrado por data.
        GET /orders/search?seller={seller_id}&q={mlb_id}&order.date_created.from={date}&sort=date_desc

        NOTA: o parâmetro "q" é uma busca textual — a API do ML não oferece filtro exato
        por item_id em /orders/search. A validação exata (garantir que o item no pedido
        realmente corresponde ao mlb_id desejado) é responsabilidade do código chamador,
        que deve comparar order_items[].item.id após normalizar ambos os lados
        (upper + remover hífens).
        """
        from datetime import date as date_type, timedelta as td

        item_id = mlb_id.upper().replace("-", "")
        if not item_id.startswith("MLB"):
            item_id = f"MLB{item_id}"

        date_from = date_type.today() - td(days=days - 1)
        date_from_str = f"{date_from.isoformat()}T00:00:00.000-03:00"
        # date_to = mesmo dia que date_from para busca diária (intervalo fechado)
        date_to = date_from
        date_to_str = f"{date_to.isoformat()}T23:59:59.000-03:00"

        response = await self._request(
            "GET",
            "/orders/search",
            params={
                "seller": seller_id,
                "q": item_id,  # busca textual; validação exata feita no caller
                "order.date_created.from": date_from_str,
                "order.date_created.to": date_to_str,
                "order.status": "paid",
                "sort": "date_desc",
                "limit": 50,
            },
        )
        return response.get("results", [])

    async def get_full_stock(self, mlb_id: str) -> dict:
        """
        Busca estoque Full de um anúncio.
        GET /user-products/{mlb_id}/stock/fulfillment
        """
        item_id = mlb_id.upper().replace("-", "")
        if not item_id.startswith("MLB"):
            item_id = f"MLB{item_id}"

        try:
            return await self._request(
                "GET",
                f"/user-products/{item_id}/stock/fulfillment",
            )
        except MLClientError:
            # Se falhar, retorna dict vazio ou padrão
            return {"available": 0, "in_transit": 0}

    async def get_item_promotions(self, mlb_id: str, seller_id: str = "") -> list[dict]:
        """
        Busca TODAS as promoções associadas a um anúncio.
        GET /seller-promotions/items/{ITEM_ID}?app_version=v2

        Retorna lista de promoções, cada uma com:
          - type: DEAL, PRICE_DISCOUNT, MARKETPLACE_CAMPAIGN, etc.
          - price: preço com desconto
          - original_price: preço sem desconto (riscado)
          - status: started, pending, finished
          - start_date, finish_date
        """
        item_id = mlb_id.upper().replace("-", "")
        if not item_id.startswith("MLB"):
            item_id = f"MLB{item_id}"

        try:
            response = await self._request(
                "GET",
                f"/seller-promotions/items/{item_id}",
                params={"app_version": "v2"},
            )
            # Resposta pode ser lista direta ou dict com "results"
            if isinstance(response, list):
                return response
            if isinstance(response, dict):
                return response.get("results", [response] if "type" in response else [])
            return []
        except MLClientError:
            return []

    async def create_promotion(
        self,
        seller_id: str,
        mlb_id: str,
        discount_pct: float,
        start_date: str,
        end_date: str,
    ) -> dict:
        """
        Cria nova promoção.
        POST /seller-promotions/users/{seller_id}
        """
        item_id = mlb_id.upper().replace("-", "")
        if not item_id.startswith("MLB"):
            item_id = f"MLB{item_id}"

        payload = {
            "items": [{"item_id": item_id}],
            "discount": {"type": "percentage", "value": discount_pct},
            "start_date": start_date,
            "end_date": end_date,
        }

        return await self._request(
            "POST",
            f"/seller-promotions/users/{seller_id}",
            json=payload,
        )

    async def update_promotion(
        self,
        promotion_id: str,
        mlb_id: str,
        discount_pct: float,
        end_date: str,
    ) -> dict:
        """
        Atualiza promoção existente.
        PUT /seller-promotions/{promotion_id}
        """
        item_id = mlb_id.upper().replace("-", "")
        if not item_id.startswith("MLB"):
            item_id = f"MLB{item_id}"

        payload = {
            "items": [{"item_id": item_id}],
            "discount": {"type": "percentage", "value": discount_pct},
            "end_date": end_date,
        }

        return await self._request(
            "PUT",
            f"/seller-promotions/{promotion_id}",
            json=payload,
        )

    async def get_advertiser_id(self) -> str | None:
        """
        Verifica se a conta tem acesso a Product Ads e retorna o advertiser_id.
        GET /advertising/advertisers?product_id=PADS
        Retorna None se account não tem acesso a Product Ads.
        """
        try:
            data = await self._request("GET", "/advertising/advertisers", params={"product_id": "PADS"})
            if isinstance(data, list) and len(data) > 0:
                return str(data[0].get("advertiser_id"))
            if isinstance(data, dict):
                return str(data.get("advertiser_id"))
            return None
        except MLClientError:
            return None

    async def get_product_ads_campaigns(self, advertiser_id: str, date_from: str, date_to: str) -> list:
        """
        Busca campanhas de Product Ads com métricas.
        GET /advertising/advertisers/{advertiser_id}/product_ads/campaigns
        Parâmetros: date_from, date_to, metrics, metrics_summary.
        Retorna lista de campanhas com métricas ou lista vazia se falhar.
        """
        try:
            data = await self._request(
                "GET",
                f"/advertising/advertisers/{advertiser_id}/product_ads/campaigns",
                params={
                    "date_from": date_from,
                    "date_to": date_to,
                    "metrics": "clicks,prints,cost,roas,acos,units_quantity,total_amount,cpc,ctr,cvr",
                    "metrics_summary": "true",
                    "limit": 50,
                },
            )
            if isinstance(data, dict):
                return data.get("results", [])
            if isinstance(data, list):
                return data
            return []
        except MLClientError:
            return []

    async def get_product_ads_items(self, advertiser_id: str, date_from: str, date_to: str, item_id: str = None) -> list:
        """
        Busca métricas de ads por item (anúncio).
        GET /advertising/advertisers/{advertiser_id}/product_ads/items
        Parâmetros: date_from, date_to, metrics, item_id (opcional).
        Retorna lista de items com métricas ou lista vazia se falhar.
        """
        try:
            params = {
                "date_from": date_from,
                "date_to": date_to,
                "metrics": "clicks,prints,cost,roas,acos,units_quantity,total_amount",
                "limit": 50,
            }
            if item_id:
                params["item_id"] = item_id
            data = await self._request(
                "GET",
                f"/advertising/advertisers/{advertiser_id}/product_ads/items",
                params=params,
            )
            if isinstance(data, dict):
                return data.get("results", [])
            if isinstance(data, list):
                return data
            return []
        except MLClientError:
            return []

    async def get_item_ads(self, mlb_id: str) -> dict:
        """
        Busca dados de publicidade (Ads) de um anúncio.
        GET /advertising/product_ads?item_id={mlb_id}&status=active
        Retorna: impressions, clicks, spend, attributed_sales, roas, cpc
        DEPRECATED: usar get_product_ads_items com advertiser_id em vez disso.
        """
        item_id = mlb_id.upper().replace("-", "")
        if not item_id.startswith("MLB"):
            item_id = f"MLB{item_id}"

        try:
            response = await self._request(
                "GET",
                "/advertising/product_ads",
                params={"item_id": item_id, "status": "active"},
            )
            return response if response else {}
        except MLClientError:
            # Se não conseguir dados de ads, retorna dict vazio
            return {}

    async def get_listing_fees(
        self, price: float, category_id: str, listing_type_id: str
    ) -> dict:
        """
        Busca taxa real do ML por categoria e tipo de anúncio.
        GET /sites/MLB/listing_prices?price={price}&category_id={cat}&listing_type_id={type}
        Retorna: {percentage_fee: float, fixed_fee: float, sale_fee_amount: float}

        Args:
            price: Preço do anúncio em R$
            category_id: ID da categoria do anúncio (ex: "MLB1000")
            listing_type_id: Tipo de anúncio (ex: "bronze", "silver", "gold")

        Returns:
            Dict com percentual_fee, fixed_fee e sale_fee_amount
        """
        try:
            params = {
                "price": price,
                "category_id": category_id,
                "listing_type_id": listing_type_id,
            }
            data = await self._request("GET", "/sites/MLB/listing_prices", params=params)

            # data pode ser uma lista — filtrar pelo listing_type_id correto
            if isinstance(data, list):
                for item in data:
                    if item.get("listing_type_id") == listing_type_id:
                        return {
                            "percentage_fee": item.get("sale_fee_details", {}).get("percentage_fee", 0),
                            "fixed_fee": item.get("sale_fee_details", {}).get("fixed_fee", 0),
                            "sale_fee_amount": item.get("sale_fee_amount", 0),
                        }
            elif isinstance(data, dict):
                return {
                    "percentage_fee": data.get("sale_fee_details", {}).get("percentage_fee", 0),
                    "fixed_fee": data.get("sale_fee_details", {}).get("fixed_fee", 0),
                    "sale_fee_amount": data.get("sale_fee_amount", 0),
                }

            return {"percentage_fee": 0, "fixed_fee": 0, "sale_fee_amount": 0}
        except MLClientError:
            # Se falhar, retorna dict vazio (fallback para taxa padrão)
            return {"percentage_fee": 0, "fixed_fee": 0, "sale_fee_amount": 0}

    async def get_seller_reputation(self, seller_id: str) -> dict:
        """
        Busca dados de reputacao do vendedor.
        GET /users/{seller_id}

        Retorna o objeto completo do usuario ML, que inclui:
          - seller_reputation.level_id
          - seller_reputation.power_seller_status
          - seller_reputation.transactions (total, completed, canceled)
          - seller_reputation.metrics (claims, delayed_handling_time, cancellations)

        O campo seller_reputation.metrics contém rates de 0.0 a 1.0
        (ex: 0.0007 = 0.07%).
        """
        return await self._request("GET", f"/users/{seller_id}")

    # Métodos auxiliares/legados mantidos para compatibilidade

    async def get_listing(self, mlb_id: str) -> dict:
        """Busca dados de um anúncio pelo ID MLB (alias de get_item)."""
        return await self.get_item(mlb_id)

    async def get_listing_visits(
        self,
        mlb_id: str,
        date_from: date,
        date_to: date,
    ) -> dict:
        """Busca visitas em um período (legado)."""
        item_id = mlb_id.upper().replace("-", "")
        if not item_id.startswith("MLB"):
            item_id = f"MLB{item_id}"

        return await self._request(
            "GET",
            "/visits/items",
            params={
                "ids": item_id,
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
            },
        )

    async def get_user_listings(self, ml_user_id: str, offset: int = 0, limit: int = 50) -> dict:
        """Busca anúncios ativos de um usuário ML."""
        return await self._request(
            "GET",
            f"/users/{ml_user_id}/items/search",
            params={
                "status": "active",
                "offset": offset,
                "limit": limit,
            },
        )

    async def get_item_questions(self, mlb_id: str) -> dict:
        """Busca perguntas de um anúncio."""
        item_id = mlb_id.upper().replace("-", "")
        if not item_id.startswith("MLB"):
            item_id = f"MLB{item_id}"

        return await self._request(
            "GET",
            "/questions/search",
            params={"item": item_id, "status": "unanswered"},
        )

    async def get_items_visits_bulk(
        self, item_ids: list[str], date_from: str, date_to: str
    ) -> dict:
        """
        Busca visitas de múltiplos itens.
        GET /visits/items?ids=MLB1,MLB2,...&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
        Retorna dict com item_id -> total_visits
        """
        result = {}

        # Process in chunks of 50
        for i in range(0, len(item_ids), 50):
            chunk = item_ids[i : i + 50]
            ids_str = ",".join(chunk)
            try:
                response = await self._request(
                    "GET",
                    "/visits/items",
                    params={
                        "ids": ids_str,
                        "date_from": date_from,
                        "date_to": date_to,
                    },
                )
                # Response é uma lista de dicts com "item_id" e "total_visits"
                if isinstance(response, list):
                    for entry in response:
                        result[entry.get("item_id", "")] = entry.get("total_visits", 0)
                elif isinstance(response, dict):
                    # Às vezes retorna um dict direto
                    for item_id_key, visits_val in response.items():
                        result[item_id_key] = (
                            visits_val if isinstance(visits_val, int) else 0
                        )
            except MLClientError:
                # Falha silenciosa — continua com próximo chunk
                pass

        return result

    async def get_campaigns(self, seller_id: str) -> list[dict]:
        """
        Busca campanhas de publicidade de um vendedor.
        GET /advertising/campaigns?user_id={seller_id}
        Retorna lista de campanhas com id, name, status, daily_budget.
        Se falhar (403/404), retorna lista vazia — chamador deve tratar.
        """
        try:
            response = await self._request(
                "GET",
                "/advertising/campaigns",
                params={"user_id": seller_id},
            )
            if isinstance(response, list):
                return response
            if isinstance(response, dict):
                return response.get("results", [])
            return []
        except MLClientError as e:
            if e.status_code in (403, 404):
                return []
            raise

    async def get_campaign_metrics(
        self, campaign_id: str, date_from: str, date_to: str
    ) -> list[dict]:
        """
        Busca métricas diárias de uma campanha.
        GET /advertising/campaigns/{campaign_id}/metrics?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
        Retorna lista de dicts com: date, impressions, clicks, spend,
        attributed_sales, attributed_revenue, organic_sales.
        Se falhar (403/404), retorna lista vazia.
        """
        try:
            response = await self._request(
                "GET",
                f"/advertising/campaigns/{campaign_id}/metrics",
                params={"date_from": date_from, "date_to": date_to},
            )
            if isinstance(response, list):
                return response
            if isinstance(response, dict):
                return response.get("results", [])
            return []
        except MLClientError as e:
            if e.status_code in (403, 404):
                return []
            raise

    async def get_orders(
        self,
        seller_id: int | str,
        date_from: str,
        offset: int = 0,
        limit: int = 50,
    ) -> dict:
        """
        Busca pedidos do vendedor por data de criacao.
        GET /orders/search?seller={seller_id}&order.date_created.from={date_from}&sort=date_desc

        Args:
            seller_id: ID do vendedor no ML
            date_from: Data de inicio no formato ISO (ex: "2026-03-10T00:00:00.000-03:00")
            offset: Offset para paginacao
            limit: Quantidade maxima de resultados (max 50)

        Returns:
            Dict com "results" (lista de pedidos) e "paging" (total, offset, limit)
        """
        return await self._request(
            "GET",
            "/orders/search",
            params={
                "seller": str(seller_id),
                "order.date_created.from": date_from,
                "sort": "date_desc",
                "offset": offset,
                "limit": limit,
            },
        )

    async def close(self):
        """Fecha o cliente HTTP."""
        await self._client.aclose()
