"""Create questions, question_answers, and qa_suggestion_logs tables

Revision ID: 0026_create_questions
Revises: 0025_create_user_notifications
Create Date: 2026-04-02 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0026_create_questions"
down_revision = "0025_create_user_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create questions table
    op.create_table(
        "questions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("ml_question_id", sa.Integer(), nullable=False),
        sa.Column("ml_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("mlb_id", sa.String(50), nullable=False),
        sa.Column("item_title", sa.String(500), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="UNANSWERED"),
        sa.Column("buyer_id", sa.Integer(), nullable=True),
        sa.Column("buyer_nickname", sa.String(100), nullable=True),
        sa.Column("date_created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("answer_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answer_source", sa.String(20), nullable=True),
        sa.Column("ai_suggestion_text", sa.Text(), nullable=True),
        sa.Column("ai_suggestion_confidence", sa.String(10), nullable=True),
        sa.Column("ai_suggested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ml_account_id"], ["ml_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ml_question_id", name="uq_questions_ml_question_id"),
    )
    op.create_index(
        "ix_questions_ml_account_id_status",
        "questions",
        ["ml_account_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_questions_mlb_id",
        "questions",
        ["mlb_id"],
        unique=False,
    )
    op.create_index(
        "ix_questions_date_created",
        "questions",
        ["date_created"],
        unique=False,
    )

    # Create question_answers table
    op.create_table(
        "question_answers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["response_templates.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_question_answers_question_id",
        "question_answers",
        ["question_id"],
        unique=False,
    )

    # Create qa_suggestion_logs table
    op.create_table(
        "qa_suggestion_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("suggested_answer", sa.Text(), nullable=False),
        sa.Column("question_type", sa.String(30), nullable=True),
        sa.Column("confidence", sa.String(10), nullable=False),
        sa.Column("was_used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("was_edited", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_qa_suggestion_logs_question_id",
        "qa_suggestion_logs",
        ["question_id"],
        unique=False,
    )
    op.create_index(
        "ix_qa_suggestion_logs_created_at",
        "qa_suggestion_logs",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_qa_suggestion_logs_created_at", table_name="qa_suggestion_logs")
    op.drop_index("ix_qa_suggestion_logs_question_id", table_name="qa_suggestion_logs")
    op.drop_table("qa_suggestion_logs")

    op.drop_index("ix_question_answers_question_id", table_name="question_answers")
    op.drop_table("question_answers")

    op.drop_index("ix_questions_date_created", table_name="questions")
    op.drop_index("ix_questions_mlb_id", table_name="questions")
    op.drop_index("ix_questions_ml_account_id_status", table_name="questions")
    op.drop_table("questions")
