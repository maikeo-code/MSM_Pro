from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ReputationSnapshotOut(BaseModel):
    id: UUID
    ml_account_id: UUID
    seller_level: str | None = None
    power_seller_status: str | None = None
    claims_rate: Decimal | None = None
    mediations_rate: Decimal | None = None
    cancellations_rate: Decimal | None = None
    late_shipments_rate: Decimal | None = None
    total_sales_60d: int | None = None
    completed_sales_60d: int | None = None
    total_revenue_60d: Decimal | None = None
    claims_value: int | None = None
    mediations_value: int | None = None
    cancellations_value: int | None = None
    late_shipments_value: int | None = None
    captured_at: datetime

    model_config = {"from_attributes": True}


class ReputationThresholdsOut(BaseModel):
    """Limites de nivel por KPI para exibicao no frontend."""
    claims: float = 3.0          # Reclamacoes: max 3%
    mediations: float = 2.0      # Mediações: max 2%
    cancellations: float = 2.0   # Cancelamentos: max 2%
    late_shipments: float = 15.0  # Atrasos envio: max 15%


class HealthDimensionItem(BaseModel):
    """Score de saude para uma dimensao especifica da reputacao."""
    dimension: str                           # "claims", "mediations", "cancellations", "late_shipments"
    rate: float                              # Taxa atual em %
    status: Literal["good", "warning", "critical"]
    threshold_good: float                    # Limite para status 'good' em %
    threshold_warning: float                 # Limite para status 'warning' em %


class ReputationCurrentOut(BaseModel):
    """Resposta da reputacao atual com campos formatados para o frontend."""
    ml_account_id: UUID
    nickname: str | None = None
    seller_level: str | None = None
    power_seller_status: str | None = None
    # Metricas como percentuais formatados
    claims_rate: float = 0.0
    mediations_rate: float = 0.0
    cancellations_rate: float = 0.0
    late_shipments_rate: float = 0.0
    # Valores absolutos
    claims_value: int = 0
    mediations_value: int = 0
    cancellations_value: int = 0
    late_shipments_value: int = 0
    # Dados de 60 dias
    total_sales_60d: int = 0
    completed_sales_60d: int = 0
    total_revenue_60d: float = 0.0
    captured_at: datetime | None = None
    # Thresholds de nivel para comparacao visual
    thresholds: ReputationThresholdsOut = ReputationThresholdsOut()
    # Score de saude por dimensao (granularidade por KPI)
    health_by_dimension: list[HealthDimensionItem] = []

    model_config = {"from_attributes": True}


# ─── Simulador de Risco de Rebaixamento ──────────────────────────────────────

class RiskItem(BaseModel):
    """Resultado de risco para um KPI especifico."""
    kpi: str                                  # "claims", "mediations", etc.
    label: str                                # Legenda amigavel
    current_rate: float                       # Taxa atual em %
    threshold: float                          # Limite para perda de nivel em %
    current_count: int                        # Ocorrencias atuais calculadas
    max_allowed: int                          # Max permitido antes de rebaixar
    buffer: int                               # Folga = max_allowed - current_count
    risk_level: Literal["critical", "warning", "safe", "no_data"]


class ReputationRiskOut(BaseModel):
    """Resposta do simulador de risco de rebaixamento."""
    ml_account_id: UUID
    total_sales_60d: int
    items: list[RiskItem]
