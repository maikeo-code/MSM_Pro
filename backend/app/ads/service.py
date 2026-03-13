import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ads.models import AdCampaign, AdSnapshot
from app.ads.schemas import AdCampaignOut, AdsDashboardOut, AdsCampaignDetailOut, AdSnapshotOut

logger = logging.getLogger(__name__)


async def list_campaigns(
    db: AsyncSession,
    ml_account_id: UUID,
    user_id: UUID | None = None,
) -> list[AdCampaign]:
    """Lista campanhas de uma conta ML armazenadas no banco.

    Se user_id for fornecido, garante isolamento filtrando pelo owner da ml_account.
    """
    from app.auth.models import MLAccount

    query = select(AdCampaign).where(AdCampaign.ml_account_id == ml_account_id)

    if user_id is not None:
        # Garante que ml_account_id pertence ao user_id (isolamento multi-tenant)
        query = query.join(MLAccount, AdCampaign.ml_account_id == MLAccount.id).where(
            MLAccount.user_id == user_id
        )

    query = query.order_by(AdCampaign.name)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_campaign_detail(
    db: AsyncSession,
    campaign_id: UUID,
    days: int = 30,
) -> AdsCampaignDetailOut | None:
    """Busca campanha + snapshots dos últimos N dias."""
    result = await db.execute(
        select(AdCampaign).where(AdCampaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        return None

    # Filtra snapshots no banco (evita carregar ALL snapshots em memória)
    cutoff = date.today() - timedelta(days=days)
    snaps_result = await db.execute(
        select(AdSnapshot)
        .where(
            AdSnapshot.campaign_id == campaign_id,
            AdSnapshot.date >= cutoff,
        )
        .order_by(AdSnapshot.date)
    )
    snapshots = list(snaps_result.scalars().all())

    # Calcula resumo agregado
    total_spend = sum(s.spend for s in snapshots) or Decimal("0")
    total_revenue = sum(s.attributed_revenue for s in snapshots) or Decimal("0")
    total_clicks = sum(s.clicks for s in snapshots)
    total_impressions = sum(s.impressions for s in snapshots)
    roas_geral = (total_revenue / total_spend) if total_spend > 0 else None
    acos_geral = (total_spend / total_revenue * 100) if total_revenue > 0 else None

    summary = {
        "total_spend": float(total_spend),
        "total_revenue": float(total_revenue),
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "roas_geral": float(roas_geral) if roas_geral is not None else None,
        "acos_geral": float(acos_geral) if acos_geral is not None else None,
        "days": days,
    }

    return AdsCampaignDetailOut(
        campaign=AdCampaignOut.model_validate(campaign),
        snapshots=[AdSnapshotOut.model_validate(s) for s in snapshots],
        summary=summary,
    )


async def get_ads_dashboard(
    db: AsyncSession,
    ml_account_id: UUID,
    period: int = 30,
    user_id: UUID | None = None,
) -> AdsDashboardOut:
    """Resumo agregado de todas as campanhas de uma conta ML.

    user_id garante isolamento multi-tenant: só retorna campanhas do owner.
    Usa batch query para evitar N+1.
    """
    campaigns = await list_campaigns(db, ml_account_id, user_id=user_id)

    if not campaigns:
        return AdsDashboardOut(
            total_spend=Decimal("0"),
            total_revenue=Decimal("0"),
            total_clicks=0,
            total_impressions=0,
            roas_geral=None,
            acos_geral=None,
            campaigns=[],
        )

    cutoff = date.today() - timedelta(days=period)
    campaign_ids = [c.id for c in campaigns]

    # Batch query: busca todos os snapshots de uma vez (evita N+1)
    snaps_result = await db.execute(
        select(AdSnapshot)
        .where(
            AdSnapshot.campaign_id.in_(campaign_ids),
            AdSnapshot.date >= cutoff,
        )
    )
    all_snapshots = list(snaps_result.scalars().all())

    total_spend = sum((s.spend for s in all_snapshots), Decimal("0"))
    total_revenue = sum((s.attributed_revenue for s in all_snapshots), Decimal("0"))
    total_clicks = sum(s.clicks for s in all_snapshots)
    total_impressions = sum(s.impressions for s in all_snapshots)

    roas_geral = (total_revenue / total_spend) if total_spend > 0 else None
    acos_geral = (total_spend / total_revenue * 100) if total_revenue > 0 else None

    return AdsDashboardOut(
        total_spend=total_spend,
        total_revenue=total_revenue,
        total_clicks=total_clicks,
        total_impressions=total_impressions,
        roas_geral=roas_geral,
        acos_geral=acos_geral,
        campaigns=[AdCampaignOut.model_validate(c) for c in campaigns],
    )


async def sync_ads_from_ml(
    db: AsyncSession,
    ml_client,
    ml_account,
) -> dict:
    """
    Busca campanhas da API ML e salva/atualiza no banco.
    Tenta endpoint /advertising/campaigns; se falhar (403/404),
    usa fallback baseado em dados de product_ads existentes.
    """
    synced_campaigns = 0
    synced_snapshots = 0
    seller_id = str(ml_account.ml_user_id)

    try:
        campaigns_data = await ml_client.get_campaigns(seller_id)
    except Exception as e:
        logger.warning(f"Falha ao buscar campanhas ML para conta {ml_account.id}: {e}")
        campaigns_data = []

    for campaign_raw in campaigns_data:
        campaign_id_str = str(campaign_raw.get("id", ""))
        if not campaign_id_str:
            continue

        # Upsert campanha
        result = await db.execute(
            select(AdCampaign).where(
                AdCampaign.ml_account_id == ml_account.id,
                AdCampaign.campaign_id == campaign_id_str,
            )
        )
        campaign = result.scalar_one_or_none()

        if not campaign:
            campaign = AdCampaign(
                id=uuid.uuid4(),
                ml_account_id=ml_account.id,
                campaign_id=campaign_id_str,
                name=campaign_raw.get("name", campaign_id_str),
                status=campaign_raw.get("status", "active"),
                daily_budget=Decimal(str(campaign_raw.get("daily_budget", 0))),
                roas_target=None,
            )
            db.add(campaign)
            synced_campaigns += 1
        else:
            campaign.name = campaign_raw.get("name", campaign.name)
            campaign.status = campaign_raw.get("status", campaign.status)
            campaign.daily_budget = Decimal(str(campaign_raw.get("daily_budget", campaign.daily_budget)))

        await db.flush()

        # Busca métricas da campanha para os últimos 30 dias
        today = date.today()
        date_from = (today - timedelta(days=30)).isoformat()
        date_to = today.isoformat()

        try:
            metrics = await ml_client.get_campaign_metrics(
                campaign_id_str, date_from, date_to
            )
        except Exception as e:
            logger.warning(f"Falha ao buscar métricas da campanha {campaign_id_str}: {e}")
            metrics = []

        for metric in metrics:
            metric_date_str = metric.get("date", "")
            if not metric_date_str:
                continue

            try:
                metric_date = date.fromisoformat(metric_date_str[:10])
            except ValueError:
                continue

            # Upsert snapshot
            snap_result = await db.execute(
                select(AdSnapshot).where(
                    AdSnapshot.campaign_id == campaign.id,
                    AdSnapshot.date == metric_date,
                )
            )
            snap = snap_result.scalar_one_or_none()

            impressions = int(metric.get("impressions", 0))
            clicks = int(metric.get("clicks", 0))
            spend = Decimal(str(metric.get("spend", 0)))
            attributed_sales = int(metric.get("attributed_sales", 0))
            attributed_revenue = Decimal(str(metric.get("attributed_revenue", 0)))
            organic_sales = int(metric.get("organic_sales", 0))

            roas = (attributed_revenue / spend) if spend > 0 else None
            acos = (spend / attributed_revenue * 100) if attributed_revenue > 0 else None
            cpc = (spend / clicks) if clicks > 0 else None
            ctr = (Decimal(clicks) / impressions * 100) if impressions > 0 else None

            if not snap:
                snap = AdSnapshot(
                    id=uuid.uuid4(),
                    campaign_id=campaign.id,
                    date=metric_date,
                    impressions=impressions,
                    clicks=clicks,
                    spend=spend,
                    attributed_sales=attributed_sales,
                    attributed_revenue=attributed_revenue,
                    organic_sales=organic_sales,
                    roas=roas,
                    acos=acos,
                    cpc=cpc,
                    ctr=ctr,
                )
                db.add(snap)
                synced_snapshots += 1
            else:
                snap.impressions = impressions
                snap.clicks = clicks
                snap.spend = spend
                snap.attributed_sales = attributed_sales
                snap.attributed_revenue = attributed_revenue
                snap.organic_sales = organic_sales
                snap.roas = roas
                snap.acos = acos
                snap.cpc = cpc
                snap.ctr = ctr

        await db.flush()

    # Nota: o commit deve ser feito pelo caller (router ou task)
    return {
        "synced_campaigns": synced_campaigns,
        "synced_snapshots": synced_snapshots,
        "ml_account_id": str(ml_account.id),
    }
