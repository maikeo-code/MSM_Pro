import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Competitor(Base):
    __tablename__ = "competitors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mlb_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    seller_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    seller_nickname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    thumbnail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relacionamentos
    listing: Mapped["Listing"] = relationship("Listing", back_populates="competitors")  # type: ignore[name-defined]
    snapshots: Mapped[list["CompetitorSnapshot"]] = relationship(
        "CompetitorSnapshot", back_populates="competitor", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Competitor id={self.id} mlb_id={self.mlb_id}>"


class CompetitorSnapshot(Base):
    __tablename__ = "competitor_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    competitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("competitors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    visits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sales_delta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sold_quantity: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=0,
        comment="sold_quantity acumulado do item ML no momento do snapshot"
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relacionamentos
    competitor: Mapped["Competitor"] = relationship("Competitor", back_populates="snapshots")

    def __repr__(self) -> str:
        return f"<CompetitorSnapshot competitor_id={self.competitor_id} price={self.price}>"
