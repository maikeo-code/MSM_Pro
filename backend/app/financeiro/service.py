import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ML_FEES

logger = logging.getLogger(__name__)


def calcular_taxa_ml(listing_type: str, sale_fee_pct: Decimal | None = None) -> Decimal:
    """
    Retorna a taxa percentual do ML para o tipo de anuncio.

    Se sale_fee_pct for fornecido (taxa real obtida via API listing_prices),
    usa esse valor em vez da tabela fixa.

    classico=0.115 (11.5%), premium=0.17 (17%), full=0.17 (17%)
    """
    if sale_fee_pct is not None and sale_fee_pct > 0:
        return sale_fee_pct

    listing_type_lower = listing_type.lower() if listing_type else ""
    if listing_type_lower not in ML_FEES:
        # Fallback: usa taxa default de 16% para listing_type desconhecido
        logger.warning(f"listing_type desconhecido: '{listing_type}' — usando taxa default de 16%")
        return Decimal("0.16")
    return ML_FEES[listing_type_lower]


def calcular_margem(
    preco: Decimal,
    custo: Decimal,
    listing_type: str,
    frete: Decimal = Decimal("0"),
    sale_fee_pct: Decimal | None = None,
) -> dict:
    """
    Calcula a margem de um anuncio.

    Args:
        preco: Preco de venda do produto
        custo: Custo do SKU (CMV)
        listing_type: Tipo do anuncio (classico/premium/full)
        frete: Custo de frete (para anuncios full, normalmente embutido)
        sale_fee_pct: Taxa real obtida via API (quando disponivel)

    Returns:
        dict com:
            - taxa_ml_pct: percentual da taxa ML
            - taxa_ml_valor: valor da taxa ML em R$
            - frete: custo do frete
            - margem_bruta: lucro bruto (preco - custo - taxa_ml - frete)
            - margem_pct: margem como percentual do preco de venda
            - lucro: alias de margem_bruta
    """
    preco = Decimal(str(preco))
    custo = Decimal(str(custo))
    frete = Decimal(str(frete))

    taxa_pct = calcular_taxa_ml(listing_type, sale_fee_pct=sale_fee_pct)
    taxa_valor = (preco * taxa_pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    margem_bruta = preco - custo - taxa_valor - frete
    margem_pct = (
        (margem_bruta / preco * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if preco > 0
        else Decimal("0.00")
    )

    return {
        "taxa_ml_pct": taxa_pct,
        "taxa_ml_valor": taxa_valor,
        "frete": frete,
        "margem_bruta": margem_bruta,
        "margem_pct": margem_pct,
        "lucro": margem_bruta,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Helpers de periodo
# ──────────────────────────────────────────────────────────────────────────────

def _parse_period(period: str) -> tuple[date, date]:
    """
    Converte '7d', '15d', '30d', '60d', '90d' em (data_inicio, data_fim).
    data_fim = ontem (o snapshot de hoje pode estar incompleto).
    """
    days_map = {"7d": 7, "15d": 15, "30d": 30, "60d": 60, "90d": 90}
    days = days_map.get(period, 30)
    hoje = datetime.now(timezone.utc).date()
    data_fim = hoje - timedelta(days=1)
    data_inicio = data_fim - timedelta(days=days - 1)
    return data_inicio, data_fim


def _period_label(period: str) -> str:
    return period


# ──────────────────────────────────────────────────────────────────────────────
# Servicos async de P&L
# ──────────────────────────────────────────────────────────────────────────────

async def get_financeiro_resumo(
    db: AsyncSession,
    user_id,
    period: str = "30d",
) -> dict[str, Any]:
    """
    Retorna resumo P&L agregado para o periodo selecionado.
    Compara automaticamente com o periodo anterior para calcular variacao.
    """
    from app.vendas.models import Listing, ListingSnapshot
    from app.produtos.models import Product

    data_inicio, data_fim = _parse_period(period)
    # Periodo anterior (mesmo comprimento, imediatamente antes)
    days = (data_fim - data_inicio).days + 1
    prev_fim = data_inicio - timedelta(days=1)
    prev_inicio = prev_fim - timedelta(days=days - 1)

    async def _aggregate(d_inicio: date, d_fim: date) -> dict:
        """Agrega metricas de snapshots no intervalo [d_inicio, d_fim].

        Uses latest-per-day deduplication to avoid counting multiple
        snapshots from the same day.
        """
        from sqlalchemy import cast, Date

        # Subquery: latest snapshot per listing per day (deduplication)
        latest_per_day = (
            select(
                ListingSnapshot.listing_id,
                cast(ListingSnapshot.captured_at, Date).label("snap_date"),
                func.max(ListingSnapshot.captured_at).label("max_captured_at"),
            )
            .where(
                cast(ListingSnapshot.captured_at, Date) >= d_inicio,
                cast(ListingSnapshot.captured_at, Date) <= d_fim,
            )
            .group_by(ListingSnapshot.listing_id, cast(ListingSnapshot.captured_at, Date))
            .subquery()
        )

        # Revenue fallback: use price * sales_today when revenue is null
        revenue_expr = func.coalesce(
            ListingSnapshot.revenue,
            ListingSnapshot.price * ListingSnapshot.sales_today,
        )

        rows = await db.execute(
            select(
                Listing.id,
                Listing.listing_type,
                Listing.sale_fee_pct,
                Listing.avg_shipping_cost,
                Listing.product_id,
                func.sum(revenue_expr).label("revenue"),
                func.sum(func.coalesce(ListingSnapshot.orders_count, ListingSnapshot.sales_today)).label("orders"),
                func.sum(ListingSnapshot.cancelled_orders).label("cancelled"),
                func.sum(ListingSnapshot.returns_count).label("returns"),
            )
            .join(ListingSnapshot, ListingSnapshot.listing_id == Listing.id)
            .join(
                latest_per_day,
                (ListingSnapshot.listing_id == latest_per_day.c.listing_id)
                & (ListingSnapshot.captured_at == latest_per_day.c.max_captured_at),
            )
            .where(
                Listing.user_id == user_id,
            )
            .group_by(
                Listing.id,
                Listing.listing_type,
                Listing.sale_fee_pct,
                Listing.avg_shipping_cost,
                Listing.product_id,
            )
        )
        listing_rows = rows.all()

        # Buscar custos dos produtos vinculados
        product_ids = [r.product_id for r in listing_rows if r.product_id]
        product_costs: dict = {}
        if product_ids:
            prod_result = await db.execute(
                select(Product.id, Product.cost).where(Product.id.in_(product_ids))
            )
            product_costs = {str(p.id): p.cost for p in prod_result.all()}

        vendas_brutas = Decimal("0")
        taxas_ml_total = Decimal("0")
        frete_total = Decimal("0")
        custo_total = Decimal("0")
        total_pedidos = 0
        total_cancelamentos = 0
        total_devolucoes = 0

        for row in listing_rows:
            rev = Decimal(str(row.revenue or 0))
            orders = int(row.orders or 0)
            taxa_pct = calcular_taxa_ml(row.listing_type, sale_fee_pct=row.sale_fee_pct)
            taxa_valor = (rev * taxa_pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            frete_unit = Decimal(str(row.avg_shipping_cost or 0))
            frete_listing = (frete_unit * orders).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            vendas_brutas += rev
            taxas_ml_total += taxa_valor
            frete_total += frete_listing
            total_pedidos += orders
            total_cancelamentos += int(row.cancelled or 0)
            total_devolucoes += int(row.returns or 0)

            if row.product_id:
                cost = product_costs.get(str(row.product_id), Decimal("0"))
                custo_total += (Decimal(str(cost)) * orders).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        receita_liquida = vendas_brutas - taxas_ml_total - frete_total
        margem_bruta = receita_liquida - custo_total
        margem_pct = (
            (margem_bruta / vendas_brutas * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if vendas_brutas > 0
            else Decimal("0")
        )

        return {
            "vendas_brutas": vendas_brutas,
            "taxas_ml_total": taxas_ml_total,
            "frete_total": frete_total,
            "receita_liquida": receita_liquida,
            "custo_total": custo_total,
            "margem_bruta": margem_bruta,
            "margem_pct": margem_pct,
            "total_pedidos": total_pedidos,
            "total_cancelamentos": total_cancelamentos,
            "total_devolucoes": total_devolucoes,
        }

    atual = await _aggregate(data_inicio, data_fim)
    anterior = await _aggregate(prev_inicio, prev_fim)

    def _variacao(novo: Decimal, antigo: Decimal) -> Decimal | None:
        if antigo == 0:
            return None
        return ((novo - antigo) / antigo * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "periodo": period,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        **atual,
        "variacao_vendas_pct": _variacao(atual["vendas_brutas"], anterior["vendas_brutas"]),
        "variacao_receita_pct": _variacao(atual["receita_liquida"], anterior["receita_liquida"]),
    }


async def get_financeiro_detalhado(
    db: AsyncSession,
    user_id,
    period: str = "30d",
) -> dict[str, Any]:
    """
    Retorna breakdown financeiro por anuncio (MLB) para o periodo.
    """
    from app.vendas.models import Listing, ListingSnapshot
    from app.produtos.models import Product
    from sqlalchemy import cast, Date

    data_inicio, data_fim = _parse_period(period)
    d_inicio_dt = datetime(data_inicio.year, data_inicio.month, data_inicio.day, tzinfo=timezone.utc)
    d_fim_dt = datetime(data_fim.year, data_fim.month, data_fim.day, 23, 59, 59, tzinfo=timezone.utc)

    # Subquery: latest snapshot per listing per day (deduplication)
    latest_per_day = (
        select(
            ListingSnapshot.listing_id,
            cast(ListingSnapshot.captured_at, Date).label("snap_date"),
            func.max(ListingSnapshot.captured_at).label("max_captured_at"),
        )
        .where(
            ListingSnapshot.captured_at >= d_inicio_dt,
            ListingSnapshot.captured_at <= d_fim_dt,
        )
        .group_by(ListingSnapshot.listing_id, cast(ListingSnapshot.captured_at, Date))
        .subquery()
    )

    # Revenue fallback: use price * sales_today when revenue is null
    revenue_expr = func.coalesce(
        ListingSnapshot.revenue,
        ListingSnapshot.price * ListingSnapshot.sales_today,
    )

    rows = await db.execute(
        select(
            Listing.id,
            Listing.mlb_id,
            Listing.title,
            Listing.listing_type,
            Listing.thumbnail,
            Listing.sale_fee_pct,
            Listing.avg_shipping_cost,
            Listing.product_id,
            func.sum(revenue_expr).label("revenue"),
            func.sum(func.coalesce(ListingSnapshot.orders_count, ListingSnapshot.sales_today)).label("orders"),
            func.sum(ListingSnapshot.cancelled_orders).label("cancelled"),
            func.sum(ListingSnapshot.returns_count).label("returns"),
        )
        .join(ListingSnapshot, ListingSnapshot.listing_id == Listing.id)
        .join(
            latest_per_day,
            (ListingSnapshot.listing_id == latest_per_day.c.listing_id)
            & (ListingSnapshot.captured_at == latest_per_day.c.max_captured_at),
        )
        .where(
            Listing.user_id == user_id,
        )
        .group_by(
            Listing.id,
            Listing.mlb_id,
            Listing.title,
            Listing.listing_type,
            Listing.thumbnail,
            Listing.sale_fee_pct,
            Listing.avg_shipping_cost,
            Listing.product_id,
        )
        .order_by(func.sum(revenue_expr).desc().nullslast())
    )
    listing_rows = rows.all()

    # Buscar custos dos produtos vinculados
    product_ids = [r.product_id for r in listing_rows if r.product_id]
    product_costs: dict = {}
    if product_ids:
        prod_result = await db.execute(
            select(Product.id, Product.cost).where(Product.id.in_(product_ids))
        )
        product_costs = {str(p.id): p.cost for p in prod_result.all()}

    items = []
    for row in listing_rows:
        rev = Decimal(str(row.revenue or 0))
        orders = int(row.orders or 0)
        taxa_pct = calcular_taxa_ml(row.listing_type, sale_fee_pct=row.sale_fee_pct)
        taxa_valor = (rev * taxa_pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        frete_unit = Decimal(str(row.avg_shipping_cost or 0))
        frete_listing = (frete_unit * orders).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        receita_liquida = rev - taxa_valor - frete_listing

        custo_unitario = None
        custo_total = None
        margem = None
        margem_pct_val = None

        if row.product_id:
            cost = product_costs.get(str(row.product_id))
            if cost is not None:
                custo_unitario = Decimal(str(cost))
                custo_total = (custo_unitario * orders).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                margem = receita_liquida - custo_total
                margem_pct_val = (
                    (margem / rev * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    if rev > 0 else Decimal("0")
                )

        items.append({
            "mlb_id": row.mlb_id,
            "title": row.title,
            "listing_type": row.listing_type,
            "thumbnail": row.thumbnail,
            "vendas_brutas": rev,
            "taxa_ml_pct": (taxa_pct * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "taxa_ml_valor": taxa_valor,
            "frete": frete_listing,
            "receita_liquida": receita_liquida,
            "custo_unitario": custo_unitario,
            "custo_total": custo_total,
            "margem": margem,
            "margem_pct": margem_pct_val,
            "unidades": orders,
            "cancelamentos": int(row.cancelled or 0),
            "devolucoes": int(row.returns or 0),
        })

    return {
        "periodo": period,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "items": items,
    }


async def get_financeiro_timeline(
    db: AsyncSession,
    user_id,
    period: str = "30d",
) -> dict[str, Any]:
    """
    Retorna serie temporal diaria de metricas financeiras para graficos.
    """
    from app.vendas.models import Listing, ListingSnapshot
    from sqlalchemy import cast, Date as SQLDate

    data_inicio, data_fim = _parse_period(period)
    d_inicio_dt = datetime(data_inicio.year, data_inicio.month, data_inicio.day, tzinfo=timezone.utc)
    d_fim_dt = datetime(data_fim.year, data_fim.month, data_fim.day, 23, 59, 59, tzinfo=timezone.utc)

    # Converte captured_at (UTC) para BRT (UTC-3) antes de extrair a data
    # Isso evita que vendas de madrugada BRT apareçam no dia anterior
    brt_date = cast(
        func.timezone("America/Sao_Paulo", ListingSnapshot.captured_at),
        SQLDate,
    ).label("snap_date")

    # Subquery: latest snapshot per listing per day (deduplication)
    latest_per_day = (
        select(
            ListingSnapshot.listing_id,
            brt_date,
            func.max(ListingSnapshot.captured_at).label("max_captured_at"),
        )
        .where(
            ListingSnapshot.captured_at >= d_inicio_dt,
            ListingSnapshot.captured_at <= d_fim_dt,
        )
        .group_by(ListingSnapshot.listing_id, brt_date)
        .subquery()
    )

    # Revenue fallback: use price * sales_today when revenue is null
    revenue_expr = func.coalesce(
        ListingSnapshot.revenue,
        ListingSnapshot.price * ListingSnapshot.sales_today,
    )

    # Agrupa por dia e listing para poder calcular taxa por listing_type
    rows = await db.execute(
        select(
            brt_date,
            Listing.listing_type,
            Listing.sale_fee_pct,
            Listing.avg_shipping_cost,
            func.sum(revenue_expr).label("revenue"),
            func.sum(func.coalesce(ListingSnapshot.orders_count, ListingSnapshot.sales_today)).label("orders"),
        )
        .join(Listing, ListingSnapshot.listing_id == Listing.id)
        .join(
            latest_per_day,
            (ListingSnapshot.listing_id == latest_per_day.c.listing_id)
            & (ListingSnapshot.captured_at == latest_per_day.c.max_captured_at),
        )
        .where(
            Listing.user_id == user_id,
        )
        .group_by(
            brt_date,
            Listing.listing_type,
            Listing.sale_fee_pct,
            Listing.avg_shipping_cost,
        )
        .order_by(brt_date)
    )
    all_rows = rows.all()

    # Agrupa por data
    by_date: dict[date, dict] = {}
    for row in all_rows:
        snap_date = row.snap_date
        if snap_date not in by_date:
            by_date[snap_date] = {
                "vendas_brutas": Decimal("0"),
                "taxas": Decimal("0"),
                "frete": Decimal("0"),
                "pedidos": 0,
            }
        rev = Decimal(str(row.revenue or 0))
        orders = int(row.orders or 0)
        taxa_pct = calcular_taxa_ml(row.listing_type, sale_fee_pct=row.sale_fee_pct)
        taxa_val = (rev * taxa_pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        frete_unit = Decimal(str(row.avg_shipping_cost or 0))
        frete_val = (frete_unit * orders).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        by_date[snap_date]["vendas_brutas"] += rev
        by_date[snap_date]["taxas"] += taxa_val
        by_date[snap_date]["frete"] += frete_val
        by_date[snap_date]["pedidos"] += orders

    points = []
    for snap_date in sorted(by_date.keys()):
        d = by_date[snap_date]
        receita_liquida = d["vendas_brutas"] - d["taxas"] - d["frete"]
        points.append({
            "date": snap_date,
            "vendas_brutas": d["vendas_brutas"],
            "receita_liquida": receita_liquida,
            "taxas": d["taxas"],
            "frete": d["frete"],
            "pedidos": d["pedidos"],
        })

    return {
        "periodo": period,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "points": points,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Servicos de DRE, Impostos e Rentabilidade por SKU
# ──────────────────────────────────────────────────────────────────────────────


async def get_dre(
    db: AsyncSession,
    user_id,
    period: str = "30d",
) -> dict[str, Any]:
    """
    Retorna DRE Gerencial Simplificado (Income Statement).

    Estrutura:
    - Receita Bruta = soma vendas brutas
    - (-) Taxas ML = soma taxas
    - (-) Frete = soma frete
    - (-) Cancelamentos/Devoluções = soma valores cancelados/devolvidos
    = Receita Líquida
    - (-) CMV = soma custo dos produtos vendidos
    = Lucro Bruto
    - (-) Impostos Estimados = baseado em tax_config
    = Lucro Operacional Estimado

    Também compara com período anterior para variações.
    """
    # Obter resumo P&L atual
    resumo_atual = await get_financeiro_resumo(db, user_id, period=period)
    data_inicio, data_fim = _parse_period(period)

    # Período anterior
    days = (data_fim - data_inicio).days + 1
    prev_fim = data_inicio - timedelta(days=1)
    prev_inicio = prev_fim - timedelta(days=days - 1)

    # Calcular para período anterior
    resumo_anterior = await get_financeiro_resumo(db, user_id, period=period)

    # Obter configuração de impostos do usuário
    from app.financeiro.models import TaxConfig

    tax_config_row = await db.execute(
        select(TaxConfig).where(TaxConfig.user_id == user_id)
    )
    tax_config = tax_config_row.scalars().first()

    # Calcular DRE
    receita_bruta = resumo_atual["vendas_brutas"]
    taxa_ml = resumo_atual["taxas_ml_total"]
    frete = resumo_atual["frete_total"]
    cancelamentos_devolvidos = Decimal("0")  # Será calculado abaixo

    # Estimar valor de cancelamentos/devoluções (usando contagem)
    if resumo_atual["total_cancelamentos"] > 0 or resumo_atual["total_devolucoes"] > 0:
        if resumo_atual["total_pedidos"] > 0:
            preco_medio = receita_bruta / resumo_atual["total_pedidos"]
            cancelamentos_devolvidos = (
                (resumo_atual["total_cancelamentos"] + resumo_atual["total_devolucoes"]) * preco_medio
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    receita_liquida = receita_bruta - taxa_ml - frete - cancelamentos_devolvidos
    cmv_total = resumo_atual["custo_total"]
    lucro_bruto = receita_liquida - cmv_total

    # Calcular impostos estimados
    impostos_estimados = Decimal("0")
    if tax_config and receita_bruta > 0:
        impostos_estimados = (receita_bruta * tax_config.aliquota_efetiva).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    lucro_operacional = lucro_bruto - impostos_estimados

    # Calcular percentuais
    margem_bruta_pct = (
        (lucro_bruto / receita_bruta * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if receita_bruta > 0
        else Decimal("0")
    )
    margem_liquida_pct = (
        (lucro_operacional / receita_bruta * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if receita_bruta > 0
        else Decimal("0")
    )

    # Variações vs período anterior
    def _variacao(novo: Decimal, antigo: Decimal) -> Decimal | None:
        if antigo == 0:
            return None
        return ((novo - antigo) / antigo * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Recalcular para período anterior para comparação
    resumo_prev = await get_financeiro_resumo(db, user_id, period=period)
    receita_bruta_prev = resumo_prev["vendas_brutas"]
    lucro_bruto_prev = resumo_prev["receita_liquida"] - resumo_prev["custo_total"]

    return {
        "periodo": period,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "receita_bruta": receita_bruta,
        "taxa_ml": taxa_ml,
        "frete": frete,
        "cancelamentos_devolvidos": cancelamentos_devolvidos,
        "receita_liquida": receita_liquida,
        "cmv_total": cmv_total,
        "lucro_bruto": lucro_bruto,
        "impostos_estimados": impostos_estimados,
        "lucro_operacional": lucro_operacional,
        "margem_bruta_pct": margem_bruta_pct,
        "margem_liquida_pct": margem_liquida_pct,
        "variacao_receita_pct": _variacao(receita_bruta, receita_bruta_prev),
        "variacao_lucro_pct": _variacao(lucro_operacional, lucro_bruto_prev - resumo_prev["custo_total"]),
    }


async def get_tax_config(
    db: AsyncSession,
    user_id,
) -> dict[str, Any] | None:
    """Obter configuração de impostos do usuário."""
    from app.financeiro.models import TaxConfig

    result = await db.execute(
        select(TaxConfig).where(TaxConfig.user_id == user_id)
    )
    tax_config = result.scalars().first()

    if not tax_config:
        return None

    return {
        "regime": tax_config.regime,
        "faixa_anual": tax_config.faixa_anual,
        "aliquota_efetiva": tax_config.aliquota_efetiva,
    }


async def set_tax_config(
    db: AsyncSession,
    user_id,
    regime: str,
    faixa_anual: Decimal,
    aliquota_efetiva: Decimal,
) -> dict[str, Any]:
    """Criar ou atualizar configuração de impostos do usuário."""
    from app.financeiro.models import TaxConfig
    from sqlalchemy import delete

    # Tentar encontrar config existente
    result = await db.execute(
        select(TaxConfig).where(TaxConfig.user_id == user_id)
    )
    tax_config = result.scalars().first()

    if tax_config:
        # Atualizar
        tax_config.regime = regime
        tax_config.faixa_anual = Decimal(str(faixa_anual))
        tax_config.aliquota_efetiva = Decimal(str(aliquota_efetiva))
    else:
        # Criar novo
        tax_config = TaxConfig(
            user_id=user_id,
            regime=regime,
            faixa_anual=Decimal(str(faixa_anual)),
            aliquota_efetiva=Decimal(str(aliquota_efetiva)),
        )
        db.add(tax_config)

    await db.commit()
    await db.refresh(tax_config)

    return {
        "regime": tax_config.regime,
        "faixa_anual": tax_config.faixa_anual,
        "aliquota_efetiva": tax_config.aliquota_efetiva,
    }


async def get_rentabilidade_por_sku(
    db: AsyncSession,
    user_id,
    period: str = "30d",
) -> dict[str, Any]:
    """
    Retorna rentabilidade agregada por SKU (Product).

    Para cada SKU:
    - Receita total
    - Custo total
    - Margem total e %
    - Número de listings vinculados
    - Número de vendas
    - Melhor e pior listing por margem
    """
    from app.vendas.models import Listing, ListingSnapshot
    from app.produtos.models import Product
    from sqlalchemy import cast, Date

    data_inicio, data_fim = _parse_period(period)
    d_inicio_dt = datetime(data_inicio.year, data_inicio.month, data_inicio.day, tzinfo=timezone.utc)
    d_fim_dt = datetime(data_fim.year, data_fim.month, data_fim.day, 23, 59, 59, tzinfo=timezone.utc)

    # Subquery: latest snapshot per listing per day (deduplication)
    latest_per_day = (
        select(
            ListingSnapshot.listing_id,
            cast(ListingSnapshot.captured_at, Date).label("snap_date"),
            func.max(ListingSnapshot.captured_at).label("max_captured_at"),
        )
        .where(
            ListingSnapshot.captured_at >= d_inicio_dt,
            ListingSnapshot.captured_at <= d_fim_dt,
        )
        .group_by(ListingSnapshot.listing_id, cast(ListingSnapshot.captured_at, Date))
        .subquery()
    )

    # Revenue fallback: use price * sales_today when revenue is null
    revenue_expr = func.coalesce(
        ListingSnapshot.revenue,
        ListingSnapshot.price * ListingSnapshot.sales_today,
    )

    # Agrupar por product_id (SKU)
    rows = await db.execute(
        select(
            Listing.product_id,
            Listing.mlb_id,
            Listing.title,
            func.sum(revenue_expr).label("revenue"),
            func.sum(func.coalesce(ListingSnapshot.orders_count, ListingSnapshot.sales_today)).label("orders"),
            Listing.listing_type,
            Listing.sale_fee_pct,
            Listing.avg_shipping_cost,
        )
        .join(ListingSnapshot, ListingSnapshot.listing_id == Listing.id)
        .join(
            latest_per_day,
            (ListingSnapshot.listing_id == latest_per_day.c.listing_id)
            & (ListingSnapshot.captured_at == latest_per_day.c.max_captured_at),
        )
        .where(
            Listing.user_id == user_id,
            Listing.product_id.isnot(None),
        )
        .group_by(
            Listing.product_id,
            Listing.mlb_id,
            Listing.title,
            Listing.listing_type,
            Listing.sale_fee_pct,
            Listing.avg_shipping_cost,
        )
        .order_by(Listing.product_id)
    )
    listing_rows = rows.all()

    # Buscar dados dos produtos
    product_ids = list(set([str(r.product_id) for r in listing_rows if r.product_id]))
    products_data: dict = {}
    if product_ids:
        prod_result = await db.execute(
            select(Product).where(Product.id.in_(product_ids))
        )
        for prod in prod_result.scalars().all():
            products_data[str(prod.id)] = {
                "sku": prod.sku,
                "nome": prod.name,
                "cost": prod.cost,
            }

    # Agrupar por product_id
    by_sku: dict[str, dict] = {}
    for row in listing_rows:
        product_id_str = str(row.product_id)
        if product_id_str not in by_sku:
            by_sku[product_id_str] = {
                "sku": products_data.get(product_id_str, {}).get("sku", ""),
                "nome": products_data.get(product_id_str, {}).get("nome", ""),
                "cost_unitario": products_data.get(product_id_str, {}).get("cost", Decimal("0")),
                "listings": [],
                "receita_total": Decimal("0"),
                "custo_total": Decimal("0"),
                "num_vendas": 0,
            }

        rev = Decimal(str(row.revenue or 0))
        orders = int(row.orders or 0)
        taxa_pct = calcular_taxa_ml(row.listing_type, sale_fee_pct=row.sale_fee_pct)
        taxa_valor = (rev * taxa_pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        frete_unit = Decimal(str(row.avg_shipping_cost or 0))
        frete_listing = (frete_unit * orders).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        receita_liquida = rev - taxa_valor - frete_listing

        custo_unitario = by_sku[product_id_str]["cost_unitario"]
        custo_listing = (custo_unitario * orders).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        margem = receita_liquida - custo_listing

        by_sku[product_id_str]["listings"].append({
            "mlb_id": row.mlb_id,
            "title": row.title[:50],
            "receita": receita_liquida,
            "margem": margem,
        })
        by_sku[product_id_str]["receita_total"] += receita_liquida
        by_sku[product_id_str]["custo_total"] += custo_listing
        by_sku[product_id_str]["num_vendas"] += orders

    # Montar resultado final
    items = []
    total_receita = Decimal("0")
    total_margem = Decimal("0")

    for product_id_str, sku_data in by_sku.items():
        receita = sku_data["receita_total"]
        custo = sku_data["custo_total"]
        margem = receita - custo
        margem_pct = (
            (margem / receita * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if receita > 0
            else Decimal("0")
        )

        # Encontrar melhor e pior listing
        listings = sku_data["listings"]
        melhor_listing = None
        pior_listing = None
        if listings:
            sorted_by_margem = sorted(listings, key=lambda x: x["margem"], reverse=True)
            melhor_listing = sorted_by_margem[0]["mlb_id"]
            pior_listing = sorted_by_margem[-1]["mlb_id"]

        items.append({
            "product_id": product_id_str,
            "sku": sku_data["sku"],
            "nome": sku_data["nome"],
            "receita_total": receita,
            "custo_total": custo,
            "margem_total": margem,
            "margem_pct": margem_pct,
            "num_listings": len(listings),
            "num_vendas": sku_data["num_vendas"],
            "melhor_listing_mlb": melhor_listing,
            "pior_listing_mlb": pior_listing,
        })

        total_receita += receita
        total_margem += margem

    # Ordenar por receita decrescente
    items.sort(key=lambda x: x["receita_total"], reverse=True)

    return {
        "periodo": period,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "items": items,
        "total_skus": len(items),
        "receita_total": total_receita,
        "margem_total": total_margem,
    }


async def get_cashflow(
    db: AsyncSession,
    user_id,
) -> dict:
    """
    Calcula o cash flow projetado para os proximos 30 dias.

    Logica de liberacao D+8:
    - Para pedidos com delivery_date preenchida e payment_status="approved":
      data_liberacao = delivery_date + 8 dias
    - Para pedidos sem delivery_date mas com shipping_status="shipped":
      estima delivery_date = order_date + 5 dias, depois libera em D+8

    Agrupa por:
      - proximos_7d: liberacoes nos proximos 7 dias
      - proximos_14d: liberacoes entre 8 e 14 dias
      - proximos_30d: liberacoes entre 15 e 30 dias

    Retorna a linha do tempo detalhada por dia.
    """
    from app.auth.models import MLAccount
    from app.vendas.models import Order

    hoje = datetime.now(timezone.utc).date()
    limite_30d = hoje + timedelta(days=30)

    # Busca todos os pedidos aprovados das contas do usuario
    # com envio ainda pendente de liberacao financeira (D+8 ainda nao venceu)
    rows = await db.execute(
        select(Order)
        .join(MLAccount, Order.ml_account_id == MLAccount.id)
        .where(
            MLAccount.user_id == user_id,
            Order.payment_status == "approved",
            Order.shipping_status.in_(["shipped", "to_be_agreed", "pending", "ready_to_ship", "delivered"]),
        )
        .order_by(Order.order_date.asc())
    )
    orders = rows.scalars().all()

    # Agrupa liberacoes por data
    by_date: dict[date, dict] = {}

    for order in orders:
        # Determina a data de entrega estimada ou real
        if order.delivery_date:
            delivery = (
                order.delivery_date.date()
                if hasattr(order.delivery_date, "date")
                else order.delivery_date
            )
        elif order.shipping_status in ("shipped", "ready_to_ship"):
            # Estima entrega em 5 dias a partir do pedido
            order_d = (
                order.order_date.date()
                if hasattr(order.order_date, "date")
                else order.order_date
            )
            delivery = order_d + timedelta(days=5)
        else:
            # Sem data de entrega estimavel, assume entrega em 7 dias
            order_d = (
                order.order_date.date()
                if hasattr(order.order_date, "date")
                else order.order_date
            )
            delivery = order_d + timedelta(days=7)

        # Libera o valor D+8 apos a entrega
        data_liberacao = delivery + timedelta(days=8)

        # Apenas considera liberacoes futuras nos proximos 30 dias
        if data_liberacao < hoje or data_liberacao > limite_30d:
            continue

        if data_liberacao not in by_date:
            by_date[data_liberacao] = {"amount": Decimal("0"), "orders_count": 0}

        by_date[data_liberacao]["amount"] += order.net_amount or Decimal("0")
        by_date[data_liberacao]["orders_count"] += 1

    # Monta a timeline e os totais por faixa
    proximos_7d = Decimal("0")
    proximos_14d = Decimal("0")
    proximos_30d = Decimal("0")

    timeline = []
    for d in sorted(by_date.keys()):
        entry = by_date[d]
        amount = entry["amount"]
        days_from_now = (d - hoje).days

        if days_from_now <= 7:
            proximos_7d += amount
        elif days_from_now <= 14:
            proximos_14d += amount
        else:
            proximos_30d += amount

        timeline.append({
            "date": d,
            "amount": amount,
            "orders_count": entry["orders_count"],
        })

    total_pendente = proximos_7d + proximos_14d + proximos_30d

    return {
        "proximos_7d": proximos_7d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "proximos_14d": proximos_14d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "proximos_30d": proximos_30d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "total_pendente": total_pendente.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "timeline": timeline,
    }
