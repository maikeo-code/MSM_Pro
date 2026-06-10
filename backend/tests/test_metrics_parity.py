"""
Testes de paridade da fonte única de métricas (Fase 2 do plano anti-regressão).

Garantem que TODAS as rotas de KPI mostram o mesmo número para o mesmo
período — é o que impede o ciclo "corrige um, quebra outro":

1. `_kpi_single_day(dt)` ≡ `_kpi_date_range(dt, dt)` (mesma fonte: aggregate_metrics).
2. `/kpi/summary` (ontem) ≡ `/kpi/daily` (D-1) ≡ tabela Order — inclusive com
   anúncio PAUSADO com vendas (era a causa do 107 vs 119 em 08/06).
3. Guarda anti-corrupção: visitas < vendas → visitas/conversão indisponíveis.
"""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.auth.models import MLAccount, User
from app.vendas.metrics import BRT, aggregate_metrics
from app.vendas.models import Listing, ListingSnapshot, Order
from app.vendas.service_kpi import (
    _kpi_date_range,
    _kpi_single_day,
    get_kpi_by_period,
    get_kpi_daily_breakdown,
)


def _brt_noon(d: date) -> datetime:
    """captured_at UTC que cai no dia `d` em BRT (12:00 BRT = 15:00 UTC)."""
    return datetime.combine(d, time(12, 0), tzinfo=BRT).astimezone(timezone.utc)


async def _setup_user(db):
    user = User(id=uuid4(), email=f"{uuid4()}@t.com", hashed_password="x")
    db.add(user)
    ml = MLAccount(
        id=uuid4(), user_id=user.id, ml_user_id="1",
        nickname="t", access_token="x", refresh_token="y",
    )
    db.add(ml)
    await db.flush()
    return user, ml


def _listing(user, ml, mlb, status="active"):
    return Listing(
        id=uuid4(), user_id=user.id, ml_account_id=ml.id,
        mlb_id=mlb, title=mlb, price=Decimal("100"), status=status,
    )


def _snap(listing, d: date, *, visits=0, sales=0, price="100", stock=0, orders=0):
    return ListingSnapshot(
        id=uuid4(), listing_id=listing.id, price=Decimal(price),
        visits=visits, sales_today=sales, stock=stock, orders_count=orders,
        captured_at=_brt_noon(d),
    )


def _order(listing, ml, d: date, *, qty=1, amount="100", status="approved"):
    return Order(
        id=uuid4(), ml_order_id=str(uuid4()), ml_account_id=ml.id,
        listing_id=listing.id, mlb_id=listing.mlb_id, quantity=qty,
        unit_price=Decimal(amount), total_amount=Decimal(amount),
        payment_status=status, order_date=_brt_noon(d),
    )


@pytest.mark.asyncio
async def test_single_day_igual_date_range_de_um_dia(db):
    """As duas funções históricas são a MESMA agregação para o mesmo dia."""
    user, ml = await _setup_user(db)
    l1 = _listing(user, ml, "MLB1")
    l2 = _listing(user, ml, "MLB2")
    db.add_all([l1, l2])
    await db.flush()

    dia = date(2026, 6, 8)
    db.add_all([
        _snap(l1, dia, visits=50, sales=3, price="100", stock=10, orders=2),
        _snap(l2, dia, visits=30, sales=1, price="200", stock=5, orders=1),
        _order(l1, ml, dia, qty=3, amount="300"),
        _order(l2, ml, dia, qty=1, amount="200"),
    ])
    await db.commit()

    ids = [l1.id, l2.id]
    single = await _kpi_single_day(db, ids, dia)
    range_ = await _kpi_date_range(db, ids, dia, dia)

    assert single == range_


