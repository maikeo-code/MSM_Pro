"""
Testes adicionais para alertas/service.py usando mocks.

Cobre:
- _get_listing_ids_for_alert: listing_id direto, product_id, nenhum
- _check_condition: tipo desconhecido → None
- _check_conversion_below / _check_stock_below: sem listing_ids → None
- _check_no_sales_days / _check_competitor_price_change: sem listing_ids → None
- evaluate_single_alert: condition=None → None; cooldown → None
"""
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest


# ─── Helpers ────────────────────────────────────────────────────────────────


def _make_alert(
    alert_type="conversion_below",
    listing_id=None,
    product_id=None,
    threshold=None,
    last_triggered_at=None,
    user_id=None,
):
    alert = MagicMock()
    alert.id = uuid.uuid4()
    alert.user_id = user_id or uuid.uuid4()
    alert.alert_type = alert_type
    alert.listing_id = listing_id
    alert.product_id = product_id
    alert.threshold = threshold
    alert.last_triggered_at = last_triggered_at
    alert.is_active = True
    return alert


def _mock_db_empty():
    db = AsyncMock()

    async def _execute(*args, **kwargs):
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        result.scalar_one_or_none.return_value = None
        result.all.return_value = []
        return result

    db.execute = _execute
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _mock_db_with_listing_ids(ids: list):
    """DB que retorna IDs de listings como scalars."""
    db = AsyncMock()

    async def _execute(*args, **kwargs):
        result = MagicMock()
        result.scalars.return_value.all.return_value = ids
        result.scalar_one_or_none.return_value = None
        result.all.return_value = []
        return result

    db.execute = _execute
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return db


# ═══════════════════════════════════════════════════════════════════════════════
# _get_listing_ids_for_alert
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetListingIdsForAlert:
    """Testa _get_listing_ids_for_alert."""

    @pytest.mark.asyncio
    async def test_listing_id_direto_retorna_lista_com_um_id(self):
        """listing_id definido → retorna [listing_id] sem query."""
        from app.alertas.service import _get_listing_ids_for_alert

        lid = uuid.uuid4()
        alert = _make_alert(listing_id=lid)
        db = _mock_db_empty()

        result = await _get_listing_ids_for_alert(db, alert)
        assert result == [lid]

    @pytest.mark.asyncio
    async def test_product_id_busca_no_db(self):
        """product_id definido → busca no DB e retorna lista."""
        from app.alertas.service import _get_listing_ids_for_alert

        pid = uuid.uuid4()
        ids_from_db = [uuid.uuid4(), uuid.uuid4()]
        alert = _make_alert(product_id=pid)
        db = _mock_db_with_listing_ids(ids_from_db)

        result = await _get_listing_ids_for_alert(db, alert)
        assert result == ids_from_db

    @pytest.mark.asyncio
    async def test_sem_listing_nem_product_retorna_vazio(self):
        """Sem listing_id nem product_id → retorna []."""
        from app.alertas.service import _get_listing_ids_for_alert

        alert = _make_alert()
        db = _mock_db_empty()

        result = await _get_listing_ids_for_alert(db, alert)
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# _check_condition — roteamento
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckCondition:
    """Testa _check_condition."""

    @pytest.mark.asyncio
    async def test_tipo_desconhecido_retorna_none(self):
        """Tipo de alerta desconhecido → warning + None."""
        from app.alertas.service import _check_condition

        alert = _make_alert(alert_type="tipo_inexistente_xyz")
        db = _mock_db_empty()

        result = await _check_condition(db, alert)
        assert result is None

    @pytest.mark.asyncio
    async def test_conversion_below_sem_listings_retorna_none(self):
        """conversion_below sem listings → None."""
        from app.alertas.service import _check_condition

        alert = _make_alert(alert_type="conversion_below", threshold=Decimal("5.0"))
        db = _mock_db_empty()

        result = await _check_condition(db, alert)
        assert result is None

    @pytest.mark.asyncio
    async def test_stock_below_sem_listings_retorna_none(self):
        """stock_below sem listings → None."""
        from app.alertas.service import _check_condition

        alert = _make_alert(alert_type="stock_below", threshold=Decimal("5"))
        db = _mock_db_empty()

        result = await _check_condition(db, alert)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_sales_days_sem_listings_retorna_none(self):
        """no_sales_days sem listings → None."""
        from app.alertas.service import _check_condition

        alert = _make_alert(alert_type="no_sales_days", threshold=Decimal("3"))
        db = _mock_db_empty()

        result = await _check_condition(db, alert)
        assert result is None

    @pytest.mark.asyncio
    async def test_competitor_price_change_sem_listings_retorna_none(self):
        """competitor_price_change sem listings → None."""
        from app.alertas.service import _check_condition

        alert = _make_alert(alert_type="competitor_price_change")
        db = _mock_db_empty()

        result = await _check_condition(db, alert)
        assert result is None

    @pytest.mark.asyncio
    async def test_competitor_price_below_sem_listings_retorna_none(self):
        """competitor_price_below sem listings → None."""
        from app.alertas.service import _check_condition

        alert = _make_alert(alert_type="competitor_price_below", threshold=Decimal("50.0"))
        db = _mock_db_empty()

        result = await _check_condition(db, alert)
        assert result is None

    @pytest.mark.asyncio
    async def test_visits_spike_sem_listings_retorna_none(self):
        """visits_spike sem listings → None."""
        from app.alertas.service import _check_condition

        alert = _make_alert(alert_type="visits_spike")
        db = _mock_db_empty()

        result = await _check_condition(db, alert)
        assert result is None

    @pytest.mark.asyncio
    async def test_conversion_improved_sem_listings_retorna_none(self):
        """conversion_improved sem listings → None."""
        from app.alertas.service import _check_condition

        alert = _make_alert(alert_type="conversion_improved")
        db = _mock_db_empty()

        result = await _check_condition(db, alert)
        assert result is None

    @pytest.mark.asyncio
    async def test_stockout_forecast_sem_listings_retorna_none(self):
        """stockout_forecast sem listings → None."""
        from app.alertas.service import _check_condition

        alert = _make_alert(alert_type="stockout_forecast")
        db = _mock_db_empty()

        result = await _check_condition(db, alert)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# evaluate_single_alert
