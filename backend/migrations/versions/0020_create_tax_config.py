"""Create tax_config table for Simples Nacional tax configuration

Revision ID: 0020
Revises: 0019
Create Date: 2026-03-23 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tax_configs",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="User who owns this tax config",
        ),
        sa.Column(
            "regime",
            sa.String(50),
            nullable=False,
            server_default="simples_nacional",
            comment="Regime tributario: simples_nacional, lucro_presumido, lucro_real",
        ),
        sa.Column(
            "faixa_anual",
            sa.Numeric(15, 2),
            nullable=False,
            comment="Faixa de faturamento anual em R$",
        ),
        sa.Column(
            "aliquota_efetiva",
            sa.Numeric(8, 6),
            nullable=False,
            comment="Aliquota efetiva/percentual de imposto (ex: 0.04 para 4%)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_tax_configs_user_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", name="uq_tax_configs_user_id"),
        sa.Index("idx_tax_configs_user_id", "user_id"),
    )


def downgrade() -> None:
    op.drop_table("tax_configs")
