from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class CompetitorCreate(BaseModel):
    listing_id: UUID
    competitor_mlb_id: str = Field(min_length=3, max_length=50, pattern=r"^MLB-?\d+$")


class CompetitorOut(BaseModel):
    id: UUID
    listing_id: UUID
    mlb_id: str
    title: str | None
    seller_nickname: str | None
    thumbnail: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CompetitorSnapshotOut(BaseModel):
    id: UUID
    competitor_id: UUID
    price: Decimal
    visits: int
    sales_delta: int
    sold_quantity: int | None = None
    captured_at: datetime

    model_config = {"from_attributes": True}


class CompetitorHistoryItem(BaseModel):
    date: datetime
    price: Decimal
    sold_quantity: int | None = None
    sales_delta: int

    model_config = {"from_attributes": True}


class CompetitorHistoryOut(BaseModel):
    competitor_id: UUID
    mlb_id: str
    title: str | None
    days: int
    history: list[CompetitorHistoryItem]
