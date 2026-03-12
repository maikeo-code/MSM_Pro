"""
Schemas Pydantic para o módulo de alertas.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

# Tipos suportados de alerta
AlertType = Literal[
    "conversion_below",
    "stock_below",
    "competitor_price_change",
    "no_sales_days",
    "competitor_price_below",
]

# Canais de notificação suportados
AlertChannel = Literal["email", "webhook"]

# Tipos que obrigam threshold
_THRESHOLD_REQUIRED: set[str] = {
    "conversion_below",
    "stock_below",
    "no_sales_days",
    "competitor_price_below",
}


class AlertConfigCreate(BaseModel):
    alert_type: AlertType
    listing_id: UUID | None = None
    product_id: UUID | None = None
    threshold: Decimal | None = Field(
        default=None,
        description=(
            "Valor limite. Obrigatório para: conversion_below (%), "
            "stock_below (unidades), no_sales_days (dias), "
            "competitor_price_below (R$)."
        ),
    )
    channel: AlertChannel = "email"

    @model_validator(mode="after")
    def validate_threshold_required(self) -> "AlertConfigCreate":
        if self.alert_type in _THRESHOLD_REQUIRED and self.threshold is None:
            raise ValueError(
                f"O campo 'threshold' é obrigatório para o tipo '{self.alert_type}'"
            )
        return self

    @model_validator(mode="after")
    def validate_listing_or_product(self) -> "AlertConfigCreate":
        if self.listing_id is None and self.product_id is None:
            raise ValueError(
                "É necessário informar 'listing_id' ou 'product_id' para criar um alerta"
            )
        return self


class AlertConfigUpdate(BaseModel):
    threshold: Decimal | None = None
    channel: AlertChannel | None = None
    is_active: bool | None = None


class AlertConfigOut(BaseModel):
    id: UUID
    user_id: UUID
    listing_id: UUID | None
    product_id: UUID | None
    alert_type: str
    threshold: Decimal | None
    channel: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertEventOut(BaseModel):
    id: UUID
    alert_config_id: UUID
    message: str
    triggered_at: datetime
    sent_at: datetime | None

    model_config = {"from_attributes": True}
