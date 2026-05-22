"""Add user_rating and user_comment to qa_suggestion_logs.

Revision ID: 0032_rating_qa_logs
Revises: 0031_item_title_orders
Create Date: 2026-04-22 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0032_rating_qa_logs"
down_revision = "0031_item_title_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "qa_suggestion_logs",
        sa.Column("user_rating", sa.Integer(), nullable=True),
    )
    op.add_column(
        "qa_suggestion_logs",
        sa.Column("user_comment", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("qa_suggestion_logs", "user_comment")
    op.drop_column("qa_suggestion_logs", "user_rating")
