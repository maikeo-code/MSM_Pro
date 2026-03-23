import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TaxConfig(Base):
    """Configuração de regime tributário e alíquota para o usuário."""
    __tablename__ = "tax_configs"

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_tax_configs_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    regime: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="simples_nacional",
        comment="Regime tributario: simples_nacional, lucro_presumido, lucro_real",
    )
    faixa_anual: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        comment="Faixa de faturamento anual em R$",
    )
    aliquota_efetiva: Mapped[Decimal] = mapped_column(
        Numeric(8, 6),
        nullable=False,
        comment="Aliquota efetiva/percentual de imposto (ex: 0.04 para 4%)",
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
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<TaxConfig id={self.id} user_id={self.user_id} regime={self.regime} aliquota={self.aliquota_efetiva}>"
