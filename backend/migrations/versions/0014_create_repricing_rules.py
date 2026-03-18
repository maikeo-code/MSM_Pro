"""Create repricing_rules table

Revision ID: 0014
Revises: 0013
Create Date: 2026-03-18 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "repricing_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "listing_id",
            UUID(as_uuid=True),
            sa.ForeignKey("listings.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # Tipos: FIXED_MARKUP | COMPETITOR_DELTA | FLOOR_CEILING
        sa.Column("rule_type", sa.String(50), nullable=False),
        # Valor generico: multiplicador (FIXED_MARKUP) ou delta R$ (COMPETITOR_DELTA)
        sa.Column("value", sa.Numeric(12, 2), nullable=True),
        # Limites de preco (FLOOR_CEILING)
        sa.Column("min_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("max_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_applied_price", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Indice para evitar regras duplicadas do mesmo tipo por anuncio ativo
    op.create_index(
        "ix_repricing_rules_listing_type",
        "repricing_rules",
        ["listing_id", "rule_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_repricing_rules_listing_type", table_name="repricing_rules")
    op.drop_table("repricing_rules")
