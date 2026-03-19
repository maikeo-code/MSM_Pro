import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PriceRecommendation(Base):
    __tablename__ = "price_recommendations"

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

    # Dados do momento
    current_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    suggested_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    price_change_pct: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)

    # Analise IA
    action: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="increase | decrease | hold"
    )
    confidence: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="high | medium | low"
    )
    risk_level: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="low | medium | high"
    )
    urgency: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="immediate | next_48h | monitor"
    )
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)

    # Score breakdown (formula Python)
    score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    score_breakdown: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="Ex: {conv_trend: 0.12, visit_trend: 0.05, ...}"
    )

    # Metricas no momento
    conversion_today: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    conversion_7d: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    visits_today: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visits_7d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sales_today: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sales_7d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stock_days_projection: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), nullable=True
    )
    estimated_daily_sales: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 2), nullable=True
    )
    estimated_daily_profit: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )

    # Health Score (0-100)
    health_score: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Score de saude do anuncio (0-100)"
    )

    # Concorrencia
    competitor_avg_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    competitor_min_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending | applied | dismissed | expired",
    )
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    applied_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    price_change_log_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("price_change_logs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Metadados
    ai_model: Mapped[str] = mapped_column(
        String(50), nullable=False, default="claude-sonnet-4-6"
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "listing_id", "report_date", name="uq_recommendation_listing_date"
        ),
    )

    # Relacionamentos
    listing: Mapped["Listing"] = relationship("Listing")  # type: ignore[name-defined]
    user: Mapped["User"] = relationship("User")  # type: ignore[name-defined]
    price_change_log: Mapped[Optional["PriceChangeLog"]] = relationship(  # type: ignore[name-defined]
        "PriceChangeLog"
    )

    def __repr__(self) -> str:
        return (
            f"<PriceRecommendation listing_id={self.listing_id} "
            f"action={self.action} suggested={self.suggested_price}>"
        )


class DailyReportLog(Base):
    __tablename__ = "daily_report_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_listings: Mapped[int] = mapped_column(Integer, nullable=False)
    recommendations_count: Mapped[int] = mapped_column(Integer, nullable=False)
    increase_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    decrease_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hold_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    email_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ai_model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_cost_estimate: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "report_date", name="uq_report_user_date"),
    )

    # Relacionamentos
    user: Mapped["User"] = relationship("User")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return (
            f"<DailyReportLog user_id={self.user_id} "
            f"date={self.report_date} recs={self.recommendations_count}>"
        )
