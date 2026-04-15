from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class AdSnapshotOut(BaseModel):
    id: UUID
    campaign_id: UUID
    date: date
    impressions: int
    clicks: int
    spend: Decimal
    attributed_sales: int
    attributed_revenue: Decimal
    organic_sales: int
    roas: Decimal | None
    acos: Decimal | None
    cpc: Decimal | None
    ctr: Decimal | None
    captured_at: datetime

    model_config = {"from_attributes": True}


class AdCampaignOut(BaseModel):
    id: UUID
    ml_account_id: UUID
    campaign_id: str
    name: str
    status: str
    daily_budget: Decimal
    roas_target: Decimal | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdsDashboardOut(BaseModel):
    """Resumo agregado de todas as campanhas de uma conta ML."""
    total_spend: Decimal
    total_revenue: Decimal
    total_clicks: int
    total_impressions: int
    roas_geral: Decimal | None
    acos_geral: Decimal | None
    campaigns: list[AdCampaignOut]
    # Tema 3: expoe o periodo consultado (evita confusao com "acumulado")
    period_days: int = 30


class AdsCampaignDetailOut(BaseModel):
    """Detalhe de uma campanha + timeline de snapshots."""
    campaign: AdCampaignOut
    snapshots: list[AdSnapshotOut]
    summary: dict