@pytest.mark.asyncio
async def test_summary_e_daily_mostram_o_mesmo_dia_igual(db):
    """`/kpi/summary` (ontem) e `/kpi/daily` (D-1) batem entre si e com Order,
    mesmo com vendas em anúncio pausado (regressão 107 vs 119 de 08/06)."""
    user, ml = await _setup_user(db)
    ativo = _listing(user, ml, "MLB1", status="active")
    pausado = _listing(user, ml, "MLB2", status="paused")
    db.add_all([ativo, pausado])
    await db.flush()

    ontem = datetime.now(BRT).date() - timedelta(days=1)
    db.add_all([
        _snap(ativo, ontem, visits=100, sales=2, price="100", orders=2),
        _snap(pausado, ontem, visits=40, sales=1, price="50", orders=1),
        _order(ativo, ml, ontem, qty=2, amount="200"),
        _order(pausado, ml, ontem, qty=1, amount="50"),
    ])
    await db.commit()

    summary = await get_kpi_by_period(db, user.id)
    daily = await get_kpi_daily_breakdown(db, user.id, days=7)
    d1 = next(d for d in daily["days"] if d["date"] == ontem.isoformat())

    # paridade entre rotas
    assert summary["ontem"]["vendas"] == d1["vendas"]
    assert summary["ontem"]["visitas"] == d1["visitas"]
    assert summary["ontem"]["pedidos"] == d1["pedidos"]
    assert summary["ontem"]["receita_total"] == d1["receita_total"]

    # coerência com a tabela Order (fonte da verdade): 3 unidades, 3 pedidos
    assert summary["ontem"]["vendas"] == 3
    assert summary["ontem"]["pedidos"] == 3
    # visitas do pausado também contam (universo único)
    assert summary["ontem"]["visitas"] == 140
    # card "Anuncios" continua mostrando só os ativos
    assert summary["ontem"]["anuncios"] == 1


@pytest.mark.asyncio
async def test_orders_vence_quando_snapshot_subnotifica(db):
    """Snapshot com menos vendas que Order → Orders reconcilia para cima."""
    user, ml = await _setup_user(db)
    l1 = _listing(user, ml, "MLB1")
    db.add(l1)
    await db.flush()

    dia = date(2026, 6, 8)
    db.add_all([
        _snap(l1, dia, visits=100, sales=1, price="100", orders=1),
        _order(l1, ml, dia, qty=5, amount="500"),
    ])
    await db.commit()

    kpi = await aggregate_metrics(db, [l1.id], dia, dia)
    assert kpi["vendas"] == 5
    assert kpi["pedidos"] == 1
    assert kpi["receita_total"] == 500.0
    # visitas plausíveis (>= vendas) são preservadas
    assert kpi["visitas"] == 100


@pytest.mark.asyncio
async def test_guarda_anti_corrupcao_visitas_menor_que_vendas(db):
    """visitas < vendas é impossível → visitas/conversão ficam indisponíveis."""
    user, ml = await _setup_user(db)
    l1 = _listing(user, ml, "MLB1")
    db.add(l1)
    await db.flush()

    dia = date(2026, 6, 8)
    db.add_all([
        _snap(l1, dia, visits=2, sales=1),
        _order(l1, ml, dia, qty=44, amount="4400"),
    ])
    await db.commit()

    kpi = await aggregate_metrics(db, [l1.id], dia, dia)
    assert kpi["vendas"] == 44
    assert kpi["visitas"] == 0
    assert kpi["conversao"] == 0.0


@pytest.mark.asyncio
async def test_pedidos_cancelados_ficam_fora(db):
    """Orders cancelled/refunded/rejected não entram na reconciliação."""
    user, ml = await _setup_user(db)
    l1 = _listing(user, ml, "MLB1")
    db.add(l1)
    await db.flush()

    dia = date(2026, 6, 8)
    db.add_all([
        _order(l1, ml, dia, qty=2, amount="200", status="approved"),
        _order(l1, ml, dia, qty=9, amount="900", status="cancelled"),
        _order(l1, ml, dia, qty=9, amount="900", status="refunded"),
    ])
    await db.commit()

    kpi = await aggregate_metrics(db, [l1.id], dia, dia)
    assert kpi["vendas"] == 2
    assert kpi["pedidos"] == 1


@pytest.mark.asyncio
async def test_range_soma_dias_e_calcula_medias(db):
    """Intervalo de N dias soma o último snapshot de cada dia e calcula médias."""
    user, ml = await _setup_user(db)
    l1 = _listing(user, ml, "MLB1")
    db.add(l1)
    await db.flush()

    d1, d2 = date(2026, 6, 7), date(2026, 6, 8)
    db.add_all([
        _snap(l1, d1, visits=10, sales=1, price="100", stock=3),
        _snap(l1, d2, visits=30, sales=2, price="100", stock=2),
    ])
    await db.commit()

    kpi = await aggregate_metrics(db, [l1.id], d1, d2)
    assert kpi["vendas"] == 3
    assert kpi["visitas"] == 40
    assert kpi["dias_no_periodo"] == 2
    assert kpi["visitas_media_dia"] == 20.0
    # estoque = posição pontual do fim do intervalo (2 un × R$100), não soma
    assert kpi["valor_estoque"] == 200.0
