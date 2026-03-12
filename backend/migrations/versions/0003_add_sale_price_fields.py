"""add original_price and sale_price to listings

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('listings', sa.Column('original_price', sa.Numeric(12, 2), nullable=True))
    op.add_column('listings', sa.Column('sale_price', sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column('listings', 'sale_price')
    op.drop_column('listings', 'original_price')
