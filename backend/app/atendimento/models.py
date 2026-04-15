"""SQLAlchemy models para o módulo de Atendimento."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.models import MLAccount, User
from app.core.database import Base


class Claim(Base):
    """Reclamacao/devolucao do Mercado Livre, persistida localmente (Tema 5).

    A API ML expoe claims via /v1/claims/search. Antes este modulo era
    read-only (buscava tudo em tempo real). Agora persistimos para:
    - Historico (aprender com solucoes usadas anteriormente)
    - Performance (nao depender de latencia/erros da API ML em cada request)
    - Enriquecer sugestoes IA com base de conhecimento local
    """

    __tablename__ = "claims"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    ml_claim_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        comment="ID do claim no ML",
    )
    ml_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ml_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    claim_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="reclamacao",
        comment="reclamacao | devolucao",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="open | opened | waiting_for_seller_response | closed | resolved",
    )
    reason: Mapped[str | None] = mapped_column(
        Text(), nullable=True, comment="reason_id/subject da reclamacao"
    )
    description: Mapped[str | None] = mapped_column(
        Text(), nullable=True, comment="descricao completa quando disponivel"
    )
    # Vinculo com order/listing
    ml_order_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="ID do pedido relacionado"
    )
    mlb_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="MLB do anuncio"
    )
    item_title: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    # Comprador
    buyer_id: Mapped[int | None] = mapped_column(
        BigInteger(), nullable=True
    )
    buyer_nickname: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    # Datas
    date_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Data de criacao no ML",
    )
    date_updated: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Resolucao
    resolution_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="refund | replace | partial_refund | kept | ml_suggested",
    )
    resolution_notes: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Como o vendedor resolveu (texto livre)",
    )
    ml_suggestion: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
        comment="Sugestao do ML sobre como resolver (quando presente no payload)",
    )
    # Payload completo para debug/auditoria
    raw_payload: Mapped[dict | None] = mapped_column(
        JSON(), nullable=True, comment="Payload bruto da API ML para referencia"
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    ml_account: Mapped[MLAccount] = relationship("MLAccount")

    __table_args__ = (
        Index("ix_claims_ml_account_status", "ml_account_id", "status"),
        Index("ix_claims_mlb_id", "mlb_id"),
        Index("ix_claims_date_created", "date_created"),
    )


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
