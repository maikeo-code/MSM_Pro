"""Alter questions.buyer_id from Integer to BigInteger.

ML user IDs também excedem int32 (ex.: 2490612425).
Detectado pelo runtime-watcher no ciclo 457 após corrigir o
ml_question_id. Mesmo padrão.

Revision ID: 0029_buyer_bigint
Revises: 0028_questions_bigint
Create Date: 2026-04-08 00:45:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0029_buyer_bigint"
down_revision = "0028_questions_bigint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "questions",
        "buyer_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "questions",
        "buyer_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
