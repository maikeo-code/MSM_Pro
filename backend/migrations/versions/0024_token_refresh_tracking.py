"""Add token refresh tracking to MLAccount

Revision ID: 0024_token_refresh_tracking
Revises: 0023_increase_seller_sku_length
Create Date: 2026-04-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0024_token_refresh_tracking"
down_revision = "0023_increase_seller_sku_length"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ml_accounts",
        sa.Column(
            "last_token_refresh_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "ml_accounts",
        sa.Column(
            "token_refresh_failures",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "ml_accounts",
        sa.Column(
            "needs_reauth",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("ml_accounts", "needs_reauth")
    op.drop_column("ml_accounts", "token_refresh_failures")
    op.drop_column("ml_accounts", "last_token_refresh_at")
