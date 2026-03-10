from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=500)
    cost: Decimal = Field(ge=0, decimal_places=2)
    unit: str = Field(default="un", max_length=50)
    notes: str | None = None


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=500)
    cost: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    unit: str | None = Field(default=None, max_length=50)
    notes: str | None = None
    is_active: bool | None = None


class ProductOut(BaseModel):
    id: UUID
    user_id: UUID
    sku: str
    name: str
    cost: Decimal
    unit: str
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
