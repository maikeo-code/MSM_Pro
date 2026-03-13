"""create reputation_snapshots table

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-12 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reputation_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ml_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ml_accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("seller_level", sa.String(50), nullable=True),
        sa.Column("power_seller_status", sa.String(50), nullable=True),
        sa.Column("claims_rate", sa.Numeric(6, 4), nullable=True),
        sa.Column("mediations_rate", sa.Numeric(6, 4), nullable=True),
        sa.Column("cancellations_rate", sa.Numeric(6, 4), nullable=True),
        sa.Column("late_shipments_rate", sa.Numeric(6, 4), nullable=True),
        sa.Column("total_sales_60d", sa.Integer, nullable=True),
        sa.Column("completed_sales_60d", sa.Integer, nullable=True),
        sa.Column("total_revenue_60d", sa.Numeric(12, 2), nullable=True),
        sa.Column("claims_value", sa.Integer, nullable=True),
        sa.Column("mediations_value", sa.Integer, nullable=True),
        sa.Column("cancellations_value", sa.Integer, nullable=True),
        sa.Column("late_shipments_value", sa.Integer, nullable=True),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("reputation_snapshots")
