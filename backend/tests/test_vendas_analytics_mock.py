"""
Testes para vendas/service_analytics.py usando mocks de DB.

Cobre:
- get_funnel_analytics: caminho com listing_ids vazio (early return)
- get_listing_analysis: HTTP 404 → retorna mock analysis
- _fetch_ads_for_listing: conta sem token → retorna {}
- _fetch_promotions_for_listing: conta sem token → retorna []
"""
import os
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest


# ─── Helpers ────────────────────────────────────────────────────────────────


def _mock_db_empty():
    """DB com execute retornando resultados vazios."""
    db = AsyncMock()

    async def _execute(*args, **kwargs):
        result = MagicMock()
        result.fetchall.return_value = []
        result.all.return_value = []
        result.scalars.return_value.all.return_value = []
        result.scalar_one_or_none.return_value = None
        result.scalar.return_value = None
        return result

    db.execute = _execute
    return db


def _mock_db_with_listing_ids(listing_ids: list):
    """DB que retorna listing_ids na primeira chamada, vazio nas demais."""
    db = AsyncMock()
    call_count = [0]

    async def _execute(*args, **kwargs):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            # Primeira chamada: retorna listing_ids como rows
            rows = [MagicMock() for _ in listing_ids]
            for i, row in enumerate(rows):
                row.__getitem__ = lambda self, idx: listing_ids[i]
                row[0] = listing_ids[i]
            # fetchall retorna rows onde row[0] é o id
            fake_rows = [(lid,) for lid in listing_ids]
            result.fetchall.return_value = fake_rows
        else:
            result.fetchall.return_value = []
            result.all.return_value = []
        result.scalars.return_value.all.return_value = []
        result.scalar_one_or_none.return_value = None
        return result

    db.execute = _execute
    return db


# ═══════════════════════════════════════════════════════════════════════════════
# get_funnel_analytics
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetFunnelAnalytics:
    """Testa get_funnel_analytics com mock de DB."""

    @pytest.mark.asyncio
    async def test_sem_listings_retorna_zeros(self):
        """Usuário sem listings → early return com zeros."""
        from app.vendas.service_analytics import get_funnel_analytics

        db = _mock_db_empty()
        user_id = uuid.uuid4()

        result = await get_funnel_analytics(db=db, user_id=user_id, period_days=7)

        assert result["visitas"] == 0
        assert result["vendas"] == 0
        assert result["conversao"] == 0.0
        assert result["receita"] == 0.0

    @pytest.mark.asyncio
    async def test_sem_listings_com_ml_account_id(self):
        """Com ml_account_id mas sem listings → early return com zeros."""
        from app.vendas.service_analytics import get_funnel_analytics

        db = _mock_db_empty()
        user_id = uuid.uuid4()

        result = await get_funnel_analytics(
            db=db,
            user_id=user_id,
            period_days=30,
            ml_account_id=uuid.uuid4(),
        )

        assert result["visitas"] == 0
        assert result["vendas"] == 0

    @pytest.mark.asyncio
    async def test_sem_listings_period_days_1(self):
        """period_days=1 sem listings → early return."""
        from app.vendas.service_analytics import get_funnel_analytics

        db = _mock_db_empty()

        result = await get_funnel_analytics(
            db=db,
            user_id=uuid.uuid4(),
            period_days=1,
        )

        assert result["conversao"] == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# get_listing_analysis — HTTPException → mock analysis
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetListingAnalysis:
    """Testa get_listing_analysis."""

    @pytest.mark.asyncio
    async def test_listing_nao_cadastrado_retorna_mock(self):
        """Listing não cadastrado (404) → retorna análise de demonstração."""
        from fastapi import HTTPException
        from app.vendas.service_analytics import get_listing_analysis

        db = _mock_db_empty()

        # Mock get_listing para lançar 404
        with patch(
            "app.vendas.service.get_listing",
            side_effect=HTTPException(status_code=404),
        ):
            result = await get_listing_analysis(
                db=db,
                mlb_id="MLB6205732214",
                user_id=uuid.uuid4(),
                days=30,
            )

        # Deve retornar uma análise de mock (dict não vazio)
        assert isinstance(result, dict)
        # A função _generate_mock_analysis retorna algo com 'title' ou 'listing'
        assert len(result) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# _fetch_ads_for_listing — sem token na conta ML
# ═══════════════════════════════════════════════════════════════════════════════


class TestFetchAdsForListing:
    """Testa _fetch_ads_for_listing."""

    @pytest.mark.asyncio
    async def test_sem_token_retorna_dict_vazio(self):
        """Conta ML sem token → retorna {} graciosamente."""
        from app.vendas.service_analytics import _fetch_ads_for_listing

        listing = MagicMock()
        listing.ml_account_id = uuid.uuid4()
        listing.mlb_id = "MLB123456"

        account_no_token = MagicMock()
        account_no_token.access_token = None

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = account_no_token
        db.execute = AsyncMock(return_value=result_mock)

        result = await _fetch_ads_for_listing(db=db, listing=listing)
        assert result == {}

    @pytest.mark.asyncio
    async def test_conta_nao_encontrada_retorna_dict_vazio(self):
        """Conta ML não encontrada → retorna {} graciosamente."""
        from app.vendas.service_analytics import _fetch_ads_for_listing

        listing = MagicMock()
        listing.ml_account_id = uuid.uuid4()
        listing.mlb_id = "MLB999"

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        result = await _fetch_ads_for_listing(db=db, listing=listing)
        assert result == {}

    @pytest.mark.asyncio
    async def test_excecao_retorna_dict_vazio(self):
        """Exceção genérica → retorna {} graciosamente."""
        from app.vendas.service_analytics import _fetch_ads_for_listing

        listing = MagicMock()
        listing.ml_account_id = uuid.uuid4()
        listing.mlb_id = "MLB000"

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=Exception("DB error"))

        result = await _fetch_ads_for_listing(db=db, listing=listing)
        assert result == {}


