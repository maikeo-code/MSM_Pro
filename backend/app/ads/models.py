import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AdCampaign(Base):
    __tablename__ = "ad_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ml_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ml_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="ID da campanha no ML"
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", comment="active | paused"
    )
    daily_budget: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    roas_target: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True, comment="Meta de ROAS configurada"
    )
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
    snapshots: Mapped[list["AdSnapshot"]] = relationship(
        "AdSnapshot", back_populates="campaign", cascade="all, delete-orphan"
    )
    ml_account: Mapped["MLAccount"] = relationship("MLAccount")  # type: ignore[name-defined]

    __table_args__ = (
        UniqueConstraint("ml_account_id", "campaign_id", name="uq_ad_campaign_account_campaign"),
    )

    def __repr__(self) -> str:
        return f"<AdCampaign id={self.id} campaign_id={self.campaign_id} name={self.name[:30]}>"


class AdSnapshot(Base):
    __tablename__ = "ad_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ad_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    spend: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    attributed_sales: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attributed_revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    organic_sales: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    roas: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True, comment="Return on ad spend"
    )
    acos: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True, comment="Advertising cost of sales %"
    )
    cpc: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True, comment="Cost per click"
    )
    ctr: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True, comment="Click through rate %"
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relacionamentos
    campaign: Mapped["AdCampaign"] = relationship("AdCampaign", back_populates="snapshots")

    __table_args__ = (
        UniqueConstraint("campaign_id", "date", name="uq_ad_snapshot_campaign_date"),
    )

    def __repr__(self) -> str:
        return f"<AdSnapshot campaign_id={self.campaign_id} date={self.date}>"
