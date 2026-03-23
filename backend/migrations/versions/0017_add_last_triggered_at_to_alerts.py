"""Add last_triggered_at to alert_configs for cooldown tracking

Revision ID: 0017
Revises: 0016
Create Date: 2026-03-23 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add last_triggered_at column to track when an alert was last triggered
    # Used for 24h cooldown to prevent duplicate alert notifications
    op.add_column(
        "alert_configs",
        sa.Column(
            "last_triggered_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp do último disparo (usado para cooldown de 24h)",
        ),
    )


def downgrade() -> None:
    op.drop_column("alert_configs", "last_triggered_at")
