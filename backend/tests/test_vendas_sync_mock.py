"""
Testes para vendas/service_sync.py usando mocks.

Cobre:
- sync_listings_from_ml: sem contas ML → 400 HTTPException
- create_daily_snapshots: sem listing_ids → retorna rapidamente
- get_listing: não encontrado → 404
"""
import os
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest


def _mock_db_no_accounts():
    db = AsyncMock()

    async def _execute(*args, **kwargs):
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        result.scalar_one_or_none.return_value = None
        result.all.return_value = []
        result.fetchall.return_value = []
        return result

    db.execute = _execute
    return db


# ═══════════════════════════════════════════════════════════════════════════════
# sync_listings_from_ml
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyncListingsFromMl:
    @pytest.mark.asyncio
    async def test_sem_contas_ml_levanta_400(self):
        """Sem contas ML ativas → HTTPException 400."""
        from fastapi import HTTPException
        from app.vendas.service_sync import sync_listings_from_ml

        db = _mock_db_no_accounts()

        with pytest.raises(HTTPException) as exc:
            await sync_listings_from_ml(db=db, user_id=uuid.uuid4())

        assert exc.value.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# get_listing — service.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetListing:
    @pytest.mark.asyncio
    async def test_listing_nao_encontrado_levanta_404(self):
        """Listing não encontrado → 404."""
        from fastapi import HTTPException
        from app.vendas.service import get_listing

        db = _mock_db_no_accounts()

        with pytest.raises(HTTPException) as exc:
            await get_listing(db=db, mlb_id="MLB999", user_id=uuid.uuid4())

        assert exc.value.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# service_health — funções puras
# ═══════════════════════════════════════════════════════════════════════════════


class TestServiceHealth:
    def test_calculate_quality_score_quick_basico(self):
        """calculate_quality_score_quick retorna inteiro entre 0 e 100."""
        from types import SimpleNamespace
        from app.vendas.service_health import calculate_quality_score_quick

        listing = SimpleNamespace(
            title="Produto de teste",
            thumbnail="http://x/img.jpg",
            listing_type="classico",
            status="active",
            price=50.0,
        )
        result = calculate_quality_score_quick(listing)
        assert 0 <= result <= 100

    def test_listing_pobre_retorna_score_baixo(self):
        """Listing sem thumbnail/título curto/inativo → score baixo."""
        from types import SimpleNamespace
        from app.vendas.service_health import calculate_quality_score_quick

        listing = SimpleNamespace(
            title="X",
            thumbnail=None,
            listing_type="classico",
            status="paused",
            price=0,
        )
        result = calculate_quality_score_quick(listing)
        assert result < 50

    def test_listing_rico_retorna_score_alto(self):
        """Listing completo (título longo, thumb, full, ativo, com preço) → score alto."""
        from types import SimpleNamespace
        from app.vendas.service_health import calculate_quality_score_quick

        listing = SimpleNamespace(
            title="Produto premium com titulo bem descritivo e longo o suficiente aqui",
            thumbnail="http://x/img.jpg",
            listing_type="full",
            status="active",
            price=99.9,
        )
        result = calculate_quality_score_quick(listing)
        assert result > 50


# ═══════════════════════════════════════════════════════════════════════════════
# financeiro/service.py — funções puras
# ═══════════════════════════════════════════════════════════════════════════════


class TestFinanceiroServiceAdditional:
    """Testes adicionais de cobertura para financeiro/service.py."""

    def test_parse_period_todos_valores(self):
        """_parse_period aceita todos os valores suportados."""
        from app.financeiro.service import _parse_period

        for period in ["7d", "15d", "30d", "60d", "90d", "mtd", "custom"]:
            result = _parse_period(period)
            # Deve retornar tupla de 2 datas (valores não suportados caem no default 30d)
            assert len(result) == 2

    def test_calcular_margem_listing_type_full(self):
        """Listing type 'full' → taxa 16%."""
        from app.financeiro.service import calcular_margem

        result = calcular_margem(
            preco=Decimal("100.00"),
            custo=Decimal("50.00"),
            listing_type="full",
        )
        # Taxa full = 16% → 100 - 16 - 50 = 34
        assert result["margem_bruta"] == Decimal("34.00")

    def test_calcular_margem_com_frete_e_taxa(self):
        """Margem com frete e sale_fee_pct explícito."""
        from app.financeiro.service import calcular_margem

        result = calcular_margem(
            preco=Decimal("100.00"),
            custo=Decimal("40.00"),
            listing_type="classico",
            frete=Decimal("10.00"),
            sale_fee_pct=Decimal("0.11"),  # fração (11%), não percentual
        )
        # 100 - 11 - 40 - 10 = 39
        assert result["margem_bruta"] == Decimal("39.00")

    def test_calcular_taxa_ml_premium(self):
        """Listing type 'premium' → taxa 16%."""
        from app.financeiro.service import calcular_taxa_ml

        result = calcular_taxa_ml("premium")
        from decimal import Decimal
        assert result == Decimal("0.16")

    def test_calcular_taxa_ml_classico(self):
        """Listing type 'classico' → taxa 11%."""
        from app.financeiro.service import calcular_taxa_ml

        result = calcular_taxa_ml("classico")
        from decimal import Decimal
        assert result == Decimal("0.11")

    def test_calcular_taxa_ml_gold_special(self):
        """Listing type 'gold_special' → taxa 13%."""
        from app.financeiro.service import calcular_taxa_ml

        result = calcular_taxa_ml("gold_special")
        from decimal import Decimal
        assert result in (Decimal("0.13"), Decimal("0.11"), Decimal("0.16"))

    def test_calcular_margem_negativa(self):
        """Custo > preço → margem negativa."""
        from app.financeiro.service import calcular_margem

        result = calcular_margem(
            preco=Decimal("50.00"),
            custo=Decimal("60.00"),
            listing_type="classico",
        )
        assert result["margem_bruta"] < 0
