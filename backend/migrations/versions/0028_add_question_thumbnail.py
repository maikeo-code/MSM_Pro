"""Add item_thumbnail to questions table

Revision ID: 0028_add_question_thumbnail
Revises: 0027_add_missing_unique_constraints
Create Date: 2026-04-02 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0028_add_question_thumbnail"
down_revision = "0027_add_missing_unique_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "questions",
        sa.Column("item_thumbnail", sa.String(500), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("questions", "item_thumbnail")
