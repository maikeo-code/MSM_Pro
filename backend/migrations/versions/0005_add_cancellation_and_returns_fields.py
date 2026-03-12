"""add cancellation revenue and returns fields to listing_snapshots

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "listing_snapshots",
        sa.Column(
            "cancelled_revenue",
            sa.Numeric(12, 2),
            nullable=True,
            server_default="0",
        ),
    )
    op.add_column(
        "listing_snapshots",
        sa.Column(
            "returns_count",
            sa.Integer(),
            nullable=True,
            server_default="0",
        ),
    )
    op.add_column(
        "listing_snapshots",
        sa.Column(
            "returns_revenue",
            sa.Numeric(12, 2),
            nullable=True,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("listing_snapshots", "returns_revenue")
    op.drop_column("listing_snapshots", "returns_count")
    op.drop_column("listing_snapshots", "cancelled_revenue")
