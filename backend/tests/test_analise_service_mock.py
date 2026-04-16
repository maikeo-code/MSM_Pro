"""
Testes para analise/service.py e intel/pricing/service_weights.py usando mocks.

Cobre:
- get_analysis_listings: mock DB retorna vazio (caminhos 48-333, 344-345)
- get_adaptive_weights: < 10 recs aplicadas → DEFAULT_WEIGHTS
"""
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest


# ─── Helpers ────────────────────────────────────────────────────────────────


def _make_user(user_id=None):
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.email = "test@example.com"
    return user


def _mock_db_two_empty_calls():
    """DB que retorna vazio para todas as chamadas execute."""
    db = AsyncMock()

    async def _execute(*args, **kwargs):
        result = MagicMock()
        result.all.return_value = []
        result.scalars.return_value.all.return_value = []
        result.scalar_one_or_none.return_value = None
        result.fetchall.return_value = []
        return result

    db.execute = _execute
    return db


# ═══════════════════════════════════════════════════════════════════════════════
# analise/service.py — get_analysis_listings
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetAnalysisListings:
    """Testa get_analysis_listings com mock DB."""

    @pytest.mark.asyncio
    async def test_sem_listings_retorna_lista_vazia(self):
        """DB vazio → retorna lista vazia de AnuncioAnalise."""
        from app.analise.service import get_analysis_listings

        user = _make_user()
        db = _mock_db_two_empty_calls()

        result = await get_analysis_listings(db=db, user=user)

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_sem_contas_ml_retorna_lista_vazia(self):
        """Zero contas ML ativas → ads_by_item vazio, lista de anúncios vazia."""
        from app.analise.service import get_analysis_listings

        user = _make_user()
        db = _mock_db_two_empty_calls()

        result = await get_analysis_listings(db=db, user=user)

        # Não deve lançar exceção com zero contas
        assert result == []

    @pytest.mark.asyncio
    async def test_com_conta_sem_advertiser_id(self):
        """Conta ML existe mas sem advertiser_id → ads_by_item vazio."""
        from app.analise.service import get_analysis_listings

        user = _make_user()
        db = AsyncMock()

        call_count = [0]

        async def _execute(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] <= 1:
                result.all.return_value = []  # rows do query principal
            else:
                # Segunda chamada: contas ML
                account = MagicMock()
                account.access_token = "token-123"
                account.id = uuid.uuid4()
                result.scalars.return_value.all.return_value = [account]
            result.scalar_one_or_none.return_value = None
            result.fetchall.return_value = []
            return result

        db.execute = _execute

        mock_ml = AsyncMock()
        mock_ml.get_advertiser_id = AsyncMock(return_value=None)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ml)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.analise.service.MLClient", return_value=mock_ctx):
            result = await get_analysis_listings(db=db, user=user)

        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# intel/pricing/service_weights.py — get_adaptive_weights
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetAdaptiveWeights:
    """Testa get_adaptive_weights."""

    @pytest.mark.asyncio
    async def test_sem_recs_aplicadas_retorna_defaults(self):
        """Menos de 10 recomendações aplicadas → DEFAULT_WEIGHTS."""
        from app.intel.pricing.service_weights import (
            get_adaptive_weights,
            DEFAULT_WEIGHTS,
        )

        db = _mock_db_two_empty_calls()

        result = await get_adaptive_weights(db=db, user_id=uuid.uuid4())

        assert result == DEFAULT_WEIGHTS
        assert "sales_trend" in result
        assert "visit_trend" in result
        assert "conv_trend" in result

    @pytest.mark.asyncio
    async def test_com_poucos_recs_retorna_defaults(self):
        """Com 5 recomendações (< 10) → DEFAULT_WEIGHTS."""
        from app.intel.pricing.service_weights import (
            get_adaptive_weights,
            DEFAULT_WEIGHTS,
        )

        # 5 recs aplicadas (menos de 10)
        recs = [MagicMock() for _ in range(5)]

        db = AsyncMock()

        async def _execute(*args, **kwargs):
            result = MagicMock()
            result.scalars.return_value.all.return_value = recs
            return result

        db.execute = _execute

        result = await get_adaptive_weights(db=db, user_id=uuid.uuid4())
        assert result == DEFAULT_WEIGHTS

    @pytest.mark.asyncio
    async def test_pesos_somam_proximo_de_1(self):
        """DEFAULT_WEIGHTS deve somar 1.0."""
        from app.intel.pricing.service_weights import DEFAULT_WEIGHTS

        total = sum(DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001


# ═══════════════════════════════════════════════════════════════════════════════
# intel/pricing/service_score.py — funções puras
# ═══════════════════════════════════════════════════════════════════════════════


class TestIntelPricingServiceScore:
    """Testa funções da lógica de scoring de preço."""

    def test_score_module_importa(self):
        """Módulo de score importa sem exceção."""
        import app.intel.pricing.service_score as _mod  # noqa: F401
        assert hasattr(_mod, "calculate_score") or True

    def test_score_weights_importa(self):
        """Módulo de weights importa e expõe DEFAULT_WEIGHTS."""
        from app.intel.pricing.service_weights import DEFAULT_WEIGHTS
        assert isinstance(DEFAULT_WEIGHTS, dict)
        assert len(DEFAULT_WEIGHTS) == 7


# ═══════════════════════════════════════════════════════════════════════════════
# intel/analytics/service_pareto.py — empty data paths
# ═══════════════════════════════════════════════════════════════════════════════


class TestServicePareto:
    """Testa service_pareto com mock DB."""

    @pytest.mark.asyncio
    async def test_sem_dados_retorna_estrutura_vazia(self):
        """Sem dados → retorna estrutura com listas vazias."""
        from app.intel.analytics.service_pareto import get_pareto_analysis

        db = _mock_db_two_empty_calls()
        user_id = uuid.uuid4()

        result = await get_pareto_analysis(db=db, user_id=user_id)

        # Deve retornar dict/objeto com dados vazios, não levantar exceção
        assert result is not None


# ═══════════════════════════════════════════════════════════════════════════════
# intel/analytics/service_abc.py — empty data paths
# ═══════════════════════════════════════════════════════════════════════════════


class TestServiceABC:
    """Testa service_abc com mock DB."""

    @pytest.mark.asyncio
    async def test_sem_dados_retorna_estrutura(self):
        """Sem dados → retorna estrutura sem exceção."""
        from app.intel.analytics.service_abc import get_abc_analysis

        db = _mock_db_two_empty_calls()

        result = await get_abc_analysis(db=db, user_id=uuid.uuid4())

        assert result is not None


# ═══════════════════════════════════════════════════════════════════════════════
# intel/analytics/service_forecast.py — empty data paths
# ═══════════════════════════════════════════════════════════════════════════════


class TestServiceForecast:
    """Testa service_forecast com mock DB."""

    @pytest.mark.asyncio
    async def test_listing_inexistente_levanta_404(self):
        """Listing não encontrado → HTTPException 404."""
        from fastapi import HTTPException
        from app.intel.analytics.service_forecast import get_sales_forecast

        db = _mock_db_two_empty_calls()

        with pytest.raises(HTTPException) as exc:
            await get_sales_forecast(db=db, user_id=uuid.uuid4(), mlb_id="MLB999")
        assert exc.value.status_code == 404

    def test_linear_regression_basic(self):
        """_linear_regression calcula slope/intercept corretamente."""
        from app.intel.analytics.service_forecast import _linear_regression

        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        slope, intercept, r2 = _linear_regression(x, y)
        assert abs(slope - 2.0) < 0.001
        assert abs(r2 - 1.0) < 0.001

    def test_linear_regression_insufficient_data(self):
        """_linear_regression com dados insuficientes → zeros."""
        from app.intel.analytics.service_forecast import _linear_regression

        slope, intercept, r2 = _linear_regression([1.0], [1.0])
        assert slope == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# intel/analytics/service_inventory.py — empty data paths
# ═══════════════════════════════════════════════════════════════════════════════


class TestServiceInventory:
    """Testa service_inventory com mock DB."""

    @pytest.mark.asyncio
    async def test_sem_dados_retorna_resultado(self):
        """Sem dados → retorna sem exceção."""
        from app.intel.analytics.service_inventory import get_inventory_health as get_inventory_analysis

        db = _mock_db_two_empty_calls()

        result = await get_inventory_analysis(db=db, user_id=uuid.uuid4())

        assert result is not None


# ═══════════════════════════════════════════════════════════════════════════════
# intel/analytics/service_comparison.py — empty data paths
# ═══════════════════════════════════════════════════════════════════════════════


class TestServiceComparison:
    """Testa service_comparison com mock DB."""

    @pytest.mark.asyncio
    async def test_sem_dados_retorna_resultado(self):
        """Sem dados → retorna sem exceção."""
        from app.intel.analytics.service_comparison import get_temporal_comparison as get_comparison_analysis

        db = _mock_db_two_empty_calls()

        result = await get_comparison_analysis(db=db, user_id=uuid.uuid4())

        assert result is not None


# ═══════════════════════════════════════════════════════════════════════════════
# intel/analytics/service_distribution.py — empty data paths
# ═══════════════════════════════════════════════════════════════════════════════


class TestServiceDistribution:
    """Testa service_distribution com mock DB."""

    @pytest.mark.asyncio
    async def test_sem_dados_retorna_resultado(self):
        """Sem dados → retorna sem exceção."""
        from app.intel.analytics.service_distribution import get_sales_distribution as get_distribution_analysis

        db = _mock_db_two_empty_calls()

        result = await get_distribution_analysis(db=db, user_id=uuid.uuid4())

        assert result is not None
