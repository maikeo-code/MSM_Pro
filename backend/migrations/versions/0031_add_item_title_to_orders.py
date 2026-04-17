"""Add item_title column to orders table.

Revision ID: 0031_item_title_orders
Revises: 0030_create_claims
Create Date: 2026-04-17 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0031_item_title_orders"
down_revision = "0030_create_claims"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("item_title", sa.String(length=500), nullable=True),
    )
    # Backfill: popula item_title de pedidos existentes usando listings.title
    op.execute(
        """
        UPDATE orders
        SET item_title = listings.title
        FROM listings
        WHERE orders.mlb_id = listings.mlb_id
          AND orders.item_title IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("orders", "item_title")