# ═══════════════════════════════════════════════════════════════════════════════


class TestEvaluateAlertCondition:
    """Testa evaluate_single_alert."""

    @pytest.mark.asyncio
    async def test_condition_none_retorna_none(self):
        """Se _check_condition retorna None → evaluate retorna None."""
        from app.alertas.service import evaluate_single_alert

        alert = _make_alert(alert_type="tipo_inexistente_xyz")
        db = _mock_db_empty()

        result = await evaluate_single_alert(db, alert)
        assert result is None

    @pytest.mark.asyncio
    async def test_em_cooldown_retorna_none(self):
        """Alerta disparado há menos de 24h → cooldown → None."""
        from app.alertas.service import evaluate_single_alert
        from unittest.mock import patch, AsyncMock

        # last_triggered_at há 1 hora (dentro do cooldown de 24h)
        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        alert = _make_alert(
            alert_type="conversion_below",
            last_triggered_at=recent,
        )
        db = _mock_db_empty()

        # Mock _check_condition para retornar uma mensagem (condição atendida)
        with patch(
            "app.alertas.service._check_condition",
            new=AsyncMock(return_value="Alerta disparado!"),
        ):
            result = await evaluate_single_alert(db, alert)

        # Em cooldown → deve retornar None (não dispara)
        assert result is None

    @pytest.mark.asyncio
    async def test_fora_do_cooldown_cria_evento(self):
        """Fora do cooldown → cria AlertEvent e retorna."""
        from app.alertas.service import evaluate_single_alert
        from unittest.mock import patch, AsyncMock

        # last_triggered_at há 25h (fora do cooldown)
        old = datetime.now(timezone.utc) - timedelta(hours=25)
        alert = _make_alert(
            alert_type="stock_below",
            last_triggered_at=old,
        )

        db = _mock_db_empty()
        db.refresh = AsyncMock()

        with patch(
            "app.alertas.service._check_condition",
            new=AsyncMock(return_value="Estoque baixo!"),
        ):
            result = await evaluate_single_alert(db, alert)

        # Deve ter criado um evento
        db.add.assert_called_once()
        db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_sem_last_triggered_at_cria_evento(self):
        """Primeira vez disparando (sem cooldown) → cria AlertEvent."""
        from app.alertas.service import evaluate_single_alert
        from unittest.mock import patch, AsyncMock

        alert = _make_alert(
            alert_type="stock_below",
            last_triggered_at=None,
        )

        db = _mock_db_empty()
        db.refresh = AsyncMock()

        with patch(
            "app.alertas.service._check_condition",
            new=AsyncMock(return_value="Estoque crítico!"),
        ):
            result = await evaluate_single_alert(db, alert)

        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_excecao_em_check_condition_retorna_none(self):
        """Exceção em _check_condition → capturada → retorna None."""
        from app.alertas.service import evaluate_single_alert
        from unittest.mock import patch, AsyncMock

        alert = _make_alert(alert_type="conversion_below")
        db = _mock_db_empty()

        with patch(
            "app.alertas.service._check_condition",
            new=AsyncMock(side_effect=Exception("DB error")),
        ):
            result = await evaluate_single_alert(db, alert)

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# list_alert_events e list_events_by_alert (mock DB)
# ═══════════════════════════════════════════════════════════════════════════════


class TestListAlertEventsMock:
    """Testa list_alert_events com mock DB."""

    @pytest.mark.asyncio
    async def test_list_events_retorna_lista_do_db(self):
        """list_alert_events retorna o que o DB retorna."""
        from app.alertas.service import list_alert_events

        user_id = uuid.uuid4()
        fake_event = MagicMock()
        fake_event.id = uuid.uuid4()

        db = AsyncMock()

        async def _execute(*args, **kwargs):
            result = MagicMock()
            result.scalars.return_value.all.return_value = [fake_event]
            return result

        db.execute = _execute

        result = await list_alert_events(db, user_id)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_events_vazio(self):
        """list_alert_events retorna [] quando DB está vazio."""
        from app.alertas.service import list_alert_events

        db = _mock_db_empty()
        result = await list_alert_events(db, uuid.uuid4())
        assert result == []

    @pytest.mark.asyncio
    async def test_list_events_by_alert_sem_alert_config_levanta_404(self):
        """list_events_by_alert com alert inexistente → 404."""
        from fastapi import HTTPException
        from app.alertas.service import list_events_by_alert

        db = _mock_db_empty()

        with pytest.raises(HTTPException) as exc:
            await list_events_by_alert(db, uuid.uuid4(), uuid.uuid4())
        assert exc.value.status_code == 404
