"""SQLAlchemy models para o módulo de Perguntas Q&A."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.models import MLAccount
from app.core.database import Base


class Question(Base):
    """Pergunta recebida do Mercado Livre, persistida localmente para histórico e análise IA."""

    __tablename__ = "questions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    ml_question_id: Mapped[int] = mapped_column(
        Integer(), nullable=False, unique=True, comment="ID da pergunta no ML"
    )
    ml_account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ml_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    listing_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("listings.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK para listing local se existir",
    )
    mlb_id: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Ex: MLB1234567890"
    )
    item_title: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="Título do anúncio"
    )
    item_thumbnail: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="URL da thumbnail do produto"
    )
    text: Mapped[str] = mapped_column(
        Text(), nullable=False, comment="Texto da pergunta"
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="UNANSWERED",
        comment="UNANSWERED | ANSWERED | CLOSED_UNANSWERED | UNDER_REVIEW",
    )
    buyer_id: Mapped[int | None] = mapped_column(
        Integer(), nullable=True, comment="ML user ID do comprador"
    )
    buyer_nickname: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Nickname do comprador no ML"
    )
    date_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="Data de criação no ML"
    )
    answer_text: Mapped[str | None] = mapped_column(
        Text(), nullable=True, comment="Texto da resposta enviada"
    )
    answer_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Data da resposta"
    )
    answer_source: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="manual | ai | template | ml_direct",
    )
    ai_suggestion_text: Mapped[str | None] = mapped_column(
        Text(), nullable=True, comment="Última sugestão IA gerada"
    )
    ai_suggestion_confidence: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="high | medium | low"
    )
    ai_suggested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Data da sugestão IA"
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Última sincronização com ML",
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

    # Relationships
    ml_account: Mapped[MLAccount] = relationship("MLAccount")
    answers: Mapped[list["QuestionAnswer"]] = relationship(
        "QuestionAnswer", back_populates="question", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_questions_ml_account_id_status", "ml_account_id", "status"),
        Index("ix_questions_mlb_id", "mlb_id"),
        Index("ix_questions_date_created", "date_created", postgresql_using="btree"),
    )


class QuestionAnswer(Base):
    """Resposta a uma pergunta, com metadados de envio."""

    __tablename__ = "question_answers"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    question_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text(), nullable=False, comment="Texto da resposta")
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending | sent | failed",
    )
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="manual",
        comment="manual | ai | template",
    )
    template_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("response_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Quando foi enviada"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text(), nullable=True, comment="Erro se falhou no envio"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    question: Mapped[Question] = relationship("Question", back_populates="answers")

    __table_args__ = (Index("ix_question_answers_question_id", "question_id"),)


class QASuggestionLog(Base):
    """Log de sugestões IA geradas para perguntas."""

    __tablename__ = "qa_suggestion_logs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    question_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=True,
    )
    question_text: Mapped[str] = mapped_column(
        Text(), nullable=False, comment="Texto original da pergunta"
    )
    suggested_answer: Mapped[str] = mapped_column(
        Text(), nullable=False, comment="Resposta sugerida pela IA"
    )
    question_type: Mapped[str | None] = mapped_column(
        String(30), nullable=True, comment="Classificação (compatibilidade, envio, etc)"
    )
    confidence: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="high | medium | low"
    )
    was_used: Mapped[bool] = mapped_column(
        nullable=False, default=False, comment="Se o usuário usou a sugestão"
    )
    was_edited: Mapped[bool] = mapped_column(
        nullable=False, default=False, comment="Se editou antes de usar"
    )
    tokens_used: Mapped[int | None] = mapped_column(
        Integer(), nullable=True, comment="Tokens consumidos pela API"
    )
    latency_ms: Mapped[int | None] = mapped_column(
        Integer(), nullable=True, comment="Tempo de resposta da IA em ms"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_qa_suggestion_logs_question_id", "question_id"),
        Index("ix_qa_suggestion_logs_created_at", "created_at"),
    )
