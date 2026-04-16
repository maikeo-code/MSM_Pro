"""
Testes para alertas/service.py

Ciclo 11 do auto-learning — cobertura alvo:
- alertas/service.py: 42.6% → 65%+ (severidade + CRUD SQLite)

Estratégia:
- _calculate_severity: teste puro (sem DB)
- create_alert_config, list_alert_configs, get_alert_config,
  update_alert_config, deactivate_alert_config, list_alert_events,
  list_events_by_alert: SQLite real (sem PG-specific queries)
"""
import os
import uuid
from decimal import Decimal

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest

from app.auth.models import User
from app.alertas.models import AlertConfig, AlertEvent
from app.produtos.models import Product


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _uid():
    return uuid.uuid4()


def _make_user(email=None):
    return User(
        id=_uid(),
        email=email or f"u_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="hashed",
        is_active=True,
    )


def _make_product(user_id):
    return Product(
        id=_uid(),
        user_id=user_id,
        sku=f"SKU-{uuid.uuid4().hex[:6].upper()}",
        name="Produto Teste",
        cost=Decimal("25.00"),
        is_active=True,
    )


async def _make_alert_payload(db, user_id, alert_type="competitor_price_change",
                               threshold=None, channel="email", severity=None):
    """Cria AlertConfigCreate com product_id real no DB."""
    from app.alertas.schemas import AlertConfigCreate
    product = _make_product(user_id)
    db.add(product)
    await db.flush()
    return AlertConfigCreate(
        alert_type=alert_type,
        threshold=threshold,
        product_id=product.id,
        channel=channel,
        severity=severity,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 1: _calculate_severity — função pura
# ═══════════════════════════════════════════════════════════════════════════════


class TestCalculateSeverity:
    """Testa _calculate_severity."""

    def test_stock_below_critico(self):
        from app.alertas.service import _calculate_severity
        result = _calculate_severity("stock_below", Decimal("2"))
        assert result == "critical"

    def test_stock_below_threshold_3_critico(self):
        from app.alertas.service import _calculate_severity
        result = _calculate_severity("stock_below", Decimal("3"))
        assert result == "critical"

    def test_stock_below_warning(self):
        from app.alertas.service import _calculate_severity
        result = _calculate_severity("stock_below", Decimal("8"))
        assert result == "warning"

    def test_no_sales_days_critico(self):
        from app.alertas.service import _calculate_severity
        result = _calculate_severity("no_sales_days", Decimal("7"))
        assert result == "critical"

    def test_competitor_price_change_warning(self):
        from app.alertas.service import _calculate_severity
        result = _calculate_severity("competitor_price_change", None)
        assert result == "warning"

    def test_visits_spike_info(self):
        from app.alertas.service import _calculate_severity
        result = _calculate_severity("visits_spike", None)
        assert result == "info"

    def test_conversion_improved_info(self):
        from app.alertas.service import _calculate_severity
        result = _calculate_severity("conversion_improved", None)
        assert result == "info"

    def test_padrao_warning(self):
        """Tipo desconhecido ou padrão → warning."""
        from app.alertas.service import _calculate_severity
        result = _calculate_severity("conversion_below", Decimal("2"))
        assert result == "warning"

    def test_threshold_none_nao_quebra(self):
        from app.alertas.service import _calculate_severity
        result = _calculate_severity("stock_below", None)
        # threshold=None → float(None) não funciona, mas o código usa 0
        assert result in ("critical", "warning", "info")


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 2: CRUD AlertConfig — SQLite
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreateAlertConfig:
    """Testa create_alert_config."""

    @pytest.mark.asyncio
    async def test_cria_alerta_basico(self, db):
        from app.alertas.service import create_alert_config

        user = _make_user()
        db.add(user)
        await db.flush()

        payload = await _make_alert_payload(db, user.id, alert_type="competitor_price_change")
        result = await create_alert_config(db, user.id, payload)

        assert result.id is not None
        assert result.user_id == user.id
        assert result.alert_type == "competitor_price_change"
        assert result.is_active is True

    @pytest.mark.asyncio
    async def test_severidade_automatica(self, db):
        """Sem severity no payload → severidade calculada automaticamente."""
        from app.alertas.service import create_alert_config

        user = _make_user()
        db.add(user)
        await db.flush()

        payload = await _make_alert_payload(db, user.id, alert_type="visits_spike", severity=None)
        result = await create_alert_config(db, user.id, payload)
        assert result.severity == "info"

    @pytest.mark.asyncio
    async def test_severidade_custom_mantida(self, db):
        """Severity fornecida é mantida."""
        from app.alertas.service import create_alert_config

        user = _make_user()
        db.add(user)
        await db.flush()

        payload = await _make_alert_payload(db, user.id, alert_type="visits_spike", severity="critical")
        result = await create_alert_config(db, user.id, payload)
        assert result.severity == "critical"

    @pytest.mark.asyncio
    async def test_listing_inexistente_levanta_404(self, db):
        """listing_id que não pertence ao user → 404."""
        from fastapi import HTTPException
        from app.alertas.service import create_alert_config
        from app.alertas.schemas import AlertConfigCreate

        user = _make_user()
        db.add(user)
        await db.flush()

        payload = AlertConfigCreate(
            alert_type="competitor_price_change",
            listing_id=_uid(),  # não existe
            channel="email",
        )
        with pytest.raises(HTTPException) as exc:
            await create_alert_config(db, user.id, payload)
        assert exc.value.status_code == 404


class TestListAlertConfigs:
    """Testa list_alert_configs."""

    @pytest.mark.asyncio
    async def test_sem_alertas_retorna_vazia(self, db):
        from app.alertas.service import list_alert_configs

        user = _make_user()
        db.add(user)
        await db.flush()

        result = await list_alert_configs(db, user.id)
        assert result == []

    @pytest.mark.asyncio
    async def test_lista_alertas_do_usuario(self, db):
        from app.alertas.service import create_alert_config, list_alert_configs

        user = _make_user()
        db.add(user)
        await db.flush()

        await create_alert_config(db, user.id, await _make_alert_payload(db, user.id))
        await create_alert_config(db, user.id, await _make_alert_payload(db, user.id))

        result = await list_alert_configs(db, user.id)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_filtro_is_active(self, db):
        """is_active=True filtra corretamente."""
        from app.alertas.service import create_alert_config, list_alert_configs

        user = _make_user()
        db.add(user)
        await db.flush()

        # Cria alerta ativo
        a = await create_alert_config(db, user.id, await _make_alert_payload(db, user.id))
        # Cria alerta inativo
        b = await create_alert_config(db, user.id, await _make_alert_payload(db, user.id))
        b.is_active = False
        await db.flush()

        result_active = await list_alert_configs(db, user.id, is_active=True)
        result_inactive = await list_alert_configs(db, user.id, is_active=False)

        assert len(result_active) == 1
        assert len(result_inactive) == 1

    @pytest.mark.asyncio
    async def test_isolamento_entre_usuarios(self, db):
        from app.alertas.service import create_alert_config, list_alert_configs

        user1 = _make_user()
        user2 = _make_user()
        db.add_all([user1, user2])
        await db.flush()

        await create_alert_config(db, user1.id, await _make_alert_payload(db, user1.id))

        r1 = await list_alert_configs(db, user1.id)
        r2 = await list_alert_configs(db, user2.id)

        assert len(r1) == 1
        assert len(r2) == 0


class TestGetAlertConfig:
    """Testa get_alert_config."""

    @pytest.mark.asyncio
    async def test_get_existente(self, db):
        from app.alertas.service import create_alert_config, get_alert_config

        user = _make_user()
        db.add(user)
        await db.flush()

        created = await create_alert_config(db, user.id, await _make_alert_payload(db, user.id))
        result = await get_alert_config(db, user.id, created.id)
        assert result.id == created.id

    @pytest.mark.asyncio
    async def test_get_inexistente_levanta_404(self, db):
        from fastapi import HTTPException
        from app.alertas.service import get_alert_config

        user = _make_user()
        db.add(user)
        await db.flush()

        with pytest.raises(HTTPException) as exc:
            await get_alert_config(db, user.id, _uid())
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_outro_usuario_levanta_404(self, db):
        from fastapi import HTTPException
        from app.alertas.service import create_alert_config, get_alert_config

        user1 = _make_user()
        user2 = _make_user()
        db.add_all([user1, user2])
        await db.flush()

        created = await create_alert_config(db, user1.id, await _make_alert_payload(db, user1.id))

        with pytest.raises(HTTPException) as exc:
            await get_alert_config(db, user2.id, created.id)
        assert exc.value.status_code == 404


class TestUpdateAlertConfig:
    """Testa update_alert_config."""

    @pytest.mark.asyncio
    async def test_atualiza_threshold(self, db):
        from app.alertas.service import create_alert_config, update_alert_config
        from app.alertas.schemas import AlertConfigUpdate

        user = _make_user()
        db.add(user)
        await db.flush()

        created = await create_alert_config(
            db, user.id,
            await _make_alert_payload(db, user.id, alert_type="competitor_price_change")
        )
        updated = await update_alert_config(
            db, user.id, created.id,
            AlertConfigUpdate(threshold=Decimal("10.00"))
        )
        assert updated.threshold == Decimal("10.00")

    @pytest.mark.asyncio
    async def test_atualiza_is_active(self, db):
        from app.alertas.service import create_alert_config, update_alert_config
        from app.alertas.schemas import AlertConfigUpdate

        user = _make_user()
        db.add(user)
        await db.flush()

        created = await create_alert_config(db, user.id, await _make_alert_payload(db, user.id))
        updated = await update_alert_config(
            db, user.id, created.id,
            AlertConfigUpdate(is_active=False)
        )
        assert updated.is_active is False

    @pytest.mark.asyncio
    async def test_update_inexistente_levanta_404(self, db):
        from fastapi import HTTPException
        from app.alertas.service import update_alert_config
        from app.alertas.schemas import AlertConfigUpdate

        user = _make_user()
        db.add(user)
        await db.flush()

        with pytest.raises(HTTPException) as exc:
            await update_alert_config(
                db, user.id, _uid(),
                AlertConfigUpdate(is_active=False)
            )
        assert exc.value.status_code == 404


class TestDeactivateAlertConfig:
    """Testa deactivate_alert_config."""

    @pytest.mark.asyncio
    async def test_desativa_alerta(self, db):
        from app.alertas.service import create_alert_config, deactivate_alert_config, get_alert_config

        user = _make_user()
        db.add(user)
        await db.flush()

        created = await create_alert_config(db, user.id, await _make_alert_payload(db, user.id))
        assert created.is_active is True

        await deactivate_alert_config(db, user.id, created.id)

        # Verifica que foi desativado
        alert = await get_alert_config(db, user.id, created.id)
        assert alert.is_active is False

    @pytest.mark.asyncio
    async def test_desativar_inexistente_levanta_404(self, db):
        from fastapi import HTTPException
        from app.alertas.service import deactivate_alert_config

        user = _make_user()
        db.add(user)
        await db.flush()

        with pytest.raises(HTTPException) as exc:
            await deactivate_alert_config(db, user.id, _uid())
        assert exc.value.status_code == 404


class TestListAlertEvents:
    """Testa list_alert_events e list_events_by_alert."""

    @pytest.mark.asyncio
    async def test_sem_eventos_retorna_vazia(self, db):
        from app.alertas.service import list_alert_events

        user = _make_user()
        db.add(user)
        await db.flush()

        result = await list_alert_events(db, user.id)
        assert result == []

    @pytest.mark.asyncio
    async def test_events_by_alert_sem_eventos(self, db):
        from app.alertas.service import create_alert_config, list_events_by_alert

        user = _make_user()
        db.add(user)
        await db.flush()

        alert = await create_alert_config(db, user.id, await _make_alert_payload(db, user.id))
        result = await list_events_by_alert(db, user.id, alert.id)
        assert result == []
