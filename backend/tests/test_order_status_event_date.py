"""Data-do-evento de pós-venda no Order (líquido fiel ao painel, liq-1/liq-2).

`status_event_date` = data em que o pedido virou cancelled/refunded, de
`payments[].date_last_modified` (validado no MCP oficial). Usada p/ contabilizar
cancelados/devoluções pela DATA DO EVENTO, não pela data da venda.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.jobs.tasks_orders import _extract_status_event_date, _upsert_order
from app.vendas.models import Order

_ACC = uuid.uuid4()


def _pay(status, dlm):
    return {"status": status, "date_last_modified": dlm, "date_approved": "2026-07-10T10:00:00.000-03:00"}


def test_helper_refunded_usa_date_last_modified():
    payments = [_pay("refunded", "2026-07-14T16:30:00.000-03:00")]
    d = _extract_status_event_date(payments, "refunded")
    # 16:30 BRT (-03:00) == 19:30 UTC — usa date_last_modified, não date_approved (10:00)
    assert d is not None
    assert d.astimezone(timezone.utc).hour == 19 and d.day == 14


def test_helper_cancelled_usa_date_last_modified():
    payments = [_pay("cancelled", "2026-07-12T09:00:00.000-03:00")]
    d = _extract_status_event_date(payments, "cancelled")
    assert d is not None and d.year == 2026 and d.month == 7 and d.day == 12


def test_helper_approved_retorna_none():
    payments = [_pay("approved", "2026-07-10T10:00:00.000-03:00")]
    assert _extract_status_event_date(payments, "approved") is None


def test_helper_sem_date_last_modified_retorna_none():
    assert _extract_status_event_date([{"status": "refunded"}], "refunded") is None
    assert _extract_status_event_date([], "refunded") is None


def _vals(ml_order_id="ML-EVT", **over):
    v = {
        "ml_order_id": ml_order_id, "ml_account_id": _ACC, "listing_id": None,
        "mlb_id": "MLB1", "item_title": "X", "buyer_nickname": "c", "quantity": 1,
        "unit_price": Decimal("100"), "total_amount": Decimal("100"),
        "sale_fee": Decimal("11"), "shipping_cost": Decimal("0"), "net_amount": Decimal("89"),
        "payment_status": "approved", "shipping_status": "pending",
        "order_date": datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
        "payment_date": None, "delivery_date": None, "status_event_date": None,
    }
    v.update(over)
    return v


@pytest.mark.asyncio
async def test_upsert_seta_event_date_quando_vira_refunded(db):
    """Venda approved sem event_date; re-sync marca refunded + data → grava a data."""
    await _upsert_order(db, _vals("ML-R", payment_status="approved", status_event_date=None))
    await db.flush()
    evt = datetime(2026, 7, 14, 16, 30, tzinfo=timezone.utc)
    await _upsert_order(db, _vals("ML-R", payment_status="refunded", status_event_date=evt))
    await db.flush()
    o = (await db.execute(Order.__table__.select().where(Order.ml_order_id == "ML-R"))).fetchone()
    assert o.payment_status == "refunded"
    # SQLite de teste não preserva tzinfo — comparar por componentes (valor está correto)
    assert o.status_event_date.replace(tzinfo=None) == evt.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_upsert_nao_limpa_event_date_em_resync_sem_dado(db):
    """Uma vez setada, a data do evento não é apagada por um re-sync sem o dado."""
    evt = datetime(2026, 7, 14, 16, 30, tzinfo=timezone.utc)
    await _upsert_order(db, _vals("ML-K", payment_status="refunded", status_event_date=evt))
    await db.flush()
    await _upsert_order(db, _vals("ML-K", payment_status="refunded", status_event_date=None))
    await db.flush()
    o = (await db.execute(Order.__table__.select().where(Order.ml_order_id == "ML-K"))).fetchone()
    assert o.status_event_date.replace(tzinfo=None) == evt.replace(tzinfo=None)  # preservada
