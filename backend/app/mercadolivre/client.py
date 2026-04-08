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


async def _distributed_rate_limit():
    """
    Rate limiter distribuído usando Redis.
    Cria conexão fresca por chamada para evitar loop-binding entre tasks Celery
    (cada task Celery cria event loop novo via run_async; um singleton de pool
    aioredis ficaria preso ao primeiro loop e quebraria com 'Event loop is closed').
    """
    import redis.asyncio as aioredis

    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        max_attempts = 10
        for _ in range(max_attempts):
            acquired = await redis.set(
                _RATE_LIMIT_KEY, "1", nx=True, px=int(_RATE_LIMIT_DELAY * 1000)
            )
            if acquired:
                return  # Slot adquirido — pode fazer a request

            ttl_ms = await redis.pttl(_RATE_LIMIT_KEY)
            if ttl_ms > 0:
                await asyncio.sleep(ttl_ms / 1000 + 0.05)
            else:
                await asyncio.sleep(0.1)
    finally:
        try:
            await redis.aclose()
        except Exception:
            pass


class MLClientError(Exception):
    """Erro genérico do cliente ML."""
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class MLClient:
    """
    Cliente HTTP para a API do Mercado Livre.
    Respeita rate limit de 1 req/seg e implementa retry com backoff exponencial.
    Suporta refresh automático de token OAuth quando 401 for retornado.
    """

    def __init__(self, access_token: str, ml_account_id: str | None = None):
        """
        Inicializa o cliente ML.

        Args:
            access_token: Token de acesso OAuth do Mercado Livre
            ml_account_id: ID da conta MLAccount no banco (usado para refresh automático)
        """
        self.access_token = access_token
        self.ml_account_id = ml_account_id
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

    async def _refresh_token_and_retry(self) -> bool:
        """
        Tenta renovar o token da conta ML e retorna sucesso.
        Retorna True se renovação foi bem-sucedida, False caso contrário.
        """
        if not self.ml_account_id:
            return False

        try:
            # Evita importação circular; importa quando necessário
            from app.auth.service import refresh_ml_token_by_id

            new_token = await refresh_ml_token_by_id(self.ml_account_id)
            if new_token:
                self.access_token = new_token
                # Atualiza header do cliente com novo token
                self._client.headers["Authorization"] = f"Bearer {new_token}"
                return True
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Falha ao renovar token para conta {self.ml_account_id}: {e}"
            )

        return False

    async def _request(
        self,
        method: str,
        url: str,
        max_retries: int = 3,
        **kwargs,
    ) -> dict:
        """
        Executa requisição com retry e backoff exponencial.
        Respeita rate limit de 1 req/seg (verificado a cada tentativa).
        Se receber 401, tenta renovar o token UMA única vez — se 401 persistir após
        o refresh, falha imediatamente para evitar loop infinito.
        """
        import logging
        logger = logging.getLogger(__name__)

        last_exception = None
        token_refreshed = False  # BUG 1: flag para evitar loop infinito no retry de 401
        for attempt in range(max_retries):
            try:
                await self._rate_limit()  # BUG 2: rate limit dentro do loop (cada tentativa respeita o limite)

                response = await self._client.request(method, url, **kwargs)

                if response.status_code == 429:
                    # Rate limit atingido — aguarda e tenta novamente
                    retry_after = int(response.headers.get("Retry-After", 5))
                    await asyncio.sleep(retry_after)
                    continue

                if response.status_code == 401:
                    # BUG 1: só tenta refresh uma única vez; segunda vez falha imediatamente
                    if not token_refreshed:
                        logger.info(
                            f"Token expirado para conta {self.ml_account_id}, tentando renovar..."
                        )
                        if await self._refresh_token_and_retry():
                            logger.info(
                                f"Token renovado para conta {self.ml_account_id}, repetindo requisição..."
                            )
                            token_refreshed = True
                            continue
                        # Refresh falhou — não adianta tentar novamente
                    raise MLClientError(
                        "Token ML expirado" if token_refreshed else "Token ML expirado e falha ao renovar",
                        status_code=401,
                    )

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

        return await self._request(
            "GET",
            f"/items/{item_id}",
            params={"include_attributes": "all"},
        )

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

    async def create_price_discount_promotion(
        self,
        seller_id: str,
        mlb_id: str,
        deal_price: float,
        start_date: str,
        finish_date: str,
        top_deal_price: float | None = None,
    ) -> dict:
        """
        Cria promoção de desconto individual (PRICE_DISCOUNT) para um item.

        POST /seller-promotions/items/{item_id}?user_id={seller_id}

        IMPORTANTE:
        - deal_price é o PREÇO FINAL em R$, NÃO percentual de desconto.
        - O item deve ter status "active".
        - Se já existe promoção PRICE_DISCOUNT ativa no item, este POST retorna erro.
          Chamar delete_price_discount_promotion() antes de criar nova.
        - start_date e finish_date devem ser ISO 8601 UTC (ex: "2026-04-02T00:00:00Z").

        Args:
            seller_id: ID do vendedor no ML (ex: "2050442871")
            mlb_id: ID do anúncio (ex: "MLB6205732214")
            deal_price: Preço com desconto em R$ para todos os compradores
            start_date: Início da promoção em ISO 8601 UTC
            finish_date: Fim da promoção em ISO 8601 UTC
            top_deal_price: Preço especial para Mercado Pontos nível 3-6 (opcional)
                           Deve ser pelo menos 5% menor que deal_price (desconto <= 35%)
                           Deve ser pelo menos 10% menor que deal_price (desconto > 35%)

        Validado com curl: PENDENTE — executar antes de ir para produção.
        Ref: docs/ml_api_reference.md seção 2.
        """
        item_id = mlb_id.upper().replace("-", "")
        if not item_id.startswith("MLB"):
            item_id = f"MLB{item_id}"

        payload: dict = {
            "promotion_type": "PRICE_DISCOUNT",
            "deal_price": deal_price,
            "start_date": start_date,
            "finish_date": finish_date,
        }
        if top_deal_price is not None:
            payload["top_deal_price"] = top_deal_price

        return await self._request(
            "POST",
            f"/seller-promotions/items/{item_id}",
            params={"user_id": seller_id},
            json=payload,
        )

    async def delete_price_discount_promotion(
        self,
        seller_id: str,
        mlb_id: str,
        promotion_type: str = "PRICE_DISCOUNT",
    ) -> dict:
        """
        Remove/finaliza uma promoção de um item.

        DELETE /seller-promotions/items/{item_id}?user_id={seller_id}&promotion_type={type}

        Necessário antes de:
        - Alterar preço via PUT /items/{id} quando há promoção ativa
        - Criar nova promoção PRICE_DISCOUNT (não é possível ter duas simultâneas)

        Para DOD e LIGHTNING: NÃO usar este método — estas promoções são do marketplace.

        Args:
            seller_id: ID do vendedor no ML
            mlb_id: ID do anúncio
            promotion_type: Tipo da promoção a remover (padrão: "PRICE_DISCOUNT")

        Validado com curl: PENDENTE — executar antes de ir para produção.
        Ref: docs/ml_api_reference.md seção 2.
        """
        item_id = mlb_id.upper().replace("-", "")
        if not item_id.startswith("MLB"):
            item_id = f"MLB{item_id}"

        return await self._request(
            "DELETE",
            f"/seller-promotions/items/{item_id}",
            params={"user_id": seller_id, "promotion_type": promotion_type},
        )

    # Mantido por compatibilidade — DEPRECADO: usar create_price_discount_promotion()
    async def create_promotion(
        self,
        seller_id: str,
        mlb_id: str,
        discount_pct: float,
        start_date: str,
        end_date: str,
    ) -> dict:
        """
        DEPRECADO — endpoint e body estavam incorretos.
        Use create_price_discount_promotion() que usa o endpoint correto:
          POST /seller-promotions/items/{item_id}?user_id={seller_id}
        com deal_price em R$ (não percentual).

        Este método é mantido apenas para não quebrar chamadores existentes.
        Ref: docs/ml_api_reference.md seção 9 (divergências conhecidas).
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            "create_promotion() está DEPRECADO. Use create_price_discount_promotion() "
            "com deal_price em R$ em vez de discount_pct."
        )
        # Não há como calcular deal_price sem saber o preço atual do item.
        # Lança erro explícito para forçar migração.
        raise NotImplementedError(
            "create_promotion() foi depreciado pois usava endpoint e formato incorretos. "
            "Use create_price_discount_promotion(seller_id, mlb_id, deal_price, start_date, finish_date)."
        )

    # Mantido por compatibilidade — DEPRECADO: PRICE_DISCOUNT não suporta PUT
    async def update_promotion(
        self,
        promotion_id: str,
        mlb_id: str,
        discount_pct: float,
        end_date: str,
    ) -> dict:
        """
        DEPRECADO — PRICE_DISCOUNT não suporta PUT (a API retornaria erro).
        Para atualizar uma promoção PRICE_DISCOUNT:
          1. delete_price_discount_promotion()
          2. create_price_discount_promotion() com novos valores

        PUT só existe para SELLER_CAMPAIGN via endpoint diferente.
        Ref: docs/ml_api_reference.md seção 9 (divergências conhecidas).
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            "update_promotion() está DEPRECADO. PRICE_DISCOUNT não suporta PUT. "
            "Use delete_price_discount_promotion() + create_price_discount_promotion()."
        )
        raise NotImplementedError(
            "update_promotion() foi depreciado. PRICE_DISCOUNT não suporta atualização via PUT. "
            "Deletar a promoção existente e criar nova com os novos valores."
        )

    async def get_advertiser_id(self) -> str | None:
        """
        Verifica se a conta tem acesso a Product Ads e retorna o advertiser_id.
        GET /advertising/advertisers?product_id=PADS
        Header obrigatório: Api-Version: 2
        Retorna None se account não tem acesso a Product Ads.
        """
        try:
            data = await self._request(
                "GET",
                "/advertising/advertisers",
                params={"product_id": "PADS"},
                headers={"Api-Version": "2"},
            )
            if isinstance(data, list) and len(data) > 0:
                return str(data[0].get("advertiser_id"))
            if isinstance(data, dict):
                # Formato: {"advertisers": [...]} ou {"advertiser_id": "..."}
                advertisers = data.get("advertisers", [])
                if advertisers:
                    return str(advertisers[0].get("advertiser_id"))
                return str(data.get("advertiser_id")) if data.get("advertiser_id") else None
            return None
        except MLClientError:
            return None

    async def get_product_ads_campaigns(self, advertiser_id: str, date_from: str, date_to: str) -> list:
        """
        Busca campanhas de Product Ads com métricas.
        GET /advertising/advertisers/{advertiser_id}/product_ads/campaigns
        Header obrigatório: Api-Version: 2
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
                headers={"Api-Version": "2"},
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
        Header obrigatório: Api-Version: 2
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
                headers={"Api-Version": "2"},
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
        date_to: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict:
        """
        Busca pedidos do vendedor por data de criacao.
        GET /orders/search?seller={seller_id}&order.date_created.from={date_from}&sort=date_desc

        Args:
            seller_id: ID do vendedor no ML
            date_from: Data de inicio no formato ISO (ex: "2026-03-10T00:00:00.000-03:00")
            date_to: Data de fim no formato ISO (opcional)
            offset: Offset para paginacao
            limit: Quantidade maxima de resultados (max 50)

        Returns:
            Dict com "results" (lista de pedidos) e "paging" (total, offset, limit)
        """
        params = {
            "seller": str(seller_id),
            "order.date_created.from": date_from,
            "sort": "date_desc",
            "offset": offset,
            "limit": limit,
        }
        if date_to:
            params["order.date_created.to"] = date_to
        return await self._request("GET", "/orders/search", params=params)

    async def get_shipment(self, shipment_id: int | str) -> dict:
        """
        Busca dados de um envio pelo ID.
        GET /shipments/{shipment_id}
        Retorna dados incluindo cost_components (sender_cost), base_cost, etc.
        """
        return await self._request("GET", f"/shipments/{shipment_id}")

    async def get_received_questions(
        self, status: str = "UNANSWERED", offset: int = 0, limit: int = 50
    ) -> dict:
        """
        Busca perguntas recebidas pelo vendedor.
        GET /my/received_questions/search?status={status}&offset={offset}&limit={limit}
        Retorna dict com "total", "limit", "questions" (lista de perguntas).
        """
        return await self._request(
            "GET",
            "/my/received_questions/search",
            params={
                "status": status,
                "offset": offset,
                "limit": limit,
                "sort_fields": "date_created",
                "sort_types": "DESC",
            },
        )

    async def answer_question(self, question_id: int, text: str) -> dict:
        """
        Responde uma pergunta do comprador.
        POST /answers
        Body: {"question_id": id, "text": "resposta"}
        Retorna o objeto da resposta criada com status e date_created.
        """
        return await self._request(
            "POST",
            "/answers",
            json={"question_id": question_id, "text": text},
        )

    async def search_items(self, query: str, offset: int = 0, limit: int = 50) -> dict:
        """
        Busca items no ML por palavra-chave.
        GET /sites/MLB/search?q={query}&offset={offset}&limit={limit}

        Endpoint público — não requer autenticação.
        Retorna: {"results": [...], "paging": {"total": N, "offset": N, "limit": N}}
        Cada item em results contém: {"id": "MLBXXXXXXXX", "title": ..., "price": ..., ...}
        """
        return await self._request(
            "GET",
            "/sites/MLB/search",
            params={"q": query, "offset": offset, "limit": limit},
        )

    # -----------------------------------------------------------------------
    # Claims (Reclamações)
    # -----------------------------------------------------------------------

    async def get_claims(
        self,
        seller_id: str,
        status: str = "open",
        offset: int = 0,
        limit: int = 50,
    ) -> dict:
        """
        Busca reclamações do vendedor.
        GET /v1/claims/search?status={status}&offset={offset}&limit={limit}
        O seller_id é derivado do token (autenticação implícita).
        """
        try:
            return await self._request(
                "GET",
                "/v1/claims/search",
                params={
                    "status": status,
                    "offset": offset,
                    "limit": limit,
                    "sort": "date_created:DESC",
                },
            )
        except MLClientError:
            return {"data": [], "paging": {"total": 0}}

    async def get_claim_detail(self, claim_id: int) -> dict:
        """
        Busca detalhes de uma reclamação.
        GET /v1/claims/{claim_id}
        """
        return await self._request("GET", f"/v1/claims/{claim_id}")

    async def send_claim_message(self, claim_id: int, message: str) -> dict:
        """
        Envia mensagem numa reclamação.
        POST /v1/claims/{claim_id}/messages
        """
        return await self._request(
            "POST",
            f"/v1/claims/{claim_id}/messages",
            json={"message": message},
        )

    # -----------------------------------------------------------------------
    # Messages (Mensagens pós-venda)
    # -----------------------------------------------------------------------

    async def get_messages(
        self,
        pack_id: str | None = None,
        order_id: str | None = None,
        seller_id: str | None = None,
    ) -> dict:
        """
        Busca mensagens de um pack ou order.
        GET /messages/packs/{pack_id}/sellers/{seller_id}
        GET /messages/orders/{order_id}
        """
        try:
            if pack_id and seller_id:
                return await self._request(
                    "GET",
                    f"/messages/packs/{pack_id}/sellers/{seller_id}",
                )
            elif order_id:
                return await self._request("GET", f"/messages/orders/{order_id}")
            return {"messages": []}
        except MLClientError:
            return {"messages": []}

    async def send_message(self, pack_id: str, text: str, seller_id: str) -> dict:
        """
        Envia mensagem num pack de conversa pós-venda.
        POST /messages/packs/{pack_id}/sellers/{seller_id}
        """
        return await self._request(
            "POST",
            f"/messages/packs/{pack_id}/sellers/{seller_id}",
            json={"from": {"user_id": seller_id}, "text": text},
        )

    async def get_message_packs(
        self,
        seller_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> dict:
        """
        Busca conversas (packs) de mensagens pós-venda do vendedor.
        GET /messages/search?seller_id={seller_id}&limit={limit}&offset={offset}
        """
        try:
            return await self._request(
                "GET",
                "/messages/search",
                params={
                    "seller_id": seller_id,
                    "offset": offset,
                    "limit": limit,
                },
            )
        except MLClientError:
            return {"data": [], "paging": {"total": 0}}

    # -----------------------------------------------------------------------
    # Returns (Devoluções)
    # -----------------------------------------------------------------------

    async def get_returns(
        self,
        seller_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> dict:
        """
        Busca devoluções — no ML são claims com claim_type=return.
        GET /v1/claims/search?claim_type=return
        """
        try:
            return await self._request(
                "GET",
                "/v1/claims/search",
                params={
                    "claim_type": "return",
                    "offset": offset,
                    "limit": limit,
                    "sort": "date_created:DESC",
                },
            )
        except MLClientError:
            return {"data": [], "paging": {"total": 0}}

    async def get_item_sale_price(self, mlb_id: str, context: str = "channel_marketplace") -> dict:
        """
        Busca o preço real de venda de um anúncio (novo endpoint da API ML).
        GET /items/{id}/sale_price?context={context}

        Este endpoint retorna o preço REAL que o comprador vê, considerando
        todas as camadas de desconto (vendedor, campanha ML, etc).

        Retorna:
            {
                "price_id": str,
                "amount": float,          # Preço que o comprador PAGA
                "regular_amount": float|None,  # Preço cheio (riscado) se em promoção
                "currency_id": "BRL",
                "metadata": {...}         # Detalhes da promoção (só para dono do item)
            }

        Se falhar (404 = item sem promoção especial), retorna dict vazio.
        """
        item_id = mlb_id.upper().replace("-", "")
        if not item_id.startswith("MLB"):
            item_id = f"MLB{item_id}"

        try:
            return await self._request(
                "GET",
                f"/items/{item_id}/sale_price",
                params={"context": context},
            )
        except MLClientError as e:
            if e.status_code in (404, 400):
                return {}
            raise

    async def get_item_prices(self, mlb_id: str) -> list[dict]:
        """
        Busca TODAS as camadas de preço de um anúncio.
        GET /items/{id}/prices

        Retorna lista com todos os tipos de preço vigentes:
        - type: "standard" (preço padrão)
        - type: "promotion" (preço promocional)

        Cada entrada tem:
            {
                "id": str,
                "type": "standard"|"promotion",
                "amount": float,
                "regular_amount": float|None,
                "currency_id": "BRL",
                "conditions": {...},
                "context_restrictions": {...},
                "metadata": {...}
            }
        """
        item_id = mlb_id.upper().replace("-", "")
        if not item_id.startswith("MLB"):
            item_id = f"MLB{item_id}"

        try:
            response = await self._request(
                "GET",
                f"/items/{item_id}/prices",
            )
            if isinstance(response, list):
                return response
            if isinstance(response, dict):
                return response.get("prices", response.get("results", []))
            return []
        except MLClientError as e:
            if e.status_code in (404, 400):
                return []
            raise

    async def close(self):
        """Fecha o cliente HTTP."""
        await self._client.aclose()
