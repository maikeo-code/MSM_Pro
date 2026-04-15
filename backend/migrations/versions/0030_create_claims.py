"""Create claims table for Tema 5 — persistencia de reclamacoes.

Revision ID: 0030_create_claims
Revises: 0029_buyer_bigint
Create Date: 2026-04-11 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0030_create_claims"
down_revision = "0029_buyer_bigint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ml_claim_id", sa.String(50), nullable=False),
        sa.Column(
            "ml_account_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("claim_type", sa.String(30), nullable=False, server_default="reclamacao"),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("ml_order_id", sa.String(50), nullable=True),
        sa.Column("mlb_id", sa.String(50), nullable=True),
        sa.Column("item_title", sa.String(500), nullable=True),
        sa.Column("buyer_id", sa.BigInteger(), nullable=True),
        sa.Column("buyer_nickname", sa.String(100), nullable=True),
        sa.Column("date_created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("date_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_type", sa.String(50), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("ml_suggestion", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSON(), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
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
        ),
        sa.ForeignKeyConstraint(
            ["ml_account_id"], ["ml_accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ml_claim_id", name="uq_claims_ml_claim_id"),
    )

    op.create_index(
        "ix_claims_ml_account_status",
        "claims",
        ["ml_account_id", "status"],
    )
    op.create_index("ix_claims_mlb_id", "claims", ["mlb_id"])
    op.create_index("ix_claims_date_created", "claims", ["date_created"])


def downgrade() -> None:
    op.drop_index("ix_claims_date_created", table_name="claims")
    op.drop_index("ix_claims_mlb_id", table_name="claims")
    op.drop_index("ix_claims_ml_account_status", table_name="claims")
    op.drop_table("claims")
