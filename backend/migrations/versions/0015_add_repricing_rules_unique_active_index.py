"""Add partial unique index on repricing_rules for active rules

Prevents race conditions on duplicate active rule checks by enforcing
uniqueness at the database level: only one active rule per (listing_id, rule_type).

Revision ID: 0015
Revises: 0014
Create Date: 2026-03-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX uq_repricing_active_rule
        ON repricing_rules (listing_id, rule_type)
        WHERE is_active = true
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_repricing_active_rule")
