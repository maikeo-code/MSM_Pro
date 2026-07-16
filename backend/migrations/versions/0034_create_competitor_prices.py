"""Create competitor_prices table (contrato flat lido pelo OAA)

Revision ID: 0034_competitor_prices
Revises: 0033_snapshot_day_unique
Create Date: 2026-07-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0034_competitor_prices"
down_revision: Union[str, None] = "0033_snapshot_day_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "competitor_prices",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("id_ml", sa.String(50), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("sold_quantity", sa.Integer(), nullable=True),
        sa.Column("available_quantity", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(30), nullable=True),
        sa.Column(
            "is_buy_box", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("id_ml", "day", name="uq_competitor_prices_id_ml_day"),
    )
    op.create_index(
        "ix_competitor_prices_id_ml", "competitor_prices", ["id_ml"]
    )


def downgrade() -> None:
    op.drop_index("ix_competitor_prices_id_ml", table_name="competitor_prices")
    op.drop_table("competitor_prices")
