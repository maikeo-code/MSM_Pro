"""Add seller_nickname and thumbnail to competitors for enrichment

Revision ID: 0019
Revises: 0018
Create Date: 2026-03-23 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add seller_nickname column to competitors
    op.add_column(
        "competitors",
        sa.Column(
            "seller_nickname",
            sa.String(255),
            nullable=True,
            comment="Nickname do vendedor concorrente (via API ML)",
        ),
    )

    # Add thumbnail column to competitors
    op.add_column(
        "competitors",
        sa.Column(
            "thumbnail",
            sa.String(500),
            nullable=True,
            comment="URL da imagem thumbnail do item concorrente",
        ),
    )


def downgrade() -> None:
    op.drop_column("competitors", "thumbnail")
    op.drop_column("competitors", "seller_nickname")
