"""Create price_recommendations and daily_report_logs tables

Revision ID: 0016
Revises: 0015
Create Date: 2026-03-19 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── price_recommendations ────────────────────────────────────────────
    op.create_table(
        "price_recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "listing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("listings.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # Dados do momento
        sa.Column("current_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("suggested_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("price_change_pct", sa.Numeric(8, 2), nullable=False),
        # Analise IA
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("confidence", sa.String(10), nullable=False),
        sa.Column("risk_level", sa.String(10), nullable=False),
        sa.Column("urgency", sa.String(20), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        # Score breakdown
        sa.Column("score", sa.Numeric(8, 4), nullable=True),
        sa.Column("score_breakdown", postgresql.JSON(), nullable=True),
        # Metricas no momento
        sa.Column("conversion_today", sa.Numeric(8, 4), nullable=True),
        sa.Column("conversion_7d", sa.Numeric(8, 4), nullable=True),
        sa.Column("visits_today", sa.Integer(), nullable=True),
        sa.Column("visits_7d", sa.Integer(), nullable=True),
        sa.Column("sales_today", sa.Integer(), nullable=True),
        sa.Column("sales_7d", sa.Integer(), nullable=True),
        sa.Column("stock", sa.Integer(), nullable=True),
        sa.Column("stock_days_projection", sa.Numeric(8, 2), nullable=True),
        sa.Column("estimated_daily_sales", sa.Numeric(8, 2), nullable=True),
        sa.Column("estimated_daily_profit", sa.Numeric(12, 2), nullable=True),
        # Health Score
        sa.Column("health_score", sa.Integer(), nullable=True),
        # Concorrencia
        sa.Column("competitor_avg_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("competitor_min_price", sa.Numeric(12, 2), nullable=True),
        # Status
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="pending"
        ),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_price", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "price_change_log_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("price_change_logs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Metadados
        sa.Column(
            "ai_model",
            sa.String(50),
            nullable=False,
            server_default="claude-sonnet-4-6",
        ),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # Constraints
        sa.UniqueConstraint(
            "listing_id", "report_date", name="uq_recommendation_listing_date"
        ),
    )

    # Indices compostos para price_recommendations
    op.create_index(
        "idx_price_rec_user_date",
        "price_recommendations",
        ["user_id", sa.text("report_date DESC")],
    )
    op.create_index(
        "idx_price_rec_status",
        "price_recommendations",
        ["status"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    # ── daily_report_logs ────────────────────────────────────────────────
    op.create_table(
        "daily_report_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("total_listings", sa.Integer(), nullable=False),
        sa.Column("recommendations_count", sa.Integer(), nullable=False),
        sa.Column(
            "increase_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "decrease_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "hold_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "email_sent", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ai_model_used", sa.String(50), nullable=True),
        sa.Column("ai_cost_estimate", sa.Numeric(8, 4), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # Constraints
        sa.UniqueConstraint(
            "user_id", "report_date", name="uq_report_user_date"
        ),
    )

    # Indice composto para daily_report_logs
    op.create_index(
        "idx_report_log_user",
        "daily_report_logs",
        ["user_id", sa.text("report_date DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_report_log_user", table_name="daily_report_logs")
    op.drop_table("daily_report_logs")

    op.drop_index("idx_price_rec_status", table_name="price_recommendations")
    op.drop_index("idx_price_rec_user_date", table_name="price_recommendations")
    op.drop_table("price_recommendations")
