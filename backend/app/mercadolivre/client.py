import asyncio
import time
from datetime import date

import httpx

from app.core.config import settings

ML_API_BASE = "https://api.mercadolibre.com"

# Rate limit: 1 req/seg
_last_request_time: float = 0.0
_RATE_LIMIT_DELAY = 1.0  # segundos


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
        """Aguarda para respeitar o rate limit de 1 req/seg."""
        global _last_request_time
        now = time.monotonic()
        elapsed = now - _last_request_time
        if elapsed < _RATE_LIMIT_DELAY:
            await asyncio.sleep(_RATE_LIMIT_DELAY - elapsed)
        _last_request_time = time.monotonic()

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
                    f"HTTP {e.response.status_code}: {e.response.text[:200]}",
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
        # Retorna dict com "visits" como chave
        return response.get("visits", [])

    async def get_item_orders(self, mlb_id: str, seller_id: str, days: int = 30) -> list[dict]:
        """
        Busca vendas/orders de um anúncio.
        GET /orders/search?seller={seller_id}&q={mlb_id}&sort=date_desc
        """
        item_id = mlb_id.upper().replace("-", "")
        if not item_id.startswith("MLB"):
            item_id = f"MLB{item_id}"

        response = await self._request(
            "GET",
            "/orders/search",
            params={
                "seller": seller_id,
                "q": item_id,
                "sort": "date_desc",
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

    async def get_item_promotions(self, mlb_id: str, seller_id: str) -> list[dict]:
        """
        Busca promoções de um anúncio.
        GET /seller-promotions/users/{seller_id}/items/{mlb_id}
        """
        item_id = mlb_id.upper().replace("-", "")
        if not item_id.startswith("MLB"):
            item_id = f"MLB{item_id}"

        try:
            response = await self._request(
                "GET",
                f"/seller-promotions/users/{seller_id}/items/{item_id}",
            )
            return response.get("results", []) if isinstance(response, dict) else []
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

    async def get_item_ads(self, mlb_id: str) -> dict:
        """
        Busca dados de publicidade (Ads) de um anúncio.
        GET /advertising/product_ads?item_id={mlb_id}&status=active
        Retorna: impressions, clicks, spend, attributed_sales, roas, cpc
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

    async def close(self):
        """Fecha o cliente HTTP."""
        await self._client.aclose()
