"""Add status_event_date to orders (data-do-evento de pós-venda).

Plano Definitivo — líquido fiel ao painel do ML. Guarda a data em que o pedido
atingiu o status TERMINAL de pós-venda (cancelled/refunded), vinda de
`payments[].date_last_modified` do ML (validado no MCP oficial, 2026-07-16).
NULL para pedidos approved/pending. Usada p/ contabilizar cancelados/devoluções
pela DATA DO EVENTO (não pela data da venda), espelhando o painel do vendedor.

Revision ID: 0035_order_status_event_date
Revises: 0034_competitor_prices
Create Date: 2026-07-16 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0035_order_status_event_date"
down_revision = "0034_competitor_prices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("status_event_date", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("orders", "status_event_date")
