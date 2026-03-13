"""Create sync_logs table

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-13 00:01:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sync_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("task_name", sa.String(100), nullable=False),
        sa.Column(
            "ml_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ml_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="running",
        ),
        sa.Column("items_processed", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("items_failed", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    )

    # Índice para consultas de histórico por task_name
    op.create_index(
        "ix_sync_logs_task_started",
        "sync_logs",
        ["task_name", sa.text("started_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_sync_logs_task_started", table_name="sync_logs")
    op.drop_table("sync_logs")
