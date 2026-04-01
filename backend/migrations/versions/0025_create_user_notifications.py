"""Create user_notifications table

Revision ID: 0025_create_user_notifications
Revises: 0024_token_refresh_tracking
Create Date: 2026-04-01 11:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0025_create_user_notifications"
down_revision = "0024_token_refresh_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("action_url", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_notifications_user_id",
        "user_notifications",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_notifications_type",
        "user_notifications",
        ["type"],
        unique=False,
    )
    op.create_index(
        "ix_user_notifications_is_read",
        "user_notifications",
        ["is_read"],
        unique=False,
    )
    op.create_index(
        "ix_user_notifications_created_at",
        "user_notifications",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_notifications_created_at",
        table_name="user_notifications",
    )
    op.drop_index(
        "ix_user_notifications_is_read",
        table_name="user_notifications",
    )
    op.drop_index(
        "ix_user_notifications_type",
        table_name="user_notifications",
    )
    op.drop_index(
        "ix_user_notifications_user_id",
        table_name="user_notifications",
    )
    op.drop_table("user_notifications")
