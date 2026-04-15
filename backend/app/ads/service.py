import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

# Timezone BRT (UTC-3)
BRT = timezone(timedelta(hours=-3))

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
    """Busca campanha + snapshots dos ultimos N dias.

    Tema 3: summary usa APENAS o snapshot mais recente (dados ja sao
    acumulados pelo sync_ads_from_ml). A lista completa de snapshots
    continua no response para possivel timeline visual.
    """
    result = await db.execute(
        select(AdCampaign).where(AdCampaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        return None

    # Filtra snapshots no banco (evita carregar ALL snapshots em memoria)
    cutoff = datetime.now(BRT).date() - timedelta(days=days)
    snaps_result = await db.execute(
        select(AdSnapshot)
        .where(
            AdSnapshot.campaign_id == campaign_id,
            AdSnapshot.date >= cutoff,
        )
        .order_by(AdSnapshot.date)
    )
    snapshots = list(snaps_result.scalars().all())

    # Usa APENAS o snapshot mais recente para o summary
    # (evita duplicar valores agregados — ver docstring acima).
    latest = snapshots[-1] if snapshots else None

    if latest is not None:
        total_spend = latest.spend or Decimal("0")
        total_revenue = latest.attributed_revenue or Decimal("0")
        total_clicks = latest.clicks or 0
        total_impressions = latest.impressions or 0
    else:
        total_spend = Decimal("0")
        total_revenue = Decimal("0")
        total_clicks = 0
        total_impressions = 0

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
        "latest_snapshot_date": latest.date.isoformat() if latest else None,
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

    Tema 3 — CORRECAO DO BUG DE DADOS ACUMULADOS:

    A API ML de Product Ads v2 retorna metricas JA AGREGADAS por periodo
    (nao por dia). O sync_ads_from_ml armazena uma linha em AdSnapshot com
    date=hoje contendo os totais do periodo inteiro.

    Codigo antigo: somava TODOS os snapshots dos ultimos N dias, o que
    multiplica o valor (cada snapshot ja era 30d acumulado, somar 7 deles
    = 210d de dados fantasmas). Isso causava valores absurdos no dashboard.

    Correcao: usar o snapshot MAIS RECENTE por campanha. Cada snapshot
    ja representa as metricas do periodo solicitado no sync.

    user_id garante isolamento multi-tenant: so retorna campanhas do owner.
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
            period_days=period,
        )

    campaign_ids = [c.id for c in campaigns]

    # Busca o snapshot MAIS RECENTE de cada campanha (dentro do periodo).
    # Cada snapshot ja contem os valores agregados do periodo sincronizado,
    # portanto nao devemos somar multiplos snapshots da mesma campanha.
    cutoff = date.today() - timedelta(days=period)
    snaps_result = await db.execute(
        select(AdSnapshot)
        .where(
            AdSnapshot.campaign_id.in_(campaign_ids),
            AdSnapshot.date >= cutoff,
        )
        .order_by(AdSnapshot.campaign_id, desc(AdSnapshot.date))
    )
    all_snaps = list(snaps_result.scalars().all())

    # Dedupe: fica so o mais recente por campanha
    latest_by_campaign: dict = {}
    for s in all_snaps:
        if s.campaign_id not in latest_by_campaign:
            latest_by_campaign[s.campaign_id] = s

    latest_snapshots = list(latest_by_campaign.values())

    total_spend = sum(
        (s.spend or Decimal("0") for s in latest_snapshots), Decimal("0")
    )
    total_revenue = sum(
        (s.attributed_revenue or Decimal("0") for s in latest_snapshots),
        Decimal("0"),
    )
    total_clicks = sum(s.clicks or 0 for s in latest_snapshots)
    total_impressions = sum(s.impressions or 0 for s in latest_snapshots)

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
        period_days=period,
    )


