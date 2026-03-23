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
# Helper: cálculo automático de severidade
# ============================================================


def _calculate_severity(alert_type: str, threshold: Decimal | None) -> str:
    """Calcula severidade automática baseada no tipo e threshold."""
    threshold_val = float(threshold) if threshold is not None else 0

    # Severidade crítica
    if alert_type == "stock_below" and threshold_val <= 3:
        return "critical"
    if alert_type == "no_sales_days" and threshold_val >= 5:
        return "critical"

    # Severidade warning
    if alert_type == "stock_below" and threshold_val <= 10:
        return "warning"
    if alert_type == "competitor_price_change":
        return "warning"

    # Padrão: info (oportunidades, alertas leves)
    if alert_type in ("visits_spike", "conversion_improved"):
        return "info"

    # Padrão para outros: warning
    return "warning"


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

    # Determina severidade automática se não fornecida
    severity = payload.severity or _calculate_severity(payload.alert_type, payload.threshold)

    alert = AlertConfig(
        user_id=user_id,
        listing_id=payload.listing_id,
        product_id=payload.product_id,
        alert_type=payload.alert_type,
        threshold=payload.threshold,
        channel=payload.channel,
        severity=severity,
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
    if payload.severity is not None:
        alert.severity = payload.severity

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
        .limit(500)
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

    Implementa deduplicação temporal: verifica se o alerta foi disparado
    nos últimos 24h (cooldown) para evitar notificações duplicadas.
    """
    try:
        message = await _check_condition(db, alert)
    except Exception as exc:  # noqa: BLE001
        logger.error("Erro ao avaliar alerta %s: %s", alert.id, exc)
        return None

    if message is None:
        return None

    # --- Verifica cooldown de 24h ---
    now = datetime.now(timezone.utc)
    if alert.last_triggered_at is not None:
        time_since_last = now - alert.last_triggered_at
        cooldown = timedelta(hours=24)
        if time_since_last < cooldown:
            logger.info(
                "Alerta %s ainda em cooldown (disparado há %s). "
                "Ignorando para evitar duplicação.",
                alert.id,
                time_since_last,
            )
            return None

    # --- Cria evento e atualiza timestamp ---
    event = AlertEvent(
        alert_config_id=alert.id,
        message=message,
    )
    db.add(event)

    # Atualiza last_triggered_at para o cooldown funcionar na próxima avaliação
    alert.last_triggered_at = now

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

    # --- visits_spike (oportunidade) ---
    if atype == "visits_spike":
        return await _check_visits_spike(db, alert)

    # --- conversion_improved (oportunidade) ---
    if atype == "conversion_improved":
        return await _check_conversion_improved(db, alert)

    # --- stockout_forecast (previsão) ---
    if atype == "stockout_forecast":
        return await _check_stockout_forecast(db, alert)

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


async def _check_visits_spike(db: AsyncSession, alert: AlertConfig) -> str | None:
    """
    Verifica se as visitas de hoje estão >150% da média dos últimos 7 dias.
    Tipo: visits_spike (oportunidade, severity=info)
    """
    from app.vendas.models import Listing, ListingSnapshot

    listing_ids = await _get_listing_ids_for_alert(db, alert)
    if not listing_ids:
        return None

    since = datetime.now(timezone.utc) - timedelta(days=7)
    now = datetime.now(timezone.utc)

    for lid in listing_ids:
        # Snapshots dos últimos 7 dias
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

        # Média de visitas (excluindo hoje)
        seven_days_ago = now - timedelta(days=7)
        older_snaps = [s for s in snaps if s.captured_at < (now - timedelta(days=1))]
        if not older_snaps:
            continue

        avg_visits = sum(s.visits_today for s in older_snaps) / len(older_snaps)

        # Snapshot de hoje
        today_snap = next((s for s in snaps if s.captured_at.date() == now.date()), None)
        if today_snap is None:
            continue

        if today_snap.visits_today > avg_visits * 1.5:
            listing_result = await db.execute(
                select(Listing).where(Listing.id == lid)
            )
            listing = listing_result.scalar_one_or_none()
            title = listing.mlb_id if listing else str(lid)
            return (
                f"Oportunidade: {title} com pico de visitas! "
                f"{int(today_snap.visits_today)} visitas hoje "
                f"(média: {int(avg_visits)} visitas/dia)"
            )

    return None


async def _check_conversion_improved(db: AsyncSession, alert: AlertConfig) -> str | None:
    """
    Verifica se a conversão subiu >20% vs média dos últimos 7 dias.
    Tipo: conversion_improved (oportunidade, severity=info)
    """
    from app.vendas.models import Listing, ListingSnapshot

    listing_ids = await _get_listing_ids_for_alert(db, alert)
    if not listing_ids:
        return None

    since = datetime.now(timezone.utc) - timedelta(days=7)
    now = datetime.now(timezone.utc)

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

        # Média de conversão (últimos 7 dias, excluindo hoje)
        older_snaps = [s for s in snaps if s.captured_at < (now - timedelta(days=1)) and s.conversion_rate]
        if not older_snaps:
            continue

        avg_conversion = sum(
            float(s.conversion_rate) for s in older_snaps
        ) / len(older_snaps)

        # Conversão de hoje
        today_snap = next((s for s in snaps if s.captured_at.date() == now.date()), None)
        if today_snap is None or today_snap.conversion_rate is None:
            continue

        today_conversion = float(today_snap.conversion_rate)
        improvement = (today_conversion - avg_conversion) / max(avg_conversion, 0.01) * 100

        if improvement > 20:
            listing_result = await db.execute(
                select(Listing).where(Listing.id == lid)
            )
            listing = listing_result.scalar_one_or_none()
            title = listing.mlb_id if listing else str(lid)
            return (
                f"Oportunidade: {title} com conversão melhorada! "
                f"{today_conversion:.2f}% hoje vs {avg_conversion:.2f}% "
                f"(+{improvement:.1f}%)"
            )

    return None


async def _check_stockout_forecast(db: AsyncSession, alert: AlertConfig) -> str | None:
    """
    Verifica se o estoque vai acabar em menos de threshold dias.
    Tipo: stockout_forecast (severidade baseada em urgência)

    Lógica:
    - Calcula velocidade média de vendas dos últimos 14 dias
    - Estima dias até stockout = estoque_atual / velocidade_venda
    - Se < threshold, dispara alerta
    """
    from app.vendas.models import Listing, ListingSnapshot

    forecast_days = int(alert.threshold or 7)
    listing_ids = await _get_listing_ids_for_alert(db, alert)
    if not listing_ids:
        return None

    since = datetime.now(timezone.utc) - timedelta(days=14)

    for lid in listing_ids:
        # Snapshots dos últimos 14 dias
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

        # Calcula velocidade de venda média
        total_sales = sum(s.sales_today for s in snaps)
        days_with_data = len(snaps)
        if days_with_data == 0:
            continue

        avg_sales_per_day = total_sales / days_with_data

        # Snapshot mais recente (estoque atual)
        latest = snaps[0]
        current_stock = latest.stock

        if avg_sales_per_day <= 0:
            # Sem vendas, não há risco
            continue

        days_to_stockout = current_stock / avg_sales_per_day

        if days_to_stockout < forecast_days:
            listing_result = await db.execute(
                select(Listing).where(Listing.id == lid)
            )
            listing = listing_result.scalar_one_or_none()
            title = listing.mlb_id if listing else str(lid)
            return (
                f"Previsão de estoque: {title} acabará em {int(days_to_stockout)} dias "
                f"no ritmo atual ({avg_sales_per_day:.1f} un/dia, "
                f"{int(current_stock)} restantes)"
            )

    return None
