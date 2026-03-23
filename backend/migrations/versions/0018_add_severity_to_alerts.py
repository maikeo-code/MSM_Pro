"""Add severity field to alert_configs for alert prioritization

Revision ID: 0018
Revises: 0017
Create Date: 2026-03-23 14:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add severity column to alert_configs
    # Values: critical, warning, info
    # Default: warning
    op.add_column(
        "alert_configs",
        sa.Column(
            "severity",
            sa.String(20),
            nullable=False,
            server_default="warning",
            comment="Nível de severidade: critical, warning, info",
        ),
    )


def downgrade() -> None:
    op.drop_column("alert_configs", "severity")
