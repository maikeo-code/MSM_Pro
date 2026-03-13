"""create ad_campaigns, ad_snapshots and orders tables

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-12 22:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- ad_campaigns ---
    op.create_table(
        "ad_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ml_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ml_accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("campaign_id", sa.String(100), nullable=False, index=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("daily_budget", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column(
            "roas_target",
            sa.Numeric(8, 4),
            nullable=True,
            comment="Meta de ROAS configurada",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "ml_account_id", "campaign_id", name="uq_ad_campaign_account_campaign"
        ),
    )

    # --- ad_snapshots ---
    op.create_table(
        "ad_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ad_campaigns.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("date", sa.Date(), nullable=False, index=True),
        sa.Column("impressions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("spend", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("attributed_sales", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "attributed_revenue", sa.Numeric(12, 2), nullable=False, server_default="0"
        ),
        sa.Column("organic_sales", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "roas",
            sa.Numeric(8, 4),
            nullable=True,
            comment="Return on ad spend",
        ),
        sa.Column(
            "acos",
            sa.Numeric(8, 4),
            nullable=True,
            comment="Advertising cost of sales %",
        ),
        sa.Column(
            "cpc",
            sa.Numeric(8, 4),
            nullable=True,
            comment="Cost per click",
        ),
        sa.Column(
            "ctr",
            sa.Numeric(8, 4),
            nullable=True,
            comment="Click through rate %",
        ),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "campaign_id", "date", name="uq_ad_snapshot_campaign_date"
        ),
    )

    # --- orders ---
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ml_order_id",
            sa.String(100),
            nullable=False,
            unique=True,
            index=True,
            comment="ID do pedido no ML",
        ),
        sa.Column(
            "ml_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ml_accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "listing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("listings.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("mlb_id", sa.String(50), nullable=False, index=True),
        sa.Column("buyer_nickname", sa.String(255), nullable=False, server_default=""),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column(
            "sale_fee",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
            comment="Tarifa de venda R$",
        ),
        sa.Column(
            "shipping_cost",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
            comment="Frete R$",
        ),
        sa.Column(
            "net_amount",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
            comment="Valor liquido a receber",
        ),
        sa.Column(
            "payment_status",
            sa.String(30),
            nullable=False,
            server_default="pending",
            comment="approved | pending | refunded",
        ),
        sa.Column(
            "shipping_status",
            sa.String(50),
            nullable=False,
            server_default="to_be_agreed",
            comment="to_be_agreed | pending | shipped | delivered",
        ),
        sa.Column("order_date", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("payment_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("orders")
    op.drop_table("ad_snapshots")
    op.drop_table("ad_campaigns")
