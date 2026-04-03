"""Add missing unique constraints to competitors and ml_accounts

Revision ID: 0027_unique_constraints
Revises: 0026_create_questions
Create Date: 2026-04-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0027_unique_constraints"
down_revision = "0026_create_questions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Unique constraint em competitors (listing_id, mlb_id)
    # Garante que o mesmo MLB externo nao seja vinculado mais de uma vez ao mesmo anuncio
    op.create_unique_constraint(
        "uq_competitors_listing_id_mlb_id",
        "competitors",
        ["listing_id", "mlb_id"],
    )

    # Unique constraint em ml_accounts (user_id, ml_user_id)
    # Garante que a mesma conta ML nao seja conectada mais de uma vez pelo mesmo usuario
    op.create_unique_constraint(
        "uq_ml_accounts_user_id_ml_user_id",
        "ml_accounts",
        ["user_id", "ml_user_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_ml_accounts_user_id_ml_user_id",
        "ml_accounts",
        type_="unique",
    )
    op.drop_constraint(
        "uq_competitors_listing_id_mlb_id",
        "competitors",
        type_="unique",
    )
