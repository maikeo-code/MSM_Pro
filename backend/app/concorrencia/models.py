import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
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


class CompetitorPrice(Base):
    """Preço diário de concorrentes — tabela FLAT (contrato lido pelo OAA).

    Denormalizada de propósito: 1 linha por (id_ml, day). Alimentada 1x/dia pela
    task collect_competitor_prices. `id_ml` pode ser item (MLB+10díg → /items/{id})
    ou catálogo (MLB 8díg ou MLBU… → /products/{id}, buy_box_winner → is_buy_box=true).
    Separada de Competitor/CompetitorSnapshot (que ligam a anúncios nossos); esta
    tabela é a fonte crua que o OAA consome exatamente nestas colunas.
    Ver [[feature-competitor-prices]].
    """

    __tablename__ = "competitor_prices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    id_ml: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    sold_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    available_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_buy_box: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("id_ml", "day", name="uq_competitor_prices_id_ml_day"),
    )

    def __repr__(self) -> str:
        return f"<CompetitorPrice id_ml={self.id_ml} day={self.day} price={self.price}>"
