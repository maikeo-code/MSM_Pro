"""
Weekly digest email — enviado todo domingo às 20:00 BRT (23:00 UTC).

Consolida os dados da semana (vendas, receita, visitas, conversão)
e envia um resumo por email para cada usuário ativo com anúncios.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import cast, func, select
from sqlalchemy import Date as SADate

from app.auth.models import User
from app.core.database import AsyncSessionLocal
from app.core.email import send_html_email
from app.vendas.models import Listing, ListingSnapshot

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Construção dos dados
# ---------------------------------------------------------------------------


async def _build_digest_for_user(user_id) -> dict | None:
    """Constrói os dados do digest semanal para um usuário."""
    async with AsyncSessionLocal() as db:
        # Anúncios ativos do usuário
        listings_result = await db.execute(
            select(Listing).where(
                Listing.user_id == user_id,
                Listing.status == "active",
            )
        )
        listings = listings_result.scalars().all()
        if not listings:
            return None

        listing_ids = [l.id for l in listings]
        today = datetime.now(timezone.utc).date()
        week_start = today - timedelta(days=7)
        prev_week_start = week_start - timedelta(days=7)

        # Receita: usa coluna revenue quando disponível, senão price * sales_today
        revenue_expr = func.coalesce(
            ListingSnapshot.revenue,
            ListingSnapshot.price * ListingSnapshot.sales_today,
        )

        # --- Esta semana ---
        latest_per_day = (
            select(
                ListingSnapshot.listing_id,
                cast(ListingSnapshot.captured_at, SADate).label("snap_date"),
                func.max(ListingSnapshot.captured_at).label("max_captured_at"),
            )
            .where(
                ListingSnapshot.listing_id.in_(listing_ids),
                cast(ListingSnapshot.captured_at, SADate) >= week_start,
                cast(ListingSnapshot.captured_at, SADate) <= today,
            )
            .group_by(
                ListingSnapshot.listing_id,
                cast(ListingSnapshot.captured_at, SADate),
            )
            .subquery()
        )

        result = await db.execute(
            select(
                func.coalesce(func.sum(ListingSnapshot.sales_today), 0).label("vendas"),
                func.coalesce(func.sum(ListingSnapshot.visits), 0).label("visitas"),
                func.coalesce(func.sum(revenue_expr), 0).label("receita"),
            )
            .join(
                latest_per_day,
                (ListingSnapshot.listing_id == latest_per_day.c.listing_id)
                & (ListingSnapshot.captured_at == latest_per_day.c.max_captured_at),
            )
            .where(ListingSnapshot.listing_id.in_(listing_ids))
        )
        row = result.fetchone()

        vendas = int(row.vendas) if row else 0
        visitas = int(row.visitas) if row else 0
        receita = float(row.receita) if row else 0.0
        conversao = round(vendas / visitas * 100, 2) if visitas > 0 else 0.0

        # --- Semana anterior (para variação) ---
        prev_latest = (
            select(
                ListingSnapshot.listing_id,
                cast(ListingSnapshot.captured_at, SADate).label("snap_date"),
                func.max(ListingSnapshot.captured_at).label("max_captured_at"),
            )
            .where(
                ListingSnapshot.listing_id.in_(listing_ids),
                cast(ListingSnapshot.captured_at, SADate) >= prev_week_start,
                cast(ListingSnapshot.captured_at, SADate) < week_start,
            )
            .group_by(
                ListingSnapshot.listing_id,
                cast(ListingSnapshot.captured_at, SADate),
            )
            .subquery()
        )

        prev_result = await db.execute(
            select(
                func.coalesce(func.sum(ListingSnapshot.sales_today), 0).label("vendas"),
                func.coalesce(func.sum(revenue_expr), 0).label("receita"),
            )
            .join(
                prev_latest,
                (ListingSnapshot.listing_id == prev_latest.c.listing_id)
                & (ListingSnapshot.captured_at == prev_latest.c.max_captured_at),
            )
            .where(ListingSnapshot.listing_id.in_(listing_ids))
        )
        prev_row = prev_result.fetchone()
        prev_vendas = int(prev_row.vendas) if prev_row else 0
        prev_receita = float(prev_row.receita) if prev_row else 0.0

        vendas_var = (
            round((vendas - prev_vendas) / prev_vendas * 100, 1)
            if prev_vendas > 0
            else None
        )
        receita_var = (
            round((receita - prev_receita) / prev_receita * 100, 1)
            if prev_receita > 0
            else None
        )

        # --- Estoque crítico (< 5 unidades) ---
        # Uma única query que pega o snapshot mais recente de cada listing
        # usando subquery de max(captured_at), evitando N+1.
        latest_snap_subq = (
            select(
                ListingSnapshot.listing_id,
                func.max(ListingSnapshot.captured_at).label("max_captured_at"),
            )
            .where(ListingSnapshot.listing_id.in_(listing_ids))
            .group_by(ListingSnapshot.listing_id)
            .subquery()
        )

        low_stock_result = await db.execute(
            select(Listing.mlb_id, Listing.title, ListingSnapshot.stock)
            .join(
                ListingSnapshot,
                ListingSnapshot.listing_id == Listing.id,
            )
            .join(
                latest_snap_subq,
                (ListingSnapshot.listing_id == latest_snap_subq.c.listing_id)
                & (ListingSnapshot.captured_at == latest_snap_subq.c.max_captured_at),
            )
            .where(
                Listing.id.in_(listing_ids),
                ListingSnapshot.stock < 5,
            )
            .order_by(ListingSnapshot.stock.asc())
        )

        low_stock: list[dict] = [
            {
                "mlb_id": row.mlb_id,
                "title": row.title[:50],
                "stock": row.stock,
            }
            for row in low_stock_result.fetchall()
        ]

        return {
            "vendas": vendas,
            "visitas": visitas,
            "receita": receita,
            "conversao": conversao,
            "vendas_var": vendas_var,
            "receita_var": receita_var,
            "total_anuncios": len(listings),
            "low_stock": low_stock[:5],
            "period": f"{week_start.strftime('%d/%m')} a {today.strftime('%d/%m/%Y')}",
        }


# ---------------------------------------------------------------------------
# Geração do HTML
# ---------------------------------------------------------------------------


def _var_badge(value: float | None, *, positive_good: bool = True) -> str:
    """Gera badge HTML de variação percentual."""
    if value is None:
        return ""
    is_positive = value >= 0
    good = is_positive if positive_good else not is_positive
    color = "#22c55e" if good else "#ef4444"
    arrow = "↑" if is_positive else "↓"
    return (
        f' <span style="color:{color}; font-size:14px; font-weight:600;">'
        f"{arrow} {abs(value):.1f}%</span>"
    )


def _build_digest_html(digest: dict) -> str:
    """Gera o HTML completo do digest semanal."""
    vendas_badge = _var_badge(digest["vendas_var"])
    receita_badge = _var_badge(digest["receita_var"])

    low_stock_html = ""
    if digest["low_stock"]:
        items_html = "".join(
            f'<li style="padding:4px 0;">'
            f'<strong>{s["mlb_id"]}</strong> — {s["title"]} '
            f'<span style="color:#dc2626;">({s["stock"]} un.)</span></li>'
            for s in digest["low_stock"]
        )
        low_stock_html = (
            '<div style="background:#fef2f2; border:1px solid #fecaca; '
            'border-radius:8px; padding:16px; margin-top:20px;">'
            '<h3 style="color:#dc2626; margin:0 0 8px 0; font-size:16px;">'
            "Estoque Critico</h3>"
            f'<ul style="margin:0; padding-left:20px; color:#374151;">{items_html}</ul>'
            "</div>"
        )

    kpi_card = (
        '<div style="background:white; padding:16px; border-radius:8px; '
        'border:1px solid #e2e8f0; min-width:120px; flex:1;">'
        '<p style="margin:0; color:#64748b; font-size:11px; '
        'text-transform:uppercase; letter-spacing:.5px;">{label}</p>'
        '<p style="margin:4px 0 0; font-size:26px; font-weight:700; '
        'color:#1e293b;">{value}{badge}</p>'
        "</div>"
    )

    cards = (
        kpi_card.format(label="Vendas", value=digest["vendas"], badge=vendas_badge)
        + kpi_card.format(
            label="Receita",
            value=f"R$ {digest['receita']:,.2f}",
            badge=receita_badge,
        )
        + kpi_card.format(label="Conversao", value=f"{digest['conversao']}%", badge="")
        + kpi_card.format(
            label="Visitas", value=f"{digest['visitas']:,}", badge=""
        )
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Resumo Semanal MSM_Pro</title>
</head>
<body style="margin:0; padding:20px; background:#f1f5f9;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <div style="max-width:600px; margin:0 auto;">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#1e40af,#3b82f6); color:white;
                padding:24px 28px; border-radius:12px 12px 0 0;">
      <h1 style="margin:0; font-size:22px; font-weight:700;">
        Resumo Semanal — MSM_Pro
      </h1>
      <p style="margin:6px 0 0; opacity:.85; font-size:14px;">{digest['period']}</p>
    </div>

    <!-- KPIs -->
    <div style="background:#f8fafc; padding:24px; border:1px solid #e2e8f0; border-top:none;">
      <div style="display:flex; flex-wrap:wrap; gap:12px;">
        {cards}
      </div>

      {low_stock_html}
    </div>

    <!-- Footer -->
    <div style="background:#1e293b; color:#94a3b8; padding:16px 24px;
                border-radius:0 0 12px 12px; text-align:center; font-size:12px;">
      <p style="margin:0;">MSM_Pro — Dashboard de Vendas Mercado Livre</p>
      <p style="margin:6px 0 0;">
        <a href="https://msmprofrontend-production.up.railway.app/dashboard"
           style="color:#60a5fa; text-decoration:none;">
          Acessar Dashboard
        </a>
      </p>
    </div>

  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Envio
# ---------------------------------------------------------------------------


async def _send_weekly_digest_async() -> dict:
    """Envia o digest semanal para todos os usuários ativos."""
    async with AsyncSessionLocal() as db:
        users_result = await db.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )
        users = users_result.scalars().all()

    sent = 0
    for user in users:
        try:
            digest = await _build_digest_for_user(user.id)
            if not digest:
                logger.info("Digest ignorado para %s — sem anuncios ativos.", user.email)
                continue

            html = _build_digest_html(digest)
            subject = (
                f"Resumo Semanal — {digest['vendas']} vendas, "
                f"R$ {digest['receita']:,.2f} receita"
            )

            await asyncio.to_thread(send_html_email, to=user.email, subject=subject, html=html)
            sent += 1
            logger.info("Digest semanal enviado para %s.", user.email)

        except Exception as exc:  # noqa: BLE001
            logger.error("Erro ao enviar digest para %s: %s", user.email, exc)

    logger.info("Weekly digest concluido — %d/%d usuarios.", sent, len(users))
    return {"sent": sent, "total_users": len(users)}
