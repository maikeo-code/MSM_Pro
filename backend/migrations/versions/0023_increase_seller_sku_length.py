"""increase seller_sku to 500 chars for variation concatenation

Revision ID: 0023_increase_seller_sku_length
Revises: 0022_create_user_preferences
Create Date: 2026-03-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0023_increase_seller_sku_length"
down_revision = "0022_create_user_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "listings",
        "seller_sku",
        existing_type=sa.String(100),
        type_=sa.String(500),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "listings",
        "seller_sku",
        existing_type=sa.String(500),
        type_=sa.String(100),
        existing_nullable=True,
    )
