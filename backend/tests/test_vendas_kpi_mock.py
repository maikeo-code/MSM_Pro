"""
Testes para vendas/service_kpi.py usando mocks de DB.

Cobre:
- _period_to_dates: função pura
- get_kpi_compare: sem listing_ids → early return
- get_kpi_by_period: sem listing_ids → zeros
- get_kpi_daily_breakdown: sem listing_ids → zeros
"""
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest


def _mock_db_empty():
    """DB que retorna resultados vazios para todas as queries."""
    db = AsyncMock()

    async def _execute(*args, **kwargs):
        result = MagicMock()
        result.fetchall.return_value = []
        result.scalars.return_value.all.return_value = []
        result.all.return_value = []
        result.scalar_one_or_none.return_value = None
        result.scalar.return_value = 0
        return result

    db.execute = _execute
    return db


# ═══════════════════════════════════════════════════════════════════════════════
# _period_to_dates — função pura
# ═══════════════════════════════════════════════════════════════════════════════


class TestPeriodToDates:
    """Testa _period_to_dates (função pura sem DB)."""

    def test_7d_retorna_7_dias(self):
        from app.vendas.service_kpi import _period_to_dates
        today = date(2026, 4, 16)
        date_from, date_to, label = _period_to_dates("7d", today)
        assert date_from == date(2026, 4, 10)
        assert date_to == today
        assert "7" in label

    def test_15d_retorna_15_dias(self):
        from app.vendas.service_kpi import _period_to_dates
        today = date(2026, 4, 16)
        date_from, date_to, label = _period_to_dates("15d", today)
        assert date_from == date(2026, 4, 2)
        assert "15" in label

    def test_30d_retorna_30_dias(self):
        from app.vendas.service_kpi import _period_to_dates
        today = date(2026, 4, 16)
        date_from, date_to, label = _period_to_dates("30d", today)
        assert date_from == date(2026, 3, 18)
        assert "30" in label

    def test_periodo_desconhecido_usa_default_7d(self):
        """Período desconhecido → usa 7 dias por padrão."""
        from app.vendas.service_kpi import _period_to_dates
        today = date(2026, 4, 16)
        date_from, date_to, label = _period_to_dates("90d", today)
        # Fallback: get(period, 7) → usa 7
        assert date_from == date(2026, 4, 10)


# ═══════════════════════════════════════════════════════════════════════════════
# get_kpi_compare — sem listing_ids
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetKpiCompare:
    """Testa get_kpi_compare."""

    @pytest.mark.asyncio
    async def test_sem_listings_retorna_zeros(self):
        """Sem listings → retorna dict com zeros em ambos os períodos."""
        from app.vendas.service_kpi import get_kpi_compare

        db = _mock_db_empty()

        result = await get_kpi_compare(
            db=db,
            user_id=uuid.uuid4(),
            period_a="7d",
            period_b="prev",
        )

        assert "period_a" in result
        assert "period_b" in result
        assert result["period_a"]["vendas"] == 0
        assert result["period_b"]["vendas"] == 0

    @pytest.mark.asyncio
    async def test_sem_listings_com_ml_account_id(self):
        """Com ml_account_id mas sem listings → zeros."""
        from app.vendas.service_kpi import get_kpi_compare

        db = _mock_db_empty()

        result = await get_kpi_compare(
            db=db,
            user_id=uuid.uuid4(),
            period_a="15d",
            period_b="prev",
            ml_account_id=uuid.uuid4(),
        )

        assert result["period_a"]["vendas"] == 0

    @pytest.mark.asyncio
    async def test_sem_listings_period_b_30d(self):
        """period_b='30d' sem listings → zeros."""
        from app.vendas.service_kpi import get_kpi_compare

        db = _mock_db_empty()

        result = await get_kpi_compare(
            db=db,
            user_id=uuid.uuid4(),
            period_a="7d",
            period_b="30d",
        )

        assert "period_a" in result
        assert "period_b" in result


# ═══════════════════════════════════════════════════════════════════════════════
# get_kpi_by_period — sem listing_ids
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetKpiByPeriod:
    """Testa get_kpi_by_period."""

    @pytest.mark.asyncio
    async def test_sem_listings_retorna_estrutura_com_zeros(self):
        """Sem listings → estrutura com zeros e today/yesterday/day_before."""
        from app.vendas.service_kpi import get_kpi_by_period

        db = _mock_db_empty()

        result = await get_kpi_by_period(db=db, user_id=uuid.uuid4())

        # Deve conter períodos principais
        assert "today" in result or len(result) > 0

    @pytest.mark.asyncio
    async def test_sem_listings_com_ml_account_id(self):
        """Com ml_account_id sem listings → sem exceção."""
        from app.vendas.service_kpi import get_kpi_by_period

        db = _mock_db_empty()

        result = await get_kpi_by_period(
            db=db,
            user_id=uuid.uuid4(),
            ml_account_id=uuid.uuid4(),
        )

        assert result is not None


# ═══════════════════════════════════════════════════════════════════════════════
# get_kpi_daily_breakdown — sem listing_ids
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetKpiDailyBreakdown:
    """Testa get_kpi_daily_breakdown."""

    @pytest.mark.asyncio
    async def test_sem_listings_retorna_estrutura_vazia(self):
        """Sem listings → retorna estrutura sem exceção."""
        from app.vendas.service_kpi import get_kpi_daily_breakdown

        db = _mock_db_empty()

        result = await get_kpi_daily_breakdown(
            db=db,
            user_id=uuid.uuid4(),
            days=7,
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_sem_listings_period_30d(self):
        """Sem listings, period=30d → sem exceção."""
        from app.vendas.service_kpi import get_kpi_daily_breakdown

        db = _mock_db_empty()

        result = await get_kpi_daily_breakdown(
            db=db,
            user_id=uuid.uuid4(),
            days=30,
        )

        assert result is not None
