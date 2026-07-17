"""
Testes da feature flag METRICS_SOURCE (Plano Definitivo, Bloco A / E119).

A flag controla como `metrics.py` reconcilia vendas/pedidos/receita entre o
snapshot (cópia derivada, pode inflar com dado legado) e a tabela Order (fato
aditivo, espelho do painel do ML).

- "legacy_max" (default): max(snapshot, order) — NÃO-aditivo. Reproduz o bug
  histórico de SOBRECONTAGEM (app > ML) quando o snapshot está inflado.
- "order_additive": Order é a fonte única — corrige a sobrecontagem.

A virada do default (E52) é a etapa mais sensível do plano e só ocorre após
backup/staging/modo-sombra. Este teste garante que o MECANISMO da flag funciona
antes disso, sem mexer no default.
"""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.auth.models import MLAccount, User
from app.core.config import settings
from app.vendas.metrics import aggregate_metrics
from app.vendas.models import Listing, ListingSnapshot, Order

from tests.test_metrics_characterization import _brt_noon


async def _setup(db):
    user = User(id=uuid4(), email=f"{uuid4()}@t.com", hashed_password="x")
    db.add(user)
    ml = MLAccount(
        id=uuid4(), user_id=user.id, ml_user_id="1",
        nickname="t", access_token="x", refresh_token="y",
    )
    db.add(ml)
    await db.flush()
    listing = Listing(
        id=uuid4(), user_id=user.id, ml_account_id=ml.id,
        mlb_id="MLB1", title="MLB1", price=Decimal("100"), status="active",
    )
    db.add(listing)
    await db.flush()
    return user, ml, listing


def _snap_inflado(listing, d):
    """Snapshot com 10 vendas/R$1000 — dado legado INFLADO acima da realidade."""
    return ListingSnapshot(
        id=uuid4(), listing_id=listing.id, price=Decimal("100"),
        visits=200, sales_today=10, stock=5, orders_count=10,
        revenue=Decimal("1000"), cancelled_orders=0, cancelled_revenue=Decimal("0"),
        returns_count=0, returns_revenue=Decimal("0"), captured_at=_brt_noon(d),
    )


def _orders_reais(listing, ml, d, n=6):
    """n orders reais (a verdade do painel): n vendas, R$100 cada."""
    return [
        Order(
            id=uuid4(), ml_order_id=str(uuid4()), ml_account_id=ml.id,
            listing_id=listing.id, mlb_id=listing.mlb_id, quantity=1,
            unit_price=Decimal("100"), total_amount=Decimal("100"),
            payment_status="approved", order_date=_brt_noon(d),
        )
        for _ in range(n)
    ]


@pytest.mark.asyncio
async def test_legacy_max_mantem_snapshot_inflado(db, monkeypatch):
    """DEFAULT (legacy_max): snapshot inflado (10) > order real (6) → vence o 10.

    Documenta o BUG que a Fase 4 resolve: o app mostra MAIS venda que o painel.
    """
    monkeypatch.setattr(settings, "metrics_source", "legacy_max")
    user, ml, listing = await _setup(db)
    dia = date(2026, 6, 10)
    db.add(_snap_inflado(listing, dia))
    db.add_all(_orders_reais(listing, ml, dia, n=6))
    await db.commit()

    kpi = await aggregate_metrics(db, [listing.id], dia, dia)

    # max(snapshot=10, order=6) = 10 — a sobrecontagem histórica.
    assert kpi["vendas"] == 10
    assert kpi["pedidos"] == 10
    assert kpi["receita_total"] == 1000.0


@pytest.mark.asyncio
async def test_order_additive_corrige_sobrecontagem(db, monkeypatch):
    """order_additive: Order é a fonte única → 6 vendas reais, não 10 do snapshot."""
    monkeypatch.setattr(settings, "metrics_source", "order_additive")
    user, ml, listing = await _setup(db)
    dia = date(2026, 6, 10)
    db.add(_snap_inflado(listing, dia))
    db.add_all(_orders_reais(listing, ml, dia, n=6))
    await db.commit()

    kpi = await aggregate_metrics(db, [listing.id], dia, dia)

    # Order manda: 6 vendas, 6 pedidos, R$600 — espelha o painel do ML.
    assert kpi["vendas"] == 6
    assert kpi["pedidos"] == 6
    assert kpi["receita_total"] == 600.0
    assert kpi["receita"] == 600.0


