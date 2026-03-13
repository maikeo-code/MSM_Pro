"""add sale_fee_amount, sale_fee_pct, avg_shipping_cost, quality_score to listings

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-12 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "listings",
        sa.Column(
            "sale_fee_amount",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
            comment="Taxa real ML em R$ (via API listing_prices)",
        ),
    )
    op.add_column(
        "listings",
        sa.Column(
            "sale_fee_pct",
            sa.Numeric(precision=8, scale=6),
            nullable=True,
            comment="Taxa real ML em % (via API listing_prices)",
        ),
    )
    op.add_column(
        "listings",
        sa.Column(
            "avg_shipping_cost",
            sa.Numeric(precision=10, scale=2),
            nullable=True,
            comment="Frete medio real extraido das orders",
        ),
    )
    op.add_column(
        "listings",
        sa.Column("quality_score", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("listings", "quality_score")
    op.drop_column("listings", "avg_shipping_cost")
    op.drop_column("listings", "sale_fee_pct")
    op.drop_column("listings", "sale_fee_amount")
