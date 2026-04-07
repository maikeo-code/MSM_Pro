"""Alter questions.ml_question_id from Integer to BigInteger.

IDs novos do Mercado Livre excedem int32 (ex.: 13539001443) e
causavam DataError em todos os syncs de perguntas.

Revision ID: 0028_questions_bigint
Revises: 0027_unique_constraints
Create Date: 2026-04-07 16:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0028_questions_bigint"
down_revision = "0027_unique_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "questions",
        "ml_question_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "questions",
        "ml_question_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
