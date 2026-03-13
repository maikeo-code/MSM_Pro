"""
Modelos SQLAlchemy compartilhados entre módulos.

Coloca aqui modelos que não pertencem a um único módulo de domínio
e são usados transversalmente (ex: SyncLog, auditoria, etc).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SyncLog(Base):
    """
    Registro de execução de cada Celery task de sincronização.

    Campos:
    - task_name: nome da task (ex: "sync_all_snapshots")
    - ml_account_id: conta ML envolvida (opcional — tasks globais deixam NULL)
    - status: "running" | "success" | "failed"
    - items_processed: quantos itens foram processados com sucesso
    - items_failed: quantos itens falharam durante o processamento
    - error_message: mensagem de erro (apenas quando status = "failed")
    - started_at: momento em que a task começou (UTC)
    - finished_at: momento em que a task terminou (UTC)
    - duration_ms: duração total em milissegundos
    """

    __tablename__ = "sync_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    task_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    ml_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ml_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    items_processed: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    items_failed: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer(), nullable=True)
