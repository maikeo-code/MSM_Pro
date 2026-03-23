"""SQLAlchemy models para o módulo de Atendimento."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.models import User
from app.core.database import Base


class ResponseTemplate(Base):
    """Template de resposta reutilizável para atendimento."""

    __tablename__ = "response_templates"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text(), nullable=False)
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="general",
        comment="general | pergunta | reclamacao | devolucao | mensagem",
    )
    variables: Mapped[dict | None] = mapped_column(
        JSON(), nullable=True, default=None, comment="List of variable names"
    )
    use_count: Mapped[int] = mapped_column(
        Integer(), nullable=False, default=0, comment="Times used"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="response_templates")
