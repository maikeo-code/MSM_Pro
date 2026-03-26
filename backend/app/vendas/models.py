import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
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
    category_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    seller_sku: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sale_fee_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True, comment="Taxa real ML em R$ (via API listing_prices)"
    )
    sale_fee_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 6), nullable=True, comment="Taxa real ML em % (via API listing_prices)"
    )
    avg_shipping_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True, comment="Frete medio real extraido das orders"
    )
    permalink: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    repricing_rules: Mapped[list["RepricingRule"]] = relationship(
        "RepricingRule", back_populates="listing", cascade="all, delete-orphan"
    )
    price_change_logs: Mapped[list["PriceChangeLog"]] = relationship(
        "PriceChangeLog", back_populates="listing", cascade="all, delete-orphan"
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
    cancelled_revenue: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True, default=0)
    returns_count: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    returns_revenue: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True, default=0)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relacionamentos
    listing: Mapped["Listing"] = relationship("Listing", back_populates="snapshots")

    def __repr__(self) -> str:
        return f"<ListingSnapshot listing_id={self.listing_id} price={self.price} at={self.captured_at}>"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ml_order_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True,
        comment="ID do pedido no ML"
    )
    ml_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ml_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    mlb_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    buyer_nickname: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    sale_fee: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0, comment="Tarifa de venda R$"
    )
    shipping_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0, comment="Frete R$"
    )
    net_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0, comment="Valor liquido a receber"
    )
    payment_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending",
        comment="approved | pending | refunded"
    )
    shipping_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="to_be_agreed",
        comment="to_be_agreed | pending | shipped | delivered"
    )
    order_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    payment_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivery_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relacionamentos
    ml_account: Mapped["MLAccount"] = relationship("MLAccount")  # type: ignore[name-defined]
    listing: Mapped[Optional["Listing"]] = relationship("Listing")

    def __repr__(self) -> str:
        return f"<Order ml_order_id={self.ml_order_id} mlb_id={self.mlb_id} total={self.total_amount}>"


class PriceChangeLog(Base):
    __tablename__ = "price_change_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mlb_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    old_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    new_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="suggestion_apply",
        comment="Origem: suggestion_apply, manual, promotion, etc."
    )
    ml_api_response: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Resposta bruta da API ML (JSON)"
    )
    success: Mapped[bool] = mapped_column(
        nullable=False, default=True, comment="Se a alteracao foi aceita pela API ML"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relacionamentos
    listing: Mapped["Listing"] = relationship("Listing", back_populates="price_change_logs")
    user: Mapped["User"] = relationship("User")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<PriceChangeLog mlb_id={self.mlb_id} {self.old_price}->{self.new_price}>"


class RepricingRule(Base):
    __tablename__ = "repricing_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Tipos suportados: FIXED_MARKUP | COMPETITOR_DELTA | FLOOR_CEILING
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # FIXED_MARKUP: multiplicador sobre custo (ex: 1.4 = 40% markup)
    # COMPETITOR_DELTA: delta em R$ sobre preco do concorrente (ex: -2.00 = R$2 abaixo)
    # FLOOR_CEILING: usa min_price e max_price como limites
    value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    min_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    max_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_applied_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relacionamentos
    listing: Mapped["Listing"] = relationship("Listing", back_populates="repricing_rules")
    user: Mapped["User"] = relationship("User")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<RepricingRule id={self.id} listing_id={self.listing_id} type={self.rule_type} active={self.is_active}>"
