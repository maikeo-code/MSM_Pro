"""Create response_templates table for Atendimento module.

Revision ID: 0021_create_response_templates
Revises: 0020_create_tax_config
Create Date: 2026-03-23 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0021_create_response_templates"
down_revision = "0020_create_tax_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "response_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "category",
            sa.String(50),
            nullable=False,
            default="general",
            comment="general | pergunta | reclamacao | devolucao | mensagem",
        ),
        sa.Column(
            "variables",
            postgresql.JSON(),
            nullable=True,
            default={},
            comment="List of variable names like {comprador}, {produto}",
        ),
        sa.Column(
            "use_count",
            sa.Integer(),
            nullable=False,
            default=0,
            comment="Number of times this template has been used",
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uc_user_template_name"),
    )
    op.create_index(
        "ix_response_templates_user_id",
        "response_templates",
        ["user_id"],
    )
    op.create_index(
        "ix_response_templates_category",
        "response_templates",
        ["category"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_response_templates_category",
        table_name="response_templates",
    )
    op.drop_index(
        "ix_response_templates_user_id",
        table_name="response_templates",
    )
    op.drop_table("response_templates")
