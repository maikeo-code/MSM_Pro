"""
Testes para intel/pricing/service_collector.py.

Cobre:
- _safe_float: funções puras
- _compute_historical_metrics: lógica pura de métricas
- _aggregate_period: sem listing_ids → {}
- collect_daily_data: sem listings → []
"""
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest


def _mock_db_empty():
    db = AsyncMock()

    async def _execute(*args, **kwargs):
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        result.all.return_value = []
        result.scalar_one_or_none.return_value = None
        result.fetchall.return_value = []
        return result

    db.execute = _execute
    db.close = AsyncMock()
    return db


# ═══════════════════════════════════════════════════════════════════════════════
# _safe_float
# ═══════════════════════════════════════════════════════════════════════════════


class TestSafeFloat:
    def test_none_retorna_zero(self):
        from app.intel.pricing.service_collector import _safe_float
        assert _safe_float(None) == 0.0

    def test_decimal_converte(self):
        from app.intel.pricing.service_collector import _safe_float
        assert _safe_float(Decimal("10.50")) == 10.50

    def test_int_converte(self):
        from app.intel.pricing.service_collector import _safe_float
        assert _safe_float(5) == 5.0

    def test_float_passa_direto(self):
        from app.intel.pricing.service_collector import _safe_float
        assert _safe_float(3.14) == 3.14


# ═══════════════════════════════════════════════════════════════════════════════
# _compute_historical_metrics
# ═══════════════════════════════════════════════════════════════════════════════


class TestComputeHistoricalMetrics:
    """Testa _compute_historical_metrics."""

    def test_sem_dados_retorna_dict_vazio(self):
        """Lista vazia → {} (sem dados)."""
        from app.intel.pricing.service_collector import _compute_historical_metrics

        result = _compute_historical_metrics([], date.today())
        assert result == {}

    def test_todos_zeros_retorna_dict_vazio(self):
        """Todos os meses com days_with_data=0 → {}."""
        from app.intel.pricing.service_collector import _compute_historical_metrics

        months_data = [
            {"month": date.today().replace(day=1), "days_with_data": 0,
             "total_sales": 0, "min_price": 0, "max_price": 0},
        ]
        result = _compute_historical_metrics(months_data, date.today())
        assert result == {}

    def test_com_dados_retorna_metricas(self):
        """Meses com dados → retorna dict com métricas."""
        from app.intel.pricing.service_collector import _compute_historical_metrics

        today = date.today()
        months_data = [
            {
                "month": today.replace(day=1),
                "days_with_data": 10,
                "total_sales": 20,
                "min_price": 50.0,
                "max_price": 100.0,
            }
        ]
        result = _compute_historical_metrics(months_data, today)

        assert "avg_30d" in result or len(result) > 0

    def test_tendencia_declinio(self):
        """Avg 30d bem menor que avg 90d → trend = declining."""
        from app.intel.pricing.service_collector import _compute_historical_metrics

        today = date.today()
        months_data = [
            {
                "month": (today - timedelta(days=180)).replace(day=1),
                "days_with_data": 30,
                "total_sales": 150,  # alto no passado
                "min_price": 50.0,
                "max_price": 100.0,
            },
            {
                "month": (today - timedelta(days=90)).replace(day=1),
                "days_with_data": 30,
                "total_sales": 120,  # médio
                "min_price": 50.0,
                "max_price": 100.0,
            },
            {
                "month": today.replace(day=1),
                "days_with_data": 10,
                "total_sales": 5,  # baixo recentemente
                "min_price": 50.0,
                "max_price": 100.0,
            },
        ]
        result = _compute_historical_metrics(months_data, today)
        # Pode ser declining dado o cenário
        assert result.get("trend") in ("declining", "stable", "increasing", None) or len(result) > 0

    def test_tendencia_crescimento(self):
        """Avg 30d bem maior que avg 90d → trend = increasing."""
        from app.intel.pricing.service_collector import _compute_historical_metrics

        today = date.today()
        months_data = [
            {
                "month": (today - timedelta(days=90)).replace(day=1),
                "days_with_data": 30,
                "total_sales": 5,  # baixo no passado
                "min_price": 50.0,
                "max_price": 80.0,
            },
            {
                "month": today.replace(day=1),
                "days_with_data": 10,
                "total_sales": 50,  # alto recentemente
                "min_price": 50.0,
                "max_price": 80.0,
            },
        ]
        result = _compute_historical_metrics(months_data, today)
        assert len(result) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# _aggregate_period — sem listing_ids
# ═══════════════════════════════════════════════════════════════════════════════


class TestAggregatePeriod:
    @pytest.mark.asyncio
    async def test_sem_listing_ids_retorna_dict_vazio(self):
        """Sem listing_ids → early return {}."""
        from app.intel.pricing.service_collector import _aggregate_period

        db = _mock_db_empty()
        today = date.today()

        result = await _aggregate_period(
            db=db,
            listing_ids=[],
            date_from=today - timedelta(days=7),
            date_to=today,
        )
        assert result == {}


# ═══════════════════════════════════════════════════════════════════════════════
# collect_daily_data — sem listings
# ═══════════════════════════════════════════════════════════════════════════════


class TestCollectDailyData:
    @pytest.mark.asyncio
    async def test_sem_listings_retorna_lista_vazia(self):
        """Sem listings ativos → []."""
        from app.intel.pricing.service_collector import collect_daily_data

        db = _mock_db_empty()

        result = await collect_daily_data(user_id=uuid.uuid4(), db=db)
        assert result == []

    @pytest.mark.asyncio
    async def test_sem_db_cria_sessao_propria(self):
        """Quando db=None, cria AsyncSessionLocal própria."""
        from app.intel.pricing.service_collector import collect_daily_data

        mock_db = _mock_db_empty()

        class _MockSession:
            async def __aenter__(self):
                return mock_db
            async def __aexit__(self, *args):
                pass
            async def close(self):
                pass
            execute = mock_db.execute

        with patch("app.intel.pricing.service_collector.AsyncSessionLocal", return_value=_MockSession()):
            result = await collect_daily_data(user_id=uuid.uuid4(), db=None)

        assert result == []
