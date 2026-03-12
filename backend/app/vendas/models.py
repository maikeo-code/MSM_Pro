import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    ml_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ml_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mlb_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    listing_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="classico"
    )  # classico | premium | full
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    original_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    permalink: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relacionamentos
    user: Mapped["User"] = relationship("User", back_populates="listings")  # type: ignore[name-defined]
    product: Mapped["Product"] = relationship("Product", back_populates="listings")  # type: ignore[name-defined]
    ml_account: Mapped["MLAccount"] = relationship("MLAccount", back_populates="listings")  # type: ignore[name-defined]
    snapshots: Mapped[list["ListingSnapshot"]] = relationship(
        "ListingSnapshot", back_populates="listing", cascade="all, delete-orphan"
    )
    competitors: Mapped[list] = relationship(
        "Competitor", back_populates="listing", cascade="all, delete-orphan"
    )
    alert_configs: Mapped[list] = relationship(
        "AlertConfig", back_populates="listing"
    )

    def __repr__(self) -> str:
        return f"<Listing id={self.id} mlb_id={self.mlb_id} title={self.title[:30]}>"


class ListingSnapshot(Base):
    __tablename__ = "listing_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    visits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sales_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conversion_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    orders_count: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    avg_selling_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    cancelled_orders: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relacionamentos
    listing: Mapped["Listing"] = relationship("Listing", back_populates="snapshots")

    def __repr__(self) -> str:
        return f"<ListingSnapshot listing_id={self.listing_id} price={self.price} at={self.captured_at}>"