@pytest.mark.asyncio
async def test_order_additive_brutas_e_liquido_evento_mesmo_dia(db, monkeypatch):
    """liq-4: brutas incluem cancel/devol; líquido desconta por data-EVENTO.

    5 approved + 2 cancelled + 1 refunded no MESMO dia (venda E evento no dia):
      - brutas: vendas/pedidos = 8, receita = 800 (o painel não desconta do bruto)
      - canceladas = 2 (R$200), devolvidas = 1 (R$100) — evento no dia
      - líquido = 800 − 200 − 100 = 500
    """
    monkeypatch.setattr(settings, "metrics_source", "order_additive")
    user, ml, listing = await _setup(db)
    dia = date(2026, 6, 10)
    evt = _brt_noon(dia)  # evento no mesmo dia da venda

    db.add(_snap_inflado(listing, dia))
    db.add_all(_orders_reais(listing, ml, dia, n=5))  # 5 approved
    for st in ("cancelled", "cancelled", "refunded"):
        db.add(Order(
            id=uuid4(), ml_order_id=str(uuid4()), ml_account_id=ml.id,
            listing_id=listing.id, mlb_id=listing.mlb_id, quantity=1,
            unit_price=Decimal("100"), total_amount=Decimal("100"),
            payment_status=st, order_date=evt, status_event_date=evt,
        ))
    await db.commit()

    kpi = await aggregate_metrics(db, [listing.id], dia, dia)

    assert kpi["vendas"] == 8            # brutas: inclui os 2 cancelados + 1 devolvido
    assert kpi["pedidos"] == 8
    assert kpi["receita_total"] == 800.0
    assert kpi["cancelamentos_valor"] == 200.0
    assert kpi["devolucoes_qtd"] == 1
    assert kpi["devolucoes_valor"] == 100.0
    assert kpi["vendas_concluidas"] == 500.0  # 800 − 200 − 100 (líquido)


@pytest.mark.asyncio
async def test_order_additive_evento_em_outro_dia_nao_desconta_na_venda(db, monkeypatch):
    """liq-4 (o ponto central): reembolso lançado no DIA DO EVENTO, não da venda.

    Venda dia 10, reembolso processado dia 12:
      - dia 10: brutas inclui a venda; devolvidas=0 (evento é dia 12) → líquido = bruto
      - dia 12: brutas=0 (nada vendido); devolvidas=1 → líquido negativo (−100)
    Espelha exatamente o painel do ML.
    """
    monkeypatch.setattr(settings, "metrics_source", "order_additive")
    user, ml, listing = await _setup(db)
    d_venda, d_evento = date(2026, 6, 10), date(2026, 6, 12)

    db.add(Order(
        id=uuid4(), ml_order_id=str(uuid4()), ml_account_id=ml.id,
        listing_id=listing.id, mlb_id=listing.mlb_id, quantity=1,
        unit_price=Decimal("100"), total_amount=Decimal("100"),
        payment_status="refunded",
        order_date=_brt_noon(d_venda), status_event_date=_brt_noon(d_evento),
    ))
    await db.commit()

    # dia da venda: conta no bruto, NÃO desconta (evento é depois)
    dia10 = await aggregate_metrics(db, [listing.id], d_venda, d_venda)
    assert dia10["receita_total"] == 100.0
    assert dia10["devolucoes_valor"] == 0.0
    assert dia10["vendas_concluidas"] == 100.0

    # dia do evento: nada vendido, mas a devolução é lançada aqui → líquido negativo
    dia12 = await aggregate_metrics(db, [listing.id], d_evento, d_evento)
    assert dia12["receita_total"] == 0.0
    assert dia12["devolucoes_valor"] == 100.0
    assert dia12["vendas_concluidas"] == -100.0


@pytest.mark.asyncio
async def test_order_additive_fallback_sem_orders(db, monkeypatch):
    """order_additive: janela sem NENHUMA order mas com snapshot (dado legado) →
    cai no snapshot (não zera o histórico)."""
    monkeypatch.setattr(settings, "metrics_source", "order_additive")
    user, ml, listing = await _setup(db)
    dia = date(2026, 6, 10)
    db.add(_snap_inflado(listing, dia))  # snapshot, sem orders
    await db.commit()

    kpi = await aggregate_metrics(db, [listing.id], dia, dia)

    # Sem order → fallback ao snapshot (10 vendas legadas).
    assert kpi["vendas"] == 10
    assert kpi["receita"] == 1000.0


@pytest.mark.asyncio
async def test_order_additive_e_aditivo(db, monkeypatch):
    """E54: Σ(cada dia) == janela inteira — a propriedade que o max() quebrava.

    3 dias com nº de orders diferente (3, 5, 2). No order_additive, somar os KPIs
    dia a dia tem que dar EXATAMENTE o KPI da janela [d1, d3]. Snapshots inflados
    de propósito para provar que é o Order (aditivo) que manda, não o snapshot.
    """
    monkeypatch.setattr(settings, "metrics_source", "order_additive")
    user, ml, listing = await _setup(db)
    d1, d2, d3 = date(2026, 6, 10), date(2026, 6, 11), date(2026, 6, 12)

    for d, n in ((d1, 3), (d2, 5), (d3, 2)):
        db.add(_snap_inflado(listing, d))          # snapshot inflado (10) em cada dia
        db.add_all(_orders_reais(listing, ml, d, n=n))  # orders reais do dia
    await db.commit()

    por_dia = [await aggregate_metrics(db, [listing.id], d, d) for d in (d1, d2, d3)]
    janela = await aggregate_metrics(db, [listing.id], d1, d3)

    for campo in ("vendas", "pedidos", "receita_total"):
        assert sum(k[campo] for k in por_dia) == janela[campo], campo
    # Concretamente: 3+5+2 = 10 orders reais, não 30 do snapshot inflado.
    assert janela["pedidos"] == 10
    assert janela["receita_total"] == 1000.0