async def sync_ads_from_ml(
    db: AsyncSession,
    ml_client,
    ml_account,
) -> dict:
    """
    Busca campanhas de Product Ads via API ML e salva/atualiza no banco.

    Fluxo:
    1. Obtém advertiser_id via GET /advertising/advertisers?product_id=PADS (Api-Version: 2)
    2. Busca campanhas via GET /advertising/advertisers/{id}/product_ads/campaigns (Api-Version: 2)
    3. Upsert de campanhas + snapshots agregados no banco

    Se a conta não tiver acesso a Product Ads (advertiser_id=None), retorna vazio.
    """
    synced_campaigns = 0
    synced_snapshots = 0

    # Passo 1: obtém advertiser_id (específico da API de Product Ads v2)
    advertiser_id = await ml_client.get_advertiser_id()
    if not advertiser_id:
        logger.info(
            f"Conta {ml_account.id} não tem acesso a Product Ads — nenhuma campanha sincronizada."
        )
        return {
            "synced_campaigns": 0,
            "synced_snapshots": 0,
            "ml_account_id": str(ml_account.id),
            "advertiser_id": None,
        }

    logger.info(f"Conta {ml_account.id}: advertiser_id={advertiser_id}")

    # Passo 2: busca campanhas com métricas dos últimos 30 dias
    today = datetime.now(BRT).date()
    date_from = (today - timedelta(days=30)).isoformat()
    date_to = today.isoformat()

    campaigns_data = await ml_client.get_product_ads_campaigns(advertiser_id, date_from, date_to)
    logger.info(
        f"Conta {ml_account.id}: {len(campaigns_data)} campanhas retornadas pela API ML."
    )

    for campaign_raw in campaigns_data:
        # O campo de ID da campanha pode ser "id" ou "campaign_id"
        campaign_id_str = str(
            campaign_raw.get("campaign_id") or campaign_raw.get("id", "")
        )
        if not campaign_id_str:
            continue

        campaign_name = campaign_raw.get("name", campaign_id_str)
        campaign_status = campaign_raw.get("status", "active")

        # daily_budget pode vir em centavos ou em reais dependendo da API
        raw_budget = campaign_raw.get("daily_budget", 0) or 0
        daily_budget = Decimal(str(raw_budget))

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
                name=campaign_name,
                status=campaign_status,
                daily_budget=daily_budget,
                roas_target=None,
            )
            db.add(campaign)
            synced_campaigns += 1
        else:
            campaign.name = campaign_name
            campaign.status = campaign_status
            campaign.daily_budget = daily_budget

        await db.flush()

        # Passo 3: extrai métricas da resposta (a API retorna métricas agregadas por campanha)
        # A API de Product Ads v2 retorna métricas inline na campanha (não separado por dia)
        metrics_data = campaign_raw.get("metrics", {}) or {}

        # Campos da API v2: prints, clicks, cost, roas, acos, units_quantity, total_amount
        impressions = int(metrics_data.get("prints", 0) or 0)
        clicks = int(metrics_data.get("clicks", 0) or 0)
        # "cost" = gasto em publicidade (em reais)
        spend = Decimal(str(metrics_data.get("cost", 0) or 0))
        attributed_sales = int(metrics_data.get("units_quantity", 0) or 0)
        attributed_revenue = Decimal(str(metrics_data.get("total_amount", 0) or 0))

        # ROAS e ACOS podem vir direto da API ou calculados
        roas_raw = metrics_data.get("roas")
        acos_raw = metrics_data.get("acos")

        roas = Decimal(str(roas_raw)) if roas_raw is not None else (
            (attributed_revenue / spend) if spend > 0 else None
        )
        acos = Decimal(str(acos_raw)) if acos_raw is not None else (
            (spend / attributed_revenue * 100) if attributed_revenue > 0 else None
        )
        cpc_raw = metrics_data.get("cpc")
        cpc = Decimal(str(cpc_raw)) if cpc_raw is not None else (
            (spend / clicks) if clicks > 0 else None
        )
        ctr_raw = metrics_data.get("ctr")
        ctr = Decimal(str(ctr_raw)) if ctr_raw is not None else (
            (Decimal(clicks) / impressions * 100) if impressions > 0 else None
        )

        # Upsert snapshot para hoje (snapshot agregado do período)
        snap_result = await db.execute(
            select(AdSnapshot).where(
                AdSnapshot.campaign_id == campaign.id,
                AdSnapshot.date == today,
            )
        )
        snap = snap_result.scalar_one_or_none()

        if not snap:
            snap = AdSnapshot(
                id=uuid.uuid4(),
                campaign_id=campaign.id,
                date=today,
                impressions=impressions,
                clicks=clicks,
                spend=spend,
                attributed_sales=attributed_sales,
                attributed_revenue=attributed_revenue,
                organic_sales=0,
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
        "advertiser_id": advertiser_id,
    }
