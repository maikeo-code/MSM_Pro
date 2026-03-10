"""Initial migration — cria todas as tabelas do Sprint 1

Revision ID: 0001
Revises:
Create Date: 2026-03-10 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- ml_accounts ---
    op.create_table(
        "ml_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ml_user_id", sa.String(100), nullable=False),
        sa.Column("nickname", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("access_token", sa.String(2000), nullable=True),
        sa.Column("refresh_token", sa.String(2000), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ml_accounts_user_id", "ml_accounts", ["user_id"])

    # --- products ---
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku", sa.String(100), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("cost", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("unit", sa.String(50), nullable=False, server_default=sa.text("'un'")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "sku", name="uq_products_user_sku"),
    )
    op.create_index("ix_products_user_id", "products", ["user_id"])

    # --- listings ---
    op.create_table(
        "listings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ml_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mlb_id", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column(
            "listing_type", sa.String(20), nullable=False, server_default=sa.text("'classico'")
        ),
        sa.Column("price", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default=sa.text("'active'")
        ),
        sa.Column("permalink", sa.Text(), nullable=True),
        sa.Column("thumbnail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ml_account_id"], ["ml_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mlb_id", name="uq_listings_mlb_id"),
    )
    op.create_index("ix_listings_user_id", "listings", ["user_id"])
    op.create_index("ix_listings_product_id", "listings", ["product_id"])
    op.create_index("ix_listings_ml_account_id", "listings", ["ml_account_id"])
    op.create_index("ix_listings_mlb_id", "listings", ["mlb_id"])

    # --- listing_snapshots ---
    op.create_table(
        "listing_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("visits", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("sales_today", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("questions", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("stock", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("conversion_rate", sa.Numeric(8, 4), nullable=True),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_listing_snapshots_listing_id", "listing_snapshots", ["listing_id"])
    op.create_index("ix_listing_snapshots_captured_at", "listing_snapshots", ["captured_at"])

    # --- competitors ---
    op.create_table(
        "competitors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mlb_id", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("seller_id", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_competitors_listing_id", "competitors", ["listing_id"])
    op.create_index("ix_competitors_mlb_id", "competitors", ["mlb_id"])

    # --- competitor_snapshots ---
    op.create_table(
        "competitor_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("competitor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("visits", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("sales_delta", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["competitor_id"], ["competitors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_competitor_snapshots_competitor_id", "competitor_snapshots", ["competitor_id"]
    )
    op.create_index(
        "ix_competitor_snapshots_captured_at", "competitor_snapshots", ["captured_at"]
    )

    # --- alert_configs ---
    op.create_table(
        "alert_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("threshold", sa.Numeric(12, 4), nullable=True),
        sa.Column(
            "channel", sa.String(20), nullable=False, server_default=sa.text("'email'")
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alert_configs_user_id", "alert_configs", ["user_id"])
    op.create_index("ix_alert_configs_listing_id", "alert_configs", ["listing_id"])
    op.create_index("ix_alert_configs_product_id", "alert_configs", ["product_id"])

    # --- alert_events ---
    op.create_table(
        "alert_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_config_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["alert_config_id"], ["alert_configs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_alert_events_alert_config_id", "alert_events", ["alert_config_id"]
    )


def downgrade() -> None:
    op.drop_table("alert_events")
    op.drop_table("alert_configs")
    op.drop_table("competitor_snapshots")
    op.drop_table("competitors")
    op.drop_table("listing_snapshots")
    op.drop_table("listings")
    op.drop_table("products")
    op.drop_table("ml_accounts")
    op.drop_table("users")
