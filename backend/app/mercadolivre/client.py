import asyncio
import time
from datetime import date

import httpx

from app.core.config import settings

ML_API_BASE = "https://api.mercadolivre.com"

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

    async def get_listing(self, mlb_id: str) -> dict:
        """
        Busca dados de um anúncio pelo ID MLB.
        Retorna título, preço, estoque, status, etc.
        """
        # Remove prefixo MLB- se presente para normalizar
        item_id = mlb_id.upper().replace("-", "")
        if not item_id.startswith("MLB"):
            item_id = f"MLB{item_id}"

        return await self._request("GET", f"/items/{item_id}")

    async def get_listing_visits(
        self,
        mlb_id: str,
        date_from: date,
        date_to: date,
    ) -> dict:
        """
        Busca visitas de um anúncio em um período.
        Endpoint: /visits/items?ids={mlb_id}&date_from=...&date_to=...
        """
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
        """
        Busca anúncios ativos de um usuário ML.
        """
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
        """
        Busca perguntas de um anúncio.
        """
        item_id = mlb_id.upper().replace("-", "")
        if not item_id.startswith("MLB"):
            item_id = f"MLB{item_id}"

        return await self._request(
            "GET",
            "/questions/search",
            params={"item": item_id, "status": "unanswered"},
        )

    async def close(self):
        """Fecha o cliente HTTP."""
        await self._client.aclose()
