"""add sold_quantity to competitor_snapshots

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-12 20:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "competitor_snapshots",
        sa.Column("sold_quantity", sa.Integer(), nullable=True, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("competitor_snapshots", "sold_quantity")
