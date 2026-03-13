"""Add performance indexes for common queries

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-13 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Índice principal: snapshot por listing + data (DESC para "últimos N dias")
    op.create_index(
        "ix_snapshot_listing_date",
        "listing_snapshots",
        ["listing_id", sa.text("captured_at DESC")],
    )

    # Índice para orders por conta + data
    op.create_index(
        "ix_orders_account_date",
        "orders",
        ["ml_account_id", sa.text("created_at DESC")],
    )

    # Índice para competitor snapshots por concorrente + data
    op.create_index(
        "ix_comp_snapshot_date",
        "competitor_snapshots",
        ["competitor_id", sa.text("captured_at DESC")],
    )

    # Índice para orders por mlb_id + data (usado no heatmap e análise por anúncio)
    op.create_index(
        "ix_orders_mlb_date",
        "orders",
        ["mlb_id", sa.text("order_date DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_orders_mlb_date", table_name="orders")
    op.drop_index("ix_comp_snapshot_date", table_name="competitor_snapshots")
    op.drop_index("ix_orders_account_date", table_name="orders")
    op.drop_index("ix_snapshot_listing_date", table_name="listing_snapshots")
