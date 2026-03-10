from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ListingCreate(BaseModel):
    product_id: UUID
    ml_account_id: UUID
    mlb_id: str = Field(min_length=3, max_length=50, pattern=r"^MLB-?\d+$")
    title: str = Field(min_length=1, max_length=500)
    listing_type: str = Field(default="classico", pattern=r"^(classico|premium|full)$")
    price: Decimal = Field(ge=0, decimal_places=2)
    permalink: str | None = None
    thumbnail: str | None = None


class ListingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    listing_type: str | None = Field(default=None, pattern=r"^(classico|premium|full)$")
    price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    status: str | None = None
    permalink: str | None = None
    thumbnail: str | None = None


class SnapshotOut(BaseModel):
    id: UUID
    listing_id: UUID
    price: Decimal
    visits: int
    sales_today: int
    questions: int
    stock: int
    conversion_rate: Decimal | None
    captured_at: datetime

    model_config = {"from_attributes": True}


class ListingOut(BaseModel):
    id: UUID
    user_id: UUID
    product_id: UUID
    ml_account_id: UUID
    mlb_id: str
    title: str
    listing_type: str
    price: Decimal
    status: str
    permalink: str | None
    thumbnail: str | None
    created_at: datetime
    updated_at: datetime
    last_snapshot: SnapshotOut | None = None

    model_config = {"from_attributes": True}


class MargemResult(BaseModel):
    preco: Decimal
    custo_sku: Decimal
    taxa_ml_pct: Decimal
    taxa_ml_valor: Decimal
    frete: Decimal
    margem_bruta: Decimal
    margem_pct: Decimal
    lucro: Decimal
    listing_type: str
