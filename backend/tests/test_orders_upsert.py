"""Testes do upsert seguro de pedidos (E11) — _upsert_order.

Garante: (1) cria quando novo; (2) atualiza seletivamente quando existe (status/
financeiro mudam, fatos imutaveis NAO); (3) gravar o mesmo ml_order_id 2x nao gera
IntegrityError e nao perde o pedido (a race que o codigo antigo perdia).
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.jobs.tasks_orders import _upsert_order
from app.vendas.models import Order

_ACCOUNT_ID = uuid.uuid4()


def _vals(ml_order_id="ML-1", **over):
    v = {
        "ml_order_id": ml_order_id,
        "ml_account_id": _ACCOUNT_ID,
        "listing_id": None,
        "mlb_id": "MLB123",
        "item_title": "Produto X",
        "buyer_nickname": "comprador",
        "quantity": 2,
        "unit_price": Decimal("50.00"),
        "total_amount": Decimal("100.00"),
        "sale_fee": Decimal("11.00"),
        "shipping_cost": Decimal("0.00"),
        "net_amount": Decimal("89.00"),
        "payment_status": "approved",
        "shipping_status": "pending",
        "order_date": datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc),
        "payment_date": None,
        "delivery_date": None,
    }
    v.update(over)
    return v


@pytest.mark.asyncio
async def test_cria_quando_novo(db):
    outcome = await _upsert_order(db, _vals("ML-NEW"))
    await db.flush()
    assert outcome == "created"
    row = (await db.execute(Order.__table__.select().where(Order.ml_order_id == "ML-NEW"))).fetchone()
    assert row is not None


@pytest.mark.asyncio
async def test_atualiza_seletivo_preserva_fatos(db):
    await _upsert_order(db, _vals("ML-UP", quantity=2, total_amount=Decimal("100.00"),
                                  shipping_status="pending", sale_fee=Decimal("11.00")))
    await db.flush()
    # Reprocessa o MESMO pedido com envio fechado + frete/taxa novos
    outcome = await _upsert_order(db, _vals("ML-UP", quantity=999, total_amount=Decimal("999.00"),
                                            shipping_status="delivered", sale_fee=Decimal("16.00"),
                                            net_amount=Decimal("84.00")))
    await db.flush()
    assert outcome == "updated"
    o = (await db.execute(Order.__table__.select().where(Order.ml_order_id == "ML-UP"))).fetchone()
    # status/financeiro ATUALIZAM
    assert o.shipping_status == "delivered"
    assert float(o.sale_fee) == 16.00
    assert float(o.net_amount) == 84.00
    # fatos imutaveis PRESERVAM (quantity/total do 1o insert, nao 999)
    assert o.quantity == 2
    assert float(o.total_amount) == 100.00


@pytest.mark.asyncio
async def test_mesmo_pedido_duas_vezes_nao_perde(db):
    """A race que o codigo antigo perdia: 2o upsert vira update, sem IntegrityError."""
    o1 = await _upsert_order(db, _vals("ML-RACE"))
    await db.flush()
    o2 = await _upsert_order(db, _vals("ML-RACE", shipping_status="shipped"))
    await db.flush()
    assert o1 == "created"
    assert o2 == "updated"
    rows = (await db.execute(Order.__table__.select().where(Order.ml_order_id == "ML-RACE"))).fetchall()
    assert len(rows) == 1  # 1 pedido, nao duplicado nem perdido
    assert rows[0].shipping_status == "shipped"
