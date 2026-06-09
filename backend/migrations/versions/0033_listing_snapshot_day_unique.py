"""Add snapshot_day + unique(listing_id, snapshot_day) to listing_snapshots

Impede múltiplos snapshots por anúncio por dia (causa raiz da inflação de
KPIs/visitas: sync diário + 24 horários + backfill criavam vários snapshots/dia,
e a agregação somava todos). Defensiva: faz BACKUP dos duplicados removidos numa
tabela separada (reversível) antes de deduplicar.

Revision ID: 0033_snapshot_day_unique
Revises: 0032_rating_qa_logs
Create Date: 2026-06-09 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0033_snapshot_day_unique"
down_revision = "0032_rating_qa_logs"
branch_labels = None
depends_on = None

_BACKUP_TABLE = "listing_snapshots_dedup_backup"


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # 1) Coluna snapshot_day (nullable de início para permitir backfill)
    op.add_column(
        "listing_snapshots",
        sa.Column("snapshot_day", sa.Date(), nullable=True),
    )

    if is_pg:
        # 2) Popula snapshot_day a partir de captured_at no fuso BRT (dia local)
        op.execute(
            "UPDATE listing_snapshots "
            "SET snapshot_day = (captured_at AT TIME ZONE 'America/Sao_Paulo')::date"
        )

        # 3) BACKUP dos duplicados que serão removidos (mantém o de maior captured_at)
        op.execute(f"DROP TABLE IF EXISTS {_BACKUP_TABLE}")
        op.execute(
            f"CREATE TABLE {_BACKUP_TABLE} AS "
            "SELECT ls.* FROM listing_snapshots ls "
            "JOIN (SELECT id, ROW_NUMBER() OVER ("
            "  PARTITION BY listing_id, snapshot_day ORDER BY captured_at DESC) AS rn "
            "  FROM listing_snapshots) d ON ls.id = d.id WHERE d.rn > 1"
        )

        # 4) Remove duplicados, mantendo o snapshot mais recente de cada (listing, dia)
        op.execute(
            "DELETE FROM listing_snapshots ls USING ("
            "  SELECT id, ROW_NUMBER() OVER ("
            "    PARTITION BY listing_id, snapshot_day ORDER BY captured_at DESC) AS rn "
            "  FROM listing_snapshots) d "
            "WHERE ls.id = d.id AND d.rn > 1"
        )
    else:
        # SQLite (testes): popula via date(captured_at); dedup análogo
        op.execute("UPDATE listing_snapshots SET snapshot_day = date(captured_at)")
        op.execute(
            "DELETE FROM listing_snapshots WHERE id IN ("
            "  SELECT id FROM (SELECT id, ROW_NUMBER() OVER ("
            "    PARTITION BY listing_id, snapshot_day ORDER BY captured_at DESC) AS rn "
            "    FROM listing_snapshots) WHERE rn > 1)"
        )

    # 5) Torna NOT NULL e cria a trava de unicidade
    op.alter_column("listing_snapshots", "snapshot_day", nullable=False)
    op.create_index(
        "ix_listing_snapshots_snapshot_day", "listing_snapshots", ["snapshot_day"]
    )
    op.create_unique_constraint(
        "uq_listing_snapshot_day",
        "listing_snapshots",
        ["listing_id", "snapshot_day"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_listing_snapshot_day", "listing_snapshots", type_="unique")
    op.drop_index("ix_listing_snapshots_snapshot_day", table_name="listing_snapshots")
    op.drop_column("listing_snapshots", "snapshot_day")
    op.execute(f"DROP TABLE IF EXISTS {_BACKUP_TABLE}")
