"""add order metrics to listing_snapshots

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "listing_snapshots",
        sa.Column("orders_count", sa.Integer(), nullable=True, server_default="0"),
    )
    op.add_column(
        "listing_snapshots",
        sa.Column("revenue", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "listing_snapshots",
        sa.Column("avg_selling_price", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "listing_snapshots",
        sa.Column("cancelled_orders", sa.Integer(), nullable=True, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("listing_snapshots", "cancelled_orders")
    op.drop_column("listing_snapshots", "avg_selling_price")
    op.drop_column("listing_snapshots", "revenue")
    op.drop_column("listing_snapshots", "orders_count")
