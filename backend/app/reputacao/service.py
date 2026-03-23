"""
Servico de reputacao do vendedor.
Busca dados da API ML e salva snapshots no banco.
"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, cast, Date, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import MLAccount
from app.mercadolivre.client import MLClient, MLClientError
from app.reputacao.models import ReputationSnapshot
from app.vendas.models import Listing, ListingSnapshot

logger = logging.getLogger(__name__)

# Thresholds de nivel por KPI (limites para manutencao de nivel)
# Referência: https://www.mercadolivre.com.br/help/Como-posso-manter-meu-nivel-de-vendedor-e-status-de-Vendedor-Premiado-_FAQ_4203
REPUTATION_THRESHOLDS = {
    "claims": Decimal("3.0"),          # Reclamacoes: max 3%
    "mediations": Decimal("0.5"),      # Mediações: max 0.5% (não documentado, usando conservador)
    "cancellations": Decimal("2.0"),   # Cancelamentos: max 2%
    "late_shipments": Decimal("15.0"), # Atrasos envio: max 15%
}

async def calculate_revenue_60d(db: AsyncSession, ml_account_id) -> Decimal:
    """
    Calcula receita bruta total dos ultimos 60 dias
    somando revenue dos ListingSnapshots vinculados a conta ML.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=60)
    result = await db.execute(
        select(func.coalesce(func.sum(ListingSnapshot.revenue), 0))
        .join(Listing, ListingSnapshot.listing_id == Listing.id)
        .where(
            Listing.ml_account_id == ml_account_id,
            ListingSnapshot.captured_at >= cutoff,
            ListingSnapshot.revenue.isnot(None),
        )
    )
    return result.scalar_one() or Decimal("0")