# ═══════════════════════════════════════════════════════════════════════════════
# _fetch_promotions_for_listing — sem token na conta ML
# ═══════════════════════════════════════════════════════════════════════════════


class TestFetchPromotionsForListing:
    """Testa _fetch_promotions_for_listing."""

    @pytest.mark.asyncio
    async def test_sem_token_retorna_lista_vazia(self):
        """Conta ML sem token → retorna []."""
        from app.vendas.service_analytics import _fetch_promotions_for_listing

        listing = MagicMock()
        listing.ml_account_id = uuid.uuid4()
        listing.mlb_id = "MLB123"

        account_no_token = MagicMock()
        account_no_token.access_token = None

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = account_no_token
        db.execute = AsyncMock(return_value=result_mock)

        result = await _fetch_promotions_for_listing(db=db, listing=listing)
        assert result == []

    @pytest.mark.asyncio
    async def test_conta_nao_encontrada_retorna_lista_vazia(self):
        """Conta não encontrada → retorna []."""
        from app.vendas.service_analytics import _fetch_promotions_for_listing

        listing = MagicMock()
        listing.ml_account_id = uuid.uuid4()
        listing.mlb_id = "MLB456"

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        result = await _fetch_promotions_for_listing(db=db, listing=listing)
        assert result == []

    @pytest.mark.asyncio
    async def test_excecao_retorna_lista_vazia(self):
        """Exceção → retorna [] graciosamente."""
        from app.vendas.service_analytics import _fetch_promotions_for_listing

        listing = MagicMock()
        listing.ml_account_id = uuid.uuid4()
        listing.mlb_id = "MLB789"

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=Exception("network error"))

        result = await _fetch_promotions_for_listing(db=db, listing=listing)
        assert result == []

    @pytest.mark.asyncio
    async def test_com_token_api_retorna_lista_nao_list(self):
        """API retorna dict em vez de list → retorna []."""
        from app.vendas.service_analytics import _fetch_promotions_for_listing

        listing = MagicMock()
        listing.ml_account_id = uuid.uuid4()
        listing.mlb_id = "MLB111"

        account = MagicMock()
        account.access_token = "valid-token"

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = account
        db.execute = AsyncMock(return_value=result_mock)

        mock_ml = AsyncMock()
        mock_ml.get_item_promotions = AsyncMock(return_value={"error": "not a list"})

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ml)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.mercadolivre.client.MLClient", return_value=mock_ctx):
            result = await _fetch_promotions_for_listing(db=db, listing=listing)

        assert result == []

    @pytest.mark.asyncio
    async def test_com_token_api_retorna_lista_valida(self):
        """API retorna lista de promoções → converte corretamente."""
        from app.vendas.service_analytics import _fetch_promotions_for_listing

        listing = MagicMock()
        listing.ml_account_id = uuid.uuid4()
        listing.mlb_id = "MLB222"

        account = MagicMock()
        account.access_token = "valid-token"

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = account
        db.execute = AsyncMock(return_value=result_mock)

        promo_data = [
            {
                "id": "promo-1",
                "type": "DEAL",
                "status": "started",
                "start_date": "2026-04-01",
                "finish_date": "2026-04-30",
                "original_price": "100.00",
                "price": "80.00",
            }
        ]

        mock_ml = AsyncMock()
        mock_ml.get_item_promotions = AsyncMock(return_value=promo_data)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ml)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.mercadolivre.client.MLClient", return_value=mock_ctx):
            result = await _fetch_promotions_for_listing(db=db, listing=listing)

        assert len(result) == 1
        assert result[0]["id"] == "promo-1"
        assert result[0]["type"] == "DEAL"
        # Desconto: (1 - 80/100) * 100 = 20%
        assert result[0]["discount_pct"] == 20.0

    @pytest.mark.asyncio
    async def test_calculo_desconto_sem_preco_original(self):
        """Promoção sem original_price → discount_pct é None."""
        from app.vendas.service_analytics import _fetch_promotions_for_listing

        listing = MagicMock()
        listing.ml_account_id = uuid.uuid4()
        listing.mlb_id = "MLB333"

        account = MagicMock()
        account.access_token = "valid-token"

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = account
        db.execute = AsyncMock(return_value=result_mock)

        promo_data = [
            {
                "id": "promo-2",
                "type": "DEAL",
                "status": "stopped",
                # sem original_price nem price
            }
        ]

        mock_ml = AsyncMock()
        mock_ml.get_item_promotions = AsyncMock(return_value=promo_data)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ml)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.mercadolivre.client.MLClient", return_value=mock_ctx):
            result = await _fetch_promotions_for_listing(db=db, listing=listing)

        assert len(result) == 1
        assert result[0]["discount_pct"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# get_listing_snapshots
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetListingSnapshots:
    """Testa get_listing_snapshots."""

    @pytest.mark.asyncio
    async def test_listing_nao_encontrado_retorna_404(self):
        """Listing não encontrado → HTTPException 404."""
        from fastapi import HTTPException
        from app.vendas.service_analytics import get_listing_snapshots

        db = _mock_db_empty()

        # Mock get_listing para retornar None (não encontrado)
        with patch(
            "app.vendas.service.get_listing",
            side_effect=HTTPException(status_code=404),
        ):
            with pytest.raises(HTTPException) as exc:
                await get_listing_snapshots(
                    db=db,
                    mlb_id="MLB000",
                    user_id=uuid.uuid4(),
                    dias=30,
                )
            assert exc.value.status_code == 404
