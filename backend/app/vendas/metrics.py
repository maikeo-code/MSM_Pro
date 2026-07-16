"""
Fonte única de agregação de métricas de vendas (Fase 2 do plano anti-regressão).

Toda rota que mostra vendas/visitas/receita por período DEVE consumir
`aggregate_metrics` — nunca reimplementar a agregação. É isso que garante que
`/kpi/summary`, `/kpi/daily` e `/kpi/compare` mostrem o mesmo número para o
mesmo período (testes de paridade em tests/test_metrics_parity.py).

Regras canônicas:
- Dia = `snapshot_day` (data BRT), nunca `cast(captured_at, Date)` (data UTC) —
  a constraint uq_listing_snapshot_day garante no máximo 1 snapshot/dia, mas a
  agregação ainda pega o último `captured_at` por (listing, dia) para ser
  robusta a dados legados anteriores à migration 0033.
- `vendas` = unidades (snapshot.sales_today) reconciliadas com a tabela Order
  (fonte mais confiável quando diverge para cima); `pedidos` = contagem de Order.
- `visits` = visitas DO DIA (incremental). Guarda anti-corrupção: se
  0 < visitas < vendas (impossível), visitas e conversão ficam indisponíveis (0).
- `valor_estoque` = posição pontual: último snapshot de cada listing com
  captured_at até o fim (BRT) de date_to — não é somatório do período.
"""
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.vendas.constants import NON_SALE_PAYMENT_STATUSES
from app.vendas.models import ListingSnapshot, Order

BRT = timezone(timedelta(hours=-3))


async def aggregate_metrics(
    db: AsyncSession,
    listing_ids: list,
    date_from: date,
    date_to: date,
    total_anuncios: int | None = None,
) -> dict:
    """Agrega métricas de vendas no intervalo [date_from, date_to] (dias BRT).

    Dia único = intervalo de 1 dia (date_from == date_to). Retorna o payload
    padrão de KPI usado por summary/daily/compare.

    total_anuncios: se fornecido, usa esse valor para "anuncios" (universo de
    listings ativos), em vez de contar snapshots do intervalo — evita números
    incoerentes quando o sync do dia foi parcial ou ainda não rodou.
    """
    if not listing_ids:
        return _empty_metrics(date_from, date_to, total_anuncios)

    # Último snapshot de cada listing em cada dia (BRT) do intervalo
    latest_per_day = (
        select(
            ListingSnapshot.listing_id,
            ListingSnapshot.snapshot_day,
            func.max(ListingSnapshot.captured_at).label("max_captured_at"),
        )
        .where(
            ListingSnapshot.listing_id.in_(listing_ids),
            ListingSnapshot.snapshot_day >= date_from,
            ListingSnapshot.snapshot_day <= date_to,
        )
        .group_by(ListingSnapshot.listing_id, ListingSnapshot.snapshot_day)
        .subquery()
    )

    result = await db.execute(
        select(
            func.coalesce(func.sum(ListingSnapshot.sales_today), 0).label("vendas"),
            func.coalesce(func.sum(ListingSnapshot.visits), 0).label("visitas"),
            func.count(func.distinct(ListingSnapshot.listing_id)).label("anuncios"),
            func.coalesce(func.sum(ListingSnapshot.price * ListingSnapshot.sales_today), 0).label("receita"),
            func.coalesce(func.sum(ListingSnapshot.orders_count), 0).label("pedidos"),
            func.coalesce(
                func.sum(func.coalesce(ListingSnapshot.revenue, ListingSnapshot.price * ListingSnapshot.sales_today)),
                0,
            ).label("receita_total"),
            func.coalesce(func.sum(ListingSnapshot.cancelled_orders), 0).label("cancelados"),
            func.coalesce(func.sum(ListingSnapshot.cancelled_revenue), 0).label("cancelados_valor"),
            func.coalesce(func.sum(ListingSnapshot.returns_count), 0).label("devolucoes_qtd"),
            func.coalesce(func.sum(ListingSnapshot.returns_revenue), 0).label("devolucoes_valor"),
        )
        .join(
            latest_per_day,
            (ListingSnapshot.listing_id == latest_per_day.c.listing_id)
            & (ListingSnapshot.captured_at == latest_per_day.c.max_captured_at),
        )
        .where(ListingSnapshot.listing_id.in_(listing_ids))
    )
    row = result.fetchone()
    vendas = int(row.vendas) if row else 0
    visitas = int(row.visitas) if row else 0
    pedidos = int(row.pedidos) if row else 0
    receita_snapshot = float(row.receita) if row else 0.0
    receita_total = float(row.receita_total) if row else 0.0
    cancelados = int(row.cancelados) if row else 0
    cancelados_valor = float(row.cancelados_valor) if row else 0.0
    devolucoes_qtd = int(row.devolucoes_qtd) if row else 0
    devolucoes_valor = float(row.devolucoes_valor) if row else 0.0

    # Reconciliação com Orders (backfilled): se a tabela Order tem mais
    # vendas/pedidos que os snapshots (sync parcial, snapshot corrompido),
    # Orders vence — é o dado real do ML.
    range_utc_start = datetime.combine(date_from, time.min, tzinfo=BRT).astimezone(timezone.utc)
    range_utc_end = datetime.combine(date_to, time.max, tzinfo=BRT).astimezone(timezone.utc)

    orders_result = await db.execute(
        select(
            func.coalesce(func.sum(Order.quantity), 0).label("vendas"),
            func.count(Order.id).label("pedidos"),
            func.coalesce(func.sum(Order.total_amount), 0).label("receita_total"),
        ).where(
            Order.listing_id.in_(listing_ids),
            Order.order_date >= range_utc_start,
            Order.order_date <= range_utc_end,
            Order.payment_status.notin_(NON_SALE_PAYMENT_STATUSES),
        )
    )
    ofb = orders_result.fetchone()
    orders_vendas = int(ofb.vendas) if ofb else 0
    orders_pedidos = int(ofb.pedidos) if ofb else 0
    receita_orders = float(ofb.receita_total) if ofb else 0.0

    if settings.metrics_source == "order_additive":
        # E52 — Order é a fonte ADITIVA única de vendas/pedidos/receita. Snapshot
        # permanece só p/ visitas/estoque/preço. Σ(dias) == janela por construção
        # (Order é aditivo; max() não era). Fallback ao snapshot APENAS quando a
        # janela não tem NENHUMA order mas tem snapshots (dado legado pré-backfill).
        if orders_pedidos > 0 or orders_vendas > 0:
            vendas = orders_vendas
            pedidos = orders_pedidos
            receita_total = receita_orders
            receita_final = receita_orders
        else:
            receita_final = receita_snapshot
    else:
        # legacy_max (default) — reconciliação histórica não-aditiva: Orders vence
        # quando conta MAIS que o snapshot. Mantido byte-idêntico ao comportamento
        # anterior à E119 (golden master inalterado).
        if ofb and (orders_vendas > vendas or orders_pedidos > pedidos):
            vendas = max(vendas, orders_vendas)
            pedidos = max(pedidos, orders_pedidos)
            receita_total = max(receita_total, receita_orders)
        receita_final = max(receita_snapshot, receita_orders)

    # Guarda anti-corrupção (ciclo 558): visitas < vendas é impossível —
    # snapshot parcial geraria conversão absurda (ex.: 4400%). Nesse caso
    # visitas/conversão ficam indisponíveis (0) em vez de contaminar o dashboard.
    if vendas > 0 and visitas > 0 and visitas < vendas:
        visitas = 0
        conversao = 0.0
    else:
        conversao = round((vendas / visitas * 100), 2) if visitas > 0 else 0.0

    preco_medio = round(receita_total / vendas, 2) if vendas > 0 else 0.0
    preco_medio_por_venda = round(receita_total / pedidos, 2) if pedidos > 0 else 0.0
    total_pedidos_com_cancelados = pedidos + cancelados
    taxa_cancelamento = (
        round(cancelados / total_pedidos_com_cancelados * 100, 2) if total_pedidos_com_cancelados > 0 else 0.0
    )
    vendas_concluidas = round(receita_total - cancelados_valor - devolucoes_valor, 2)

    # Valor de estoque: posição pontual no fim do intervalo (último snapshot de
    # cada listing até o fim de date_to, sem limite inferior — cobre sync
    # parcial e "Hoje" antes das 06:00 BRT).
    valor_estoque = await _stock_value_at(db, listing_ids, date_to)

    dias_no_periodo = (date_to - date_from).days + 1
    if dias_no_periodo < 1:
        dias_no_periodo = 1

    if total_anuncios is not None:
        anuncios_count = total_anuncios
    else:
        anuncios_count = int(row.anuncios) if row else 0

    return {
        "vendas": vendas,
        "visitas": visitas,
        "conversao": conversao,
        "anuncios": anuncios_count,
        "valor_estoque": valor_estoque,
        "receita": receita_final,
        "pedidos": pedidos,
        "receita_total": receita_total,
        "preco_medio": preco_medio,
        "taxa_cancelamento": taxa_cancelamento,
        "preco_medio_por_venda": preco_medio_por_venda,
        "vendas_concluidas": vendas_concluidas,
        "cancelamentos_valor": cancelados_valor,
        "devolucoes_valor": devolucoes_valor,
        "devolucoes_qtd": devolucoes_qtd,
        "dias_no_periodo": dias_no_periodo,
        "vendas_media_dia": round(vendas / dias_no_periodo, 2),
        "visitas_media_dia": round(visitas / dias_no_periodo, 2),
        "pedidos_media_dia": round(pedidos / dias_no_periodo, 2),
        "receita_media_dia": round(receita_total / dias_no_periodo, 2),
    }