async def calculate_orders_60d(db: AsyncSession, ml_account_id) -> int:
    """
    Calcula total de pedidos dos ultimos 60 dias
    somando orders_count dos ListingSnapshots vinculados a conta ML.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=60)
    result = await db.execute(
        select(func.coalesce(func.sum(ListingSnapshot.orders_count), 0))
        .join(Listing, ListingSnapshot.listing_id == Listing.id)
        .where(
            Listing.ml_account_id == ml_account_id,
            ListingSnapshot.captured_at >= cutoff,
        )
    )
    return int(result.scalar_one() or 0)


async def fetch_and_save_reputation(
    db: AsyncSession, account: MLAccount
) -> ReputationSnapshot | None:
    """
    Busca reputacao do vendedor via API ML e salva snapshot.
    Faz upsert: se ja existe snapshot do mesmo dia, atualiza.
    """
    if not account.access_token:
        logger.warning(f"Sem token ML para conta {account.nickname}")
        return None

    client = MLClient(account.access_token)
    try:
        data = await client.get_seller_reputation(account.ml_user_id)
    except MLClientError as e:
        logger.error(f"Erro ao buscar reputacao de {account.nickname}: {e}")
        return None
    finally:
        await client.close()

    if not data:
        return None

    reputation = data.get("seller_reputation", {})
    transactions = reputation.get("transactions", {})
    metrics = reputation.get("metrics", {})

    # Extrai rates das metricas
    # Path real da API ML GET /users/{id}:
    #   seller_reputation.metrics.claims.rate         — taxa de reclamacoes
    #   seller_reputation.metrics.cancellations.rate  — taxa de cancelamentos
    #   seller_reputation.metrics.delayed_handling_time.rate — atrasos de envio
    #   seller_reputation.transactions.canceled       — cancelamentos totais (all-time)
    # Mediations: nao existe campo "mediations" separado na API publica do ML.
    # Algumas versoes retornam como sub-campo de claims ou como campo top-level
    # em metrics. O fallback abaixo cobre ambos os casos.
    claims_data = metrics.get("claims", {})
    delayed_data = metrics.get("delayed_handling_time", {})
    cancellations_data = metrics.get("cancellations", {})

    claims_rate = Decimal(str(claims_data.get("rate", 0))) * 100 if claims_data.get("rate") is not None else None
    cancellations_rate = Decimal(str(cancellations_data.get("rate", 0))) * 100 if cancellations_data.get("rate") is not None else None
    late_rate = Decimal(str(delayed_data.get("rate", 0))) * 100 if delayed_data.get("rate") is not None else None

    # Mediations: tenta metrics.mediations primeiro, depois claims.mediations (fallback)
    # Se nenhum existir, usa None (nao inventar 0%)
    mediations_data = metrics.get("mediations") or claims_data.get("mediations") or {}
    if isinstance(mediations_data, dict) and mediations_data.get("rate") is not None:
        mediations_rate = Decimal(str(mediations_data["rate"])) * 100
    else:
        mediations_rate = None

    # Valores absolutos
    claims_value = claims_data.get("value", 0)
    cancellations_value = cancellations_data.get("value", 0)
    late_value = delayed_data.get("value", 0)
    mediations_value = mediations_data.get("value", 0) if isinstance(mediations_data, dict) else 0

    # Transacoes — usar completed como base dos 60d se disponivel
    # transactions.total e ALL-TIME, nao 60 dias
    # O ML nao retorna "60d" diretamente; usamos nossos snapshots como fonte
    completed = transactions.get("completed", 0)
    canceled = transactions.get("canceled", 0)

    # Nivel e power seller
    seller_level = reputation.get("level_id")
    power_seller_status = reputation.get("power_seller_status")

    # Revenue e total_sales dos 60 dias: calcular a partir dos ListingSnapshots reais
    total_revenue = await calculate_revenue_60d(db, account.id)
    total_sales_from_snapshots = await calculate_orders_60d(db, account.id)
    # Se temos dados reais dos snapshots, usamos; senao, fallback para completed da API
    total_sales = total_sales_from_snapshots if total_sales_from_snapshots > 0 else completed

    # Upsert: verifica se ja existe snapshot do mesmo dia
    from datetime import date as date_type
    existing_result = await db.execute(
        select(ReputationSnapshot).where(
            ReputationSnapshot.ml_account_id == account.id,
            cast(ReputationSnapshot.captured_at, Date) == date_type.today(),
        ).order_by(ReputationSnapshot.captured_at.desc()).limit(1)
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        existing.seller_level = seller_level
        existing.power_seller_status = power_seller_status
        existing.claims_rate = claims_rate
        existing.mediations_rate = mediations_rate
        existing.cancellations_rate = cancellations_rate
        existing.late_shipments_rate = late_rate
        existing.total_sales_60d = total_sales
        existing.completed_sales_60d = completed
        existing.total_revenue_60d = total_revenue
        existing.claims_value = claims_value
        existing.mediations_value = mediations_value
        existing.cancellations_value = cancellations_value
        existing.late_shipments_value = late_value
        existing.captured_at = datetime.now(timezone.utc)
        snapshot = existing
    else:
        snapshot = ReputationSnapshot(
            ml_account_id=account.id,
            seller_level=seller_level,
            power_seller_status=power_seller_status,
            claims_rate=claims_rate,
            mediations_rate=mediations_rate,
            cancellations_rate=cancellations_rate,
            late_shipments_rate=late_rate,
            total_sales_60d=total_sales,
            completed_sales_60d=completed,
            total_revenue_60d=total_revenue,
            claims_value=claims_value,
            mediations_value=mediations_value,
            cancellations_value=cancellations_value,
            late_shipments_value=late_value,
        )
        db.add(snapshot)

    await db.flush()
    logger.info(f"Reputacao salva para {account.nickname}: level={seller_level}")
    return snapshot


async def get_current_reputation(
    db: AsyncSession, user_id, ml_account_id=None
) -> ReputationSnapshot | None:
    """Busca o snapshot de reputacao mais recente."""
    query = (
        select(ReputationSnapshot)
        .join(MLAccount, ReputationSnapshot.ml_account_id == MLAccount.id)
        .where(MLAccount.user_id == user_id)
    )
    if ml_account_id:
        query = query.where(ReputationSnapshot.ml_account_id == ml_account_id)

    query = query.order_by(ReputationSnapshot.captured_at.desc()).limit(1)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_reputation_history(
    db: AsyncSession, user_id, days: int = 60, ml_account_id=None
) -> list[ReputationSnapshot]:
    """Busca historico de snapshots de reputacao."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    query = (
        select(ReputationSnapshot)
        .join(MLAccount, ReputationSnapshot.ml_account_id == MLAccount.id)
        .where(
            MLAccount.user_id == user_id,
            ReputationSnapshot.captured_at >= cutoff,
        )
    )
    if ml_account_id:
        query = query.where(ReputationSnapshot.ml_account_id == ml_account_id)

    query = query.order_by(ReputationSnapshot.captured_at.asc()).limit(365)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_reputation_risk(
    db: AsyncSession,
    user_id,
    ml_account_id=None,
) -> dict | None:
    """
    Calcula o risco de rebaixamento para cada KPI de reputacao.

    Logica:
    - Pega o snapshot mais recente
    - Para cada KPI, calcula quantas ocorrencias adicionais sao necessarias
      para ultrapassar o threshold e perder o nivel atual.
    - buffer = max_allowed - current_count
    - risk_level: buffer <= 1 -> critical, <= 3 -> warning, else -> safe

    Retorna None se nao houver snapshot disponivel.
    """
    snapshot = await get_current_reputation(db, user_id, ml_account_id)
    if not snapshot:
        return None

    total_sales = snapshot.total_sales_60d or 0

    # Se não há dados de vendas, retornar status especial
    if total_sales == 0:
        return {
            "ml_account_id": snapshot.ml_account_id,
            "total_sales_60d": 0,
            "items": [
                {
                    "kpi": "claims",
                    "label": "Reclamacoes",
                    "current_rate": 0,
                    "threshold": float(REPUTATION_THRESHOLDS["claims"]),
                    "current_count": 0,
                    "max_allowed": 0,
                    "buffer": 0,
                    "risk_level": "no_data",
                }
            ] * 4,  # Duplica para os 4 KPIs
        }

    kpi_configs = [
        {
            "kpi": "claims",
            "label": "Reclamacoes",
            "rate": float(snapshot.claims_rate or 0),
            "threshold": float(REPUTATION_THRESHOLDS["claims"]),
        },
        {
            "kpi": "mediations",
            "label": "Mediacoes",
            "rate": float(snapshot.mediations_rate or 0),
            "threshold": float(REPUTATION_THRESHOLDS["mediations"]),
        },
        {
            "kpi": "cancellations",
            "label": "Cancelamentos",
            "rate": float(snapshot.cancellations_rate or 0),
            "threshold": float(REPUTATION_THRESHOLDS["cancellations"]),
        },
        {
            "kpi": "late_shipments",
            "label": "Atrasos de Envio",
            "rate": float(snapshot.late_shipments_rate or 0),
            "threshold": float(REPUTATION_THRESHOLDS["late_shipments"]),
        },
    ]

    items = []
    for cfg in kpi_configs:
        current_rate = cfg["rate"]       # em % (ex: 0.8 significa 0.8%)
        threshold = cfg["threshold"]     # em % (ex: 1.0 significa 1.0%)

        # Quantidade atual de ocorrencias baseada na taxa e total de vendas
        # rate esta em %, entao dividimos por 100 para obter a fracao
        current_count = int(round(total_sales * current_rate / 100))
        max_allowed = int(round(total_sales * threshold / 100))

        buffer = max_allowed - current_count
        # Garante que buffer nao seja negativo (ja ultrapassou o limite)
        buffer = max(buffer, 0)

        if buffer <= 1:
            risk_level = "critical"
        elif buffer <= 3:
            risk_level = "warning"
        else:
            risk_level = "safe"

        items.append({
            "kpi": cfg["kpi"],
            "label": cfg["label"],
            "current_rate": current_rate,
            "threshold": threshold,
            "current_count": current_count,
            "max_allowed": max_allowed,
            "buffer": buffer,
            "risk_level": risk_level,
        })

    return {
        "ml_account_id": snapshot.ml_account_id,
        "total_sales_60d": total_sales,
        "items": items,
    }
