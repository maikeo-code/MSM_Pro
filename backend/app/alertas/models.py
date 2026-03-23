import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Tipos: conversion_below, stock_below, competitor_price_change,
    #        no_sales_days, competitor_price_below
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    threshold: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="email")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")

    # Relacionamentos
    user: Mapped["User"] = relationship("User", back_populates="alert_configs")  # type: ignore[name-defined]
    listing: Mapped["Listing | None"] = relationship("Listing", back_populates="alert_configs")  # type: ignore[name-defined]
    product: Mapped["Product | None"] = relationship("Product", back_populates="alert_configs")  # type: ignore[name-defined]
    events: Mapped[list["AlertEvent"]] = relationship(
        "AlertEvent", back_populates="alert_config", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AlertConfig id={self.id} type={self.alert_type}>"


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    alert_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alert_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relacionamentos
    alert_config: Mapped["AlertConfig"] = relationship("AlertConfig", back_populates="events")

    def __repr__(self) -> str:
        return f"<AlertEvent id={self.id} config_id={self.alert_config_id}>"
