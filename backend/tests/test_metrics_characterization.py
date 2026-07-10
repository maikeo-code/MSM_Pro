"""
Testes de CARACTERIZAÇÃO (golden master) da fonte única de métricas.

Diferença para test_metrics_parity.py: lá o foco é *paridade entre rotas* e
casos de borda isolados. Aqui a gente TRAVA O DICIONÁRIO KPI INTEIRO de cenários
realistas. Qualquer mudança silenciosa em QUALQUER número derivado — preço médio,
vendas_concluidas, taxa de cancelamento, médias por dia, valor de estoque — quebra
o teste na hora, antes de ir pro ar.

É a rede de segurança contra o "conserta um, quebra outro" descrito no
Acordo de Trabalho (msm_pro/CLAUDE.md). Os valores esperados abaixo foram
calculados à mão a partir da lógica de app/vendas/metrics.py. Se você mudou a
`metrics.py` DE PROPÓSITO e este teste quebrou: atualize os valores esperados no
MESMO commit, justificando a mudança de número no corpo do commit. Se você NÃO
pretendia mudar número nenhum: você acabou de causar uma regressão — reverta.
"""
from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.auth.models import MLAccount, User
from app.vendas.metrics import BRT, aggregate_metrics
from app.vendas.models import Listing, ListingSnapshot, Order


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


def _snap(
    listing, d: date, *, visits=0, sales=0, price="100", stock=0, orders=0,
    revenue=None, cancelled_orders=0, cancelled_revenue=0,
    returns_count=0, returns_revenue=0,
):
    """Snapshot com TODOS os campos que a agregação consome — para golden master."""
    return ListingSnapshot(
        id=uuid4(), listing_id=listing.id, price=Decimal(price),
        visits=visits, sales_today=sales, stock=stock, orders_count=orders,
        revenue=None if revenue is None else Decimal(revenue),
        cancelled_orders=cancelled_orders,
        cancelled_revenue=Decimal(cancelled_revenue),
        returns_count=returns_count,
        returns_revenue=Decimal(returns_revenue),
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
async def test_golden_dia_unico_com_cancelamento_e_devolucao(db):
    """Golden master de UM dia, 2 anúncios, com cancelamento e devolução.

    Fonte = snapshots (não há Order que reconcilie para cima). Trava todos os
    campos financeiros derivados: preço médio, taxa de cancelamento,
    vendas_concluidas, valor de estoque e médias por dia.
    """
    user, ml = await _setup_user(db)
    l1 = _listing(user, ml, "MLB1")
    l2 = _listing(user, ml, "MLB2")
    db.add_all([l1, l2])
    await db.flush()

    dia = date(2026, 6, 8)
    db.add_all([
        _snap(
            l1, dia, visits=200, sales=4, price="100", stock=10, orders=3,
            revenue="400", cancelled_orders=1, cancelled_revenue="100",
            returns_count=1, returns_revenue="100",
        ),
        _snap(l2, dia, visits=100, sales=2, price="50", stock=4, orders=2, revenue="100"),
    ])
    await db.commit()

    kpi = await aggregate_metrics(db, [l1.id, l2.id], dia, dia)

    assert kpi == {
        "vendas": 6,
        "visitas": 300,
        "conversao": 2.0,
        "anuncios": 2,
        "valor_estoque": 1200.0,
        "receita": 500.0,
        "pedidos": 5,
        "receita_total": 500.0,
        "preco_medio": 83.33,
        "taxa_cancelamento": 16.67,
        "preco_medio_por_venda": 100.0,
        "vendas_concluidas": 300.0,
        "cancelamentos_valor": 100.0,
        "devolucoes_valor": 100.0,
        "devolucoes_qtd": 1,
        "dias_no_periodo": 1,
        "vendas_media_dia": 6.0,
        "visitas_media_dia": 300.0,
        "pedidos_media_dia": 5.0,
        "receita_media_dia": 500.0,
    }


@pytest.mark.asyncio
async def test_golden_intervalo_com_reconciliacao_orders(db):
    """Golden master de intervalo de 2 dias com Orders vencendo os snapshots.

    Snapshots subnotificam (3 vendas / 3 pedidos); Orders reais somam 6 unidades
    em 4 pedidos e R$ 600 — a reconciliação puxa tudo para cima. Trava esse
    caminho por inteiro, inclusive as médias por dia sobre o valor reconciliado.
    """
    user, ml = await _setup_user(db)
    l1 = _listing(user, ml, "MLB1")
    db.add(l1)
    await db.flush()

    d1, d2 = date(2026, 6, 7), date(2026, 6, 8)
    db.add_all([
        _snap(l1, d1, visits=20, sales=1, price="100", stock=5, orders=1),
        _snap(l1, d2, visits=50, sales=2, price="100", stock=3, orders=2),
        _order(l1, ml, d1, qty=3, amount="300"),
        _order(l1, ml, d1, qty=1, amount="100"),
        _order(l1, ml, d2, qty=1, amount="100"),
        _order(l1, ml, d2, qty=1, amount="100"),
    ])
    await db.commit()

    kpi = await aggregate_metrics(db, [l1.id], d1, d2)

    assert kpi == {
        "vendas": 6,
        "visitas": 70,
        "conversao": 8.57,
        "anuncios": 1,
        "valor_estoque": 300.0,
        "receita": 600.0,
        "pedidos": 4,
        "receita_total": 600.0,
        "preco_medio": 100.0,
        "taxa_cancelamento": 0.0,
        "preco_medio_por_venda": 150.0,
        "vendas_concluidas": 600.0,
        "cancelamentos_valor": 0.0,
        "devolucoes_valor": 0.0,
        "devolucoes_qtd": 0,
        "dias_no_periodo": 2,
        "vendas_media_dia": 3.0,
        "visitas_media_dia": 35.0,
        "pedidos_media_dia": 2.0,
        "receita_media_dia": 300.0,
    }


@pytest.mark.asyncio
async def test_golden_sem_listings_retorna_metricas_zeradas(db):
    """Sem anúncios no universo, o payload é o zero canônico (mesmas chaves)."""
    dia = date(2026, 6, 8)
    kpi = await aggregate_metrics(db, [], dia, dia, total_anuncios=7)

    assert kpi == {
        "vendas": 0,
        "visitas": 0,
        "conversao": 0.0,
        "anuncios": 7,
        "valor_estoque": 0.0,
        "receita": 0.0,
        "pedidos": 0,
        "receita_total": 0.0,
        "preco_medio": 0.0,
        "taxa_cancelamento": 0.0,
        "preco_medio_por_venda": 0.0,
        "vendas_concluidas": 0.0,
        "cancelamentos_valor": 0.0,
        "devolucoes_valor": 0.0,
        "devolucoes_qtd": 0,
        "dias_no_periodo": 1,
        "vendas_media_dia": 0.0,
        "visitas_media_dia": 0.0,
        "pedidos_media_dia": 0.0,
        "receita_media_dia": 0.0,
    }
