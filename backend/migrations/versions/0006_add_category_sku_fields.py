"""add category_id and seller_sku to listings

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "listings",
        sa.Column("category_id", sa.String(50), nullable=True),
    )
    op.add_column(
        "listings",
        sa.Column("seller_sku", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("listings", "seller_sku")
    op.drop_column("listings", "category_id")
