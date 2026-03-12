"""
Service de alertas MSM_Pro.

Responsável por:
- CRUD de AlertConfig com validação de ownership
- Listagem de AlertEvent
- Lógica de avaliação de condições (usada pela Celery task)
"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alertas.models import AlertConfig, AlertEvent
from app.alertas.schemas import AlertConfigCreate, AlertConfigUpdate

logger = logging.getLogger(__name__)


# ============================================================
# CRUD — AlertConfig
# ============================================================


async def create_alert_config(
    db: AsyncSession,
    user_id: UUID,
    payload: AlertConfigCreate,
) -> AlertConfig:
    """Cria uma nova configuração de alerta para o usuário."""
    # Se listing_id foi informado, valida que pertence ao usuário
    if payload.listing_id:
        from app.vendas.models import Listing

        listing_result = await db.execute(
            select(Listing).where(
                Listing.id == payload.listing_id,
                Listing.user_id == user_id,
            )
        )
        if not listing_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Listing não encontrado ou não pertence ao usuário",
            )

    # Se product_id foi informado, valida ownership
    if payload.product_id:
        from app.produtos.models import Product

        product_result = await db.execute(
            select(Product).where(
                Product.id == payload.product_id,
                Product.user_id == user_id,
            )
        )
        if not product_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SKU não encontrado ou não pertence ao usuário",
            )

    alert = AlertConfig(
        user_id=user_id,
        listing_id=payload.listing_id,
        product_id=payload.product_id,
        alert_type=payload.alert_type,
        threshold=payload.threshold,
        channel=payload.channel,
        is_active=True,
    )
    db.add(alert)
    await db.flush()
    await db.refresh(alert)
    return alert


async def list_alert_configs(
    db: AsyncSession,
    user_id: UUID,
    listing_id: UUID | None = None,
    is_active: bool | None = None,
) -> list[AlertConfig]:
    """Lista as configurações de alerta do usuário com filtros opcionais."""
    conditions = [AlertConfig.user_id == user_id]

    if listing_id is not None:
        conditions.append(AlertConfig.listing_id == listing_id)

    if is_active is not None:
        conditions.append(AlertConfig.is_active == is_active)  # noqa: E712

    result = await db.execute(
        select(AlertConfig)
        .where(and_(*conditions))
        .order_by(AlertConfig.created_at.desc())
    )
    return list(result.scalars().all())


async def get_alert_config(
    db: AsyncSession,
    user_id: UUID,
    alert_id: UUID,
) -> AlertConfig:
    """Retorna uma configuração de alerta específica, validando ownership."""
    result = await db.execute(
        select(AlertConfig).where(
            AlertConfig.id == alert_id,
            AlertConfig.user_id == user_id,
        )
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alerta não encontrado",
        )
    return alert


async def update_alert_config(
    db: AsyncSession,
    user_id: UUID,
    alert_id: UUID,
    payload: AlertConfigUpdate,
) -> AlertConfig:
    """Atualiza threshold, canal ou status ativo de um alerta."""
    alert = await get_alert_config(db, user_id, alert_id)

    if payload.threshold is not None:
        alert.threshold = payload.threshold
    if payload.channel is not None:
        alert.channel = payload.channel
    if payload.is_active is not None:
        alert.is_active = payload.is_active

    await db.flush()
    await db.refresh(alert)
    return alert


async def deactivate_alert_config(
    db: AsyncSession,
    user_id: UUID,
    alert_id: UUID,
) -> None:
    """Soft-delete: marca o alerta como inativo."""
    alert = await get_alert_config(db, user_id, alert_id)
    alert.is_active = False
    await db.flush()


# ============================================================
# AlertEvent — listagem
# ============================================================


async def list_alert_events(
    db: AsyncSession,
    user_id: UUID,
    days: int = 30,
) -> list[AlertEvent]:
    """Lista os eventos de alerta disparados nos últimos N dias."""
    threshold = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(AlertEvent)
        .join(AlertConfig, AlertEvent.alert_config_id == AlertConfig.id)
        .where(
            AlertConfig.user_id == user_id,
            AlertEvent.triggered_at >= threshold,
        )
        .order_by(AlertEvent.triggered_at.desc())
    )
    return list(result.scalars().all())


async def list_events_by_alert(
    db: AsyncSession,
    user_id: UUID,
    alert_id: UUID,
    days: int = 30,
) -> list[AlertEvent]:
    """Lista eventos de um alerta específico (valida ownership)."""
    # Garante que o alerta pertence ao usuário
    await get_alert_config(db, user_id, alert_id)

    threshold = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(AlertEvent)
        .where(
            AlertEvent.alert_config_id == alert_id,
            AlertEvent.triggered_at >= threshold,
        )
        .order_by(AlertEvent.triggered_at.desc())
    )
    return list(result.scalars().all())


# ============================================================
# Lógica de avaliação de condições (usada pela Celery task)
# ============================================================


async def evaluate_single_alert(
    db: AsyncSession,
    alert: AlertConfig,
) -> AlertEvent | None:
    """
    Avalia se a condição de um alerta foi atendida.
    Retorna um AlertEvent se disparado, None caso contrário.
    """
    try:
        message = await _check_condition(db, alert)
    except Exception as exc:  # noqa: BLE001
        logger.error("Erro ao avaliar alerta %s: %s", alert.id, exc)
        return None

    if message is None:
        return None

    event = AlertEvent(
        alert_config_id=alert.id,
        message=message,
    )
    db.add(event)
    await db.flush()
    await db.refresh(event)
    logger.info("Alerta disparado: %s | %s", alert.alert_type, message)
    return event


async def _check_condition(db: AsyncSession, alert: AlertConfig) -> str | None:
    """
    Verifica a condição do alerta e retorna mensagem descritiva se disparada.
    Retorna None se a condição NÃO foi atendida.
    """
    atype = alert.alert_type

    # --- conversion_below ---
    if atype == "conversion_below":
        return await _check_conversion_below(db, alert)

    # --- stock_below ---
    if atype == "stock_below":
        return await _check_stock_below(db, alert)

    # --- no_sales_days ---
    if atype == "no_sales_days":
        return await _check_no_sales_days(db, alert)

    # --- competitor_price_change ---
    if atype == "competitor_price_change":
        return await _check_competitor_price_change(db, alert)

    # --- competitor_price_below ---
    if atype == "competitor_price_below":
        return await _check_competitor_price_below(db, alert)

    logger.warning("Tipo de alerta desconhecido: %s", atype)
    return None


# --- helpers por tipo ---

async def _get_listing_ids_for_alert(db: AsyncSession, alert: AlertConfig) -> list:
    """Retorna lista de IDs de listings cobertos pelo alerta."""
    from app.vendas.models import Listing

    if alert.listing_id:
        return [alert.listing_id]

    if alert.product_id:
        result = await db.execute(
            select(Listing.id).where(Listing.product_id == alert.product_id)
        )
        return list(result.scalars().all())

    return []


async def _check_conversion_below(db: AsyncSession, alert: AlertConfig) -> str | None:
    """Verifica se a conversão média dos últimos 7 dias está abaixo do threshold."""
    from app.vendas.models import Listing, ListingSnapshot

    threshold = Decimal(str(alert.threshold or 0))
    listing_ids = await _get_listing_ids_for_alert(db, alert)
    if not listing_ids:
        return None

    since = datetime.now(timezone.utc) - timedelta(days=7)

    for lid in listing_ids:
        result = await db.execute(
            select(ListingSnapshot)
            .where(
                ListingSnapshot.listing_id == lid,
                ListingSnapshot.captured_at >= since,
                ListingSnapshot.conversion_rate.isnot(None),
            )
            .order_by(ListingSnapshot.captured_at.desc())
        )
        snaps = result.scalars().all()
        if not snaps:
            continue

        snaps_with_conv = [s for s in snaps if s.conversion_rate]
        if not snaps_with_conv:
            continue
        avg_conversion = sum(
            float(s.conversion_rate) for s in snaps_with_conv
        ) / len(snaps_with_conv)

        if Decimal(str(avg_conversion)) < threshold:
            # Busca título do listing
            listing_result = await db.execute(
                select(Listing).where(Listing.id == lid)
            )
            listing = listing_result.scalar_one_or_none()
            title = listing.mlb_id if listing else str(lid)
            return (
                f"Alerta de conversão: {title} com conversão média de "
                f"{avg_conversion:.2f}% nos últimos 7 dias "
                f"(abaixo do limite de {threshold}%)"
            )

    return None


async def _check_stock_below(db: AsyncSession, alert: AlertConfig) -> str | None:
    """Verifica se o estoque atual está abaixo do threshold."""
    from app.vendas.models import Listing, ListingSnapshot

    threshold = int(alert.threshold or 0)
    listing_ids = await _get_listing_ids_for_alert(db, alert)
    if not listing_ids:
        return None

    for lid in listing_ids:
        # Pega o snapshot mais recente
        result = await db.execute(
            select(ListingSnapshot)
            .where(ListingSnapshot.listing_id == lid)
            .order_by(ListingSnapshot.captured_at.desc())
            .limit(1)
        )
        snap = result.scalar_one_or_none()
        if snap is None:
            continue

        if snap.stock < threshold:
            listing_result = await db.execute(
                select(Listing).where(Listing.id == lid)
            )
            listing = listing_result.scalar_one_or_none()
            title = listing.mlb_id if listing else str(lid)
            return (
                f"Alerta de estoque: {title} com apenas {snap.stock} unidades "
                f"(abaixo do limite de {threshold} unidades)"
            )

    return None


async def _check_no_sales_days(db: AsyncSession, alert: AlertConfig) -> str | None:
    """Verifica se houve 0 vendas pelos últimos N dias (threshold = N dias)."""
    from app.vendas.models import Listing, ListingSnapshot

    days_limit = int(alert.threshold or 3)
    listing_ids = await _get_listing_ids_for_alert(db, alert)
    if not listing_ids:
        return None

    since = datetime.now(timezone.utc) - timedelta(days=days_limit)

    for lid in listing_ids:
        result = await db.execute(
            select(ListingSnapshot)
            .where(
                ListingSnapshot.listing_id == lid,
                ListingSnapshot.captured_at >= since,
            )
            .order_by(ListingSnapshot.captured_at.desc())
        )
        snaps = result.scalars().all()

        if not snaps:
            continue

        total_sales = sum(s.sales_today for s in snaps)
        if total_sales == 0:
            listing_result = await db.execute(
                select(Listing).where(Listing.id == lid)
            )
            listing = listing_result.scalar_one_or_none()
            title = listing.mlb_id if listing else str(lid)
            return (
                f"Alerta de vendas: {title} sem nenhuma venda nos últimos "
                f"{days_limit} dias"
            )

    return None


async def _check_competitor_price_change(
    db: AsyncSession, alert: AlertConfig
) -> str | None:
    """
    Verifica se algum concorrente alterou preço nas últimas 24h.
    Compara o snapshot mais recente com o anterior.
    """
    from app.concorrencia.models import Competitor, CompetitorSnapshot
    from app.vendas.models import Listing

    listing_ids = await _get_listing_ids_for_alert(db, alert)
    if not listing_ids:
        return None

    since = datetime.now(timezone.utc) - timedelta(hours=24)

    for lid in listing_ids:
        comp_result = await db.execute(
            select(Competitor).where(
                Competitor.listing_id == lid,
                Competitor.is_active == True,  # noqa: E712
            )
        )
        competitors = comp_result.scalars().all()

        for comp in competitors:
            # Pega os 2 snapshots mais recentes
            snaps_result = await db.execute(
                select(CompetitorSnapshot)
                .where(CompetitorSnapshot.competitor_id == comp.id)
                .order_by(CompetitorSnapshot.captured_at.desc())
                .limit(2)
            )
            snaps = snaps_result.scalars().all()

            if len(snaps) < 2:
                continue

            latest, previous = snaps[0], snaps[1]
            # Só verifica se o snapshot mais recente é das últimas 24h
            if latest.captured_at < since:
                continue

            if latest.price != previous.price:
                listing_result = await db.execute(
                    select(Listing).where(Listing.id == lid)
                )
                listing = listing_result.scalar_one_or_none()
                my_mlb = listing.mlb_id if listing else str(lid)
                diff = float(latest.price) - float(previous.price)
                direction = "subiu" if diff > 0 else "baixou"
                return (
                    f"Alerta de concorrente: {comp.mlb_id} {direction} de "
                    f"R$ {float(previous.price):.2f} para R$ {float(latest.price):.2f} "
                    f"(anúncio monitorado: {my_mlb})"
                )

    return None


async def _check_competitor_price_below(
    db: AsyncSession, alert: AlertConfig
) -> str | None:
    """Verifica se algum concorrente está vendendo abaixo de R$ X (threshold)."""
    from app.concorrencia.models import Competitor, CompetitorSnapshot
    from app.vendas.models import Listing

    price_limit = Decimal(str(alert.threshold or 0))
    listing_ids = await _get_listing_ids_for_alert(db, alert)
    if not listing_ids:
        return None

    for lid in listing_ids:
        comp_result = await db.execute(
            select(Competitor).where(
                Competitor.listing_id == lid,
                Competitor.is_active == True,  # noqa: E712
            )
        )
        competitors = comp_result.scalars().all()

        for comp in competitors:
            # Snapshot mais recente
            snap_result = await db.execute(
                select(CompetitorSnapshot)
                .where(CompetitorSnapshot.competitor_id == comp.id)
                .order_by(CompetitorSnapshot.captured_at.desc())
                .limit(1)
            )
            snap = snap_result.scalar_one_or_none()
            if snap is None:
                continue

            if snap.price < price_limit:
                listing_result = await db.execute(
                    select(Listing).where(Listing.id == lid)
                )
                listing = listing_result.scalar_one_or_none()
                my_mlb = listing.mlb_id if listing else str(lid)
                return (
                    f"Alerta de preço: {comp.mlb_id} está vendendo a "
                    f"R$ {float(snap.price):.2f}, abaixo do limite de "
                    f"R$ {float(price_limit):.2f} "
                    f"(anúncio monitorado: {my_mlb})"
                )

    return None
