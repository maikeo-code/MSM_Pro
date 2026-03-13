import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ReputationSnapshot(Base):
    """Snapshot diario da reputacao do vendedor no Mercado Livre."""
    __tablename__ = "reputation_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ml_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ml_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Nivel do vendedor: "1_red", "2_orange", "3_yellow", "4_light_green", "5_green"
    seller_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Status power seller: "gold", "platinum", "silver", null
    power_seller_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Metricas penalizadoras (em percentual, ex: 0.07 = 0.07%)
    claims_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    mediations_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    cancellations_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    late_shipments_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)

    # Dados de transacoes (periodo de 60 dias)
    total_sales_60d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_sales_60d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_revenue_60d: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Campos extras da API
    claims_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mediations_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cancellations_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    late_shipments_value: Mapped[int | None] = mapped_column(Integer, nullable=True)

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relacionamento
    ml_account: Mapped["MLAccount"] = relationship("MLAccount")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return (
            f"<ReputationSnapshot account={self.ml_account_id} "
            f"level={self.seller_level} at={self.captured_at}>"
        )