async def _stock_value_at(db: AsyncSession, listing_ids: list, dt: date) -> float:
    """Valor de estoque (price * stock) na posição do fim do dia `dt` (BRT)."""
    dt_end = datetime.combine(dt, time.max, tzinfo=BRT).astimezone(timezone.utc)
    per_listing_latest = (
        select(
            ListingSnapshot.listing_id,
            func.max(ListingSnapshot.captured_at).label("max_captured_at"),
        )
        .where(
            ListingSnapshot.listing_id.in_(listing_ids),
            ListingSnapshot.captured_at <= dt_end,
        )
        .group_by(ListingSnapshot.listing_id)
        .subquery()
    )
    result = await db.execute(
        select(
            func.coalesce(func.sum(ListingSnapshot.price * ListingSnapshot.stock), 0).label("valor_estoque"),
        )
        .join(
            per_listing_latest,
            (ListingSnapshot.listing_id == per_listing_latest.c.listing_id)
            & (ListingSnapshot.captured_at == per_listing_latest.c.max_captured_at),
        )
        .where(ListingSnapshot.listing_id.in_(listing_ids))
    )
    est_row = result.fetchone()
    return float(est_row.valor_estoque) if est_row else 0.0


def _empty_metrics(date_from: date, date_to: date, total_anuncios: int | None) -> dict:
    dias = max((date_to - date_from).days + 1, 1)
    return {
        "vendas": 0,
        "visitas": 0,
        "conversao": 0.0,
        "anuncios": total_anuncios or 0,
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
        "dias_no_periodo": dias,
        "vendas_media_dia": 0.0,
        "visitas_media_dia": 0.0,
        "pedidos_media_dia": 0.0,
        "receita_media_dia": 0.0,
    }
