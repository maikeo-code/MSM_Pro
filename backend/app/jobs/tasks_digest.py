"""
Weekly digest email — enviado todo domingo às 20:00 BRT (23:00 UTC).

Consolida os dados da semana (vendas, receita, visitas, conversão,
top anúncios, queda de vendas, estoque crítico, perguntas, reputação,
concorrência, alertas disparados) e envia um resumo por email para
cada usuário ativo com anúncios.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import cast, func, select, and_
from sqlalchemy import Date as SADate

from app.auth.models import User, MLAccount
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
        listing_by_id = {l.id: l for l in listings}
        today = datetime.now(timezone.utc).date()
        week_start = today - timedelta(days=7)
        prev_week_start = week_start - timedelta(days=7)

        # Receita: usa coluna revenue quando disponível, senão price * sales_today
        revenue_expr = func.coalesce(
            ListingSnapshot.revenue,
            ListingSnapshot.price * ListingSnapshot.sales_today,
        )

        # ── Subquery: snapshot mais recente por listing por dia (esta semana) ──
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

        # ── KPIs da semana ──────────────────────────────────────────────────
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

        # ── Semana anterior (para variação) ────────────────────────────────
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

        # ── Top 5 anúncios da semana (por receita) ─────────────────────────
        top_per_listing = await db.execute(
            select(
                ListingSnapshot.listing_id,
                func.coalesce(func.sum(ListingSnapshot.sales_today), 0).label("vendas"),
                func.coalesce(func.sum(revenue_expr), 0).label("receita"),
            )
            .join(
                latest_per_day,
                (ListingSnapshot.listing_id == latest_per_day.c.listing_id)
                & (ListingSnapshot.captured_at == latest_per_day.c.max_captured_at),
            )
            .where(ListingSnapshot.listing_id.in_(listing_ids))
            .group_by(ListingSnapshot.listing_id)
            .order_by(func.sum(revenue_expr).desc())
            .limit(5)
        )
        top_anuncios: list[dict] = []
        for r in top_per_listing.fetchall():
            listing = listing_by_id.get(r.listing_id)
            if listing:
                top_anuncios.append({
                    "mlb_id": listing.mlb_id,
                    "title": listing.title[:45],
                    "vendas": int(r.vendas),
                    "receita": float(r.receita),
                })

        # ── Anúncios com queda (comparar esta semana vs anterior) ──────────
        # Pega vendas por listing desta semana
        curr_by_listing_result = await db.execute(
            select(
                ListingSnapshot.listing_id,
                func.coalesce(func.sum(ListingSnapshot.sales_today), 0).label("vendas"),
            )
            .join(
                latest_per_day,
                (ListingSnapshot.listing_id == latest_per_day.c.listing_id)
                & (ListingSnapshot.captured_at == latest_per_day.c.max_captured_at),
            )
            .where(ListingSnapshot.listing_id.in_(listing_ids))
            .group_by(ListingSnapshot.listing_id)
        )
        curr_by_listing = {r.listing_id: int(r.vendas) for r in curr_by_listing_result}

        # Pega vendas por listing da semana anterior
        prev_by_listing_result = await db.execute(
            select(
                ListingSnapshot.listing_id,
                func.coalesce(func.sum(ListingSnapshot.sales_today), 0).label("vendas"),
            )
            .join(
                prev_latest,
                (ListingSnapshot.listing_id == prev_latest.c.listing_id)
                & (ListingSnapshot.captured_at == prev_latest.c.max_captured_at),
            )
            .where(ListingSnapshot.listing_id.in_(listing_ids))
            .group_by(ListingSnapshot.listing_id)
        )
        prev_by_listing = {r.listing_id: int(r.vendas) for r in prev_by_listing_result}

        anuncios_queda: list[dict] = []
        for lid, curr_v in curr_by_listing.items():
            prev_v = prev_by_listing.get(lid, 0)
            if prev_v > 0 and curr_v < prev_v:
                queda_pct = round((prev_v - curr_v) / prev_v * 100, 1)
                listing = listing_by_id.get(lid)
                if listing and queda_pct >= 20:  # só quedas significativas (>=20%)
                    anuncios_queda.append({
                        "mlb_id": listing.mlb_id,
                        "title": listing.title[:45],
                        "vendas_atual": curr_v,
                        "vendas_anterior": prev_v,
                        "queda_pct": queda_pct,
                    })

        anuncios_queda.sort(key=lambda x: x["queda_pct"], reverse=True)

        # ── Estoque crítico (< 5 unidades) ─────────────────────────────────
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

        # ── Alertas disparados na semana ───────────────────────────────────
        alertas_count = 0
        try:
            from app.alertas.models import AlertConfig, AlertEvent
            alertas_result = await db.execute(
                select(func.count(AlertEvent.id))
                .join(AlertConfig, AlertEvent.alert_config_id == AlertConfig.id)
                .where(
                    AlertConfig.user_id == user_id,
                    AlertEvent.triggered_at >= datetime.combine(
                        week_start, datetime.min.time(), tzinfo=timezone.utc
                    ),
                )
            )
            alertas_count = alertas_result.scalar() or 0
        except Exception as e:
            logger.debug("Digest: erro ao contar alertas: %s", e)

        # ── Reputação atual ────────────────────────────────────────────────
        reputacao: dict | None = None
        try:
            from app.reputacao.models import ReputationSnapshot

            # Pega as contas ML do usuário
            accounts_result = await db.execute(
                select(MLAccount.id, MLAccount.nickname).where(
                    MLAccount.user_id == user_id,
                    MLAccount.is_active == True,  # noqa: E712
                )
            )
            accounts = accounts_result.fetchall()
            if accounts:
                # Usa a primeira conta como referência
                account_id = accounts[0].id
                rep_result = await db.execute(
                    select(ReputationSnapshot)
                    .where(ReputationSnapshot.ml_account_id == account_id)
                    .order_by(ReputationSnapshot.captured_at.desc())
                    .limit(2)
                )
                rep_rows = rep_result.scalars().all()
                if rep_rows:
                    latest_rep = rep_rows[0]
                    level_labels = {
                        "1_red": "Vermelho",
                        "2_orange": "Laranja",
                        "3_yellow": "Amarelo",
                        "4_light_green": "Verde Claro",
                        "5_green": "Verde",
                    }
                    level_label = level_labels.get(
                        latest_rep.seller_level or "", latest_rep.seller_level or "N/A"
                    )
                    tendencia = None
                    if len(rep_rows) >= 2:
                        prev_rep = rep_rows[1]
                        if latest_rep.seller_level and prev_rep.seller_level:
                            if latest_rep.seller_level > prev_rep.seller_level:
                                tendencia = "melhora"
                            elif latest_rep.seller_level < prev_rep.seller_level:
                                tendencia = "queda"
                            else:
                                tendencia = "estavel"

                    reputacao = {
                        "nivel": level_label,
                        "poder": latest_rep.power_seller_status or "N/A",
                        "reclamacoes": float(latest_rep.claims_rate or 0),
                        "tendencia": tendencia,
                        "account_nickname": accounts[0].nickname or "Conta Principal",
                    }
        except Exception as e:
            logger.debug("Digest: erro ao buscar reputacao: %s", e)

        # ── Mudanças de concorrência na semana ─────────────────────────────
        concorrencia_mudancas: list[dict] = []
        try:
            from app.concorrencia.models import Competitor, CompetitorSnapshot

            # Busca concorrentes dos anúncios do usuário
            comp_result = await db.execute(
                select(Competitor).where(
                    Competitor.listing_id.in_(listing_ids),
                    Competitor.is_active == True,  # noqa: E712
                )
            )
            competitors = comp_result.scalars().all()
            comp_ids = [c.id for c in competitors]

            if comp_ids:
                comp_by_id = {c.id: c for c in competitors}

                # Snapshot mais recente de cada concorrente
                latest_comp = (
                    select(
                        CompetitorSnapshot.competitor_id,
                        func.max(CompetitorSnapshot.captured_at).label("max_at"),
                    )
                    .where(CompetitorSnapshot.competitor_id.in_(comp_ids))
                    .group_by(CompetitorSnapshot.competitor_id)
                    .subquery()
                )

                # Snapshot mais antigo desta semana de cada concorrente
                oldest_comp_week = (
                    select(
                        CompetitorSnapshot.competitor_id,
                        func.min(CompetitorSnapshot.captured_at).label("min_at"),
                    )
                    .where(
                        CompetitorSnapshot.competitor_id.in_(comp_ids),
                        cast(CompetitorSnapshot.captured_at, SADate) >= week_start,
                    )
                    .group_by(CompetitorSnapshot.competitor_id)
                    .subquery()
                )

                # Preço mais recente
                latest_prices = await db.execute(
                    select(
                        CompetitorSnapshot.competitor_id,
                        CompetitorSnapshot.price,
                    )
                    .join(
                        latest_comp,
                        (CompetitorSnapshot.competitor_id == latest_comp.c.competitor_id)
                        & (CompetitorSnapshot.captured_at == latest_comp.c.max_at),
                    )
                )
                price_latest = {r.competitor_id: float(r.price) for r in latest_prices}

                # Preço no início da semana
                oldest_prices = await db.execute(
                    select(
                        CompetitorSnapshot.competitor_id,
                        CompetitorSnapshot.price,
                    )
                    .join(
                        oldest_comp_week,
                        (CompetitorSnapshot.competitor_id == oldest_comp_week.c.competitor_id)
                        & (CompetitorSnapshot.captured_at == oldest_comp_week.c.min_at),
                    )
                )
                price_oldest = {r.competitor_id: float(r.price) for r in oldest_prices}

                for comp_id, price_now in price_latest.items():
                    price_before = price_oldest.get(comp_id)
                    if price_before and price_before > 0:
                        variacao = round((price_now - price_before) / price_before * 100, 1)
                        if abs(variacao) >= 3:  # mudança significativa (>=3%)
                            comp = comp_by_id.get(comp_id)
                            listing = listing_by_id.get(comp.listing_id) if comp else None
                            concorrencia_mudancas.append({
                                "mlb_concorrente": comp.mlb_id if comp else "N/A",
                                "titulo": (comp.title or comp.mlb_id or "")[:40] if comp else "N/A",
                                "preco_antes": price_before,
                                "preco_agora": price_now,
                                "variacao": variacao,
                                "meu_anuncio": listing.mlb_id if listing else "N/A",
                            })

                concorrencia_mudancas.sort(key=lambda x: abs(x["variacao"]), reverse=True)
        except Exception as e:
            logger.debug("Digest: erro ao buscar concorrencia: %s", e)

        # ── Perguntas pendentes (via DB de perguntas não existe — estimativa) ──
        # A API de perguntas é em tempo real via ML API, não armazenamos localmente.
        # Registramos a estimativa como None (seção exibe "acesse o dashboard").
        perguntas_pendentes_count = None

        return {
            "vendas": vendas,
            "visitas": visitas,
            "receita": receita,
            "conversao": conversao,
            "vendas_var": vendas_var,
            "receita_var": receita_var,
            "total_anuncios": len(listings),
            "low_stock": low_stock[:5],
            "top_anuncios": top_anuncios,
            "anuncios_queda": anuncios_queda[:5],
            "alertas_count": alertas_count,
            "reputacao": reputacao,
            "concorrencia_mudancas": concorrencia_mudancas[:5],
            "perguntas_pendentes_count": perguntas_pendentes_count,
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


def _section_header(title: str, color: str = "#1e40af") -> str:
    return (
        f'<h3 style="color:{color}; font-size:15px; font-weight:700; '
        f'margin:0 0 12px 0; padding-bottom:8px; border-bottom:2px solid {color}22;">'
        f"{title}</h3>"
    )


def _build_digest_html(digest: dict) -> str:
    """Gera o HTML completo do digest semanal."""
    vendas_badge = _var_badge(digest["vendas_var"])
    receita_badge = _var_badge(digest["receita_var"])

    kpi_card_tpl = (
        '<div style="background:white; padding:16px; border-radius:8px; '
        'border:1px solid #e2e8f0; min-width:120px; flex:1;">'
        '<p style="margin:0; color:#64748b; font-size:11px; '
        'text-transform:uppercase; letter-spacing:.5px;">{label}</p>'
        '<p style="margin:4px 0 0; font-size:26px; font-weight:700; '
        'color:#1e293b;">{value}{badge}</p>'
        "</div>"
    )

    cards = (
        kpi_card_tpl.format(label="Vendas", value=digest["vendas"], badge=vendas_badge)
        + kpi_card_tpl.format(
            label="Receita",
            value=f"R$ {digest['receita']:,.2f}",
            badge=receita_badge,
        )
        + kpi_card_tpl.format(label="Conversao", value=f"{digest['conversao']}%", badge="")
        + kpi_card_tpl.format(
            label="Visitas", value=f"{digest['visitas']:,}", badge=""
        )
    )

    # ── Estoque crítico ────────────────────────────────────────────────────
    low_stock_html = ""
    if digest["low_stock"]:
        items_html = "".join(
            f'<tr><td style="padding:6px 8px; font-family:monospace; font-size:12px;">'
            f'{s["mlb_id"]}</td>'
            f'<td style="padding:6px 8px; color:#374151; font-size:13px;">{s["title"]}</td>'
            f'<td style="padding:6px 8px; text-align:center;">'
            f'<span style="background:#fef2f2; color:#dc2626; padding:2px 8px; '
            f'border-radius:12px; font-weight:700; font-size:13px;">{s["stock"]} un.</span>'
            f"</td></tr>"
            for s in digest["low_stock"]
        )
        low_stock_html = (
            '<div style="background:#fef2f2; border:1px solid #fecaca; '
            'border-radius:8px; padding:16px; margin-top:20px;">'
            + _section_header("Estoque Critico", "#dc2626")
            + '<table style="width:100%; border-collapse:collapse;">'
            '<tr style="background:#fee2e2;"><th style="padding:6px 8px; text-align:left; '
            'font-size:11px; color:#991b1b;">MLB</th>'
            '<th style="padding:6px 8px; text-align:left; font-size:11px; color:#991b1b;">Titulo</th>'
            '<th style="padding:6px 8px; text-align:center; font-size:11px; color:#991b1b;">Estoque</th>'
            f"</tr>{items_html}</table>"
            "</div>"
        )

    # ── Top 5 anúncios ────────────────────────────────────────────────────
    top_anuncios_html = ""
    if digest.get("top_anuncios"):
        rows = "".join(
            f'<tr style="border-bottom:1px solid #f1f5f9;">'
            f'<td style="padding:7px 8px; font-weight:700; color:#1d4ed8; font-size:13px;">'
            f'{i + 1}. {a["mlb_id"]}</td>'
            f'<td style="padding:7px 8px; color:#374151; font-size:13px;">{a["title"]}</td>'
            f'<td style="padding:7px 8px; text-align:right; font-weight:600; font-size:13px;">'
            f'{a["vendas"]} vnd</td>'
            f'<td style="padding:7px 8px; text-align:right; font-weight:700; color:#15803d; font-size:13px;">'
            f'R$ {a["receita"]:,.2f}</td>'
            f"</tr>"
            for i, a in enumerate(digest["top_anuncios"])
        )
        top_anuncios_html = (
            '<div style="background:white; border:1px solid #e2e8f0; border-radius:8px; '
            'padding:16px; margin-top:20px;">'
            + _section_header("Top 5 Anuncios da Semana", "#1d4ed8")
            + '<table style="width:100%; border-collapse:collapse;">'
            + rows
            + "</table></div>"
        )

    # ── Anúncios com queda ────────────────────────────────────────────────
    anuncios_queda_html = ""
    if digest.get("anuncios_queda"):
        rows = "".join(
            f'<tr style="border-bottom:1px solid #fef2f2;">'
            f'<td style="padding:7px 8px; font-family:monospace; font-size:12px;">{a["mlb_id"]}</td>'
            f'<td style="padding:7px 8px; color:#374151; font-size:13px;">{a["title"]}</td>'
            f'<td style="padding:7px 8px; text-align:center; font-size:13px;">'
            f'{a["vendas_anterior"]} → {a["vendas_atual"]}</td>'
            f'<td style="padding:7px 8px; text-align:right;">'
            f'<span style="background:#fef2f2; color:#dc2626; padding:2px 8px; '
            f'border-radius:12px; font-weight:700; font-size:12px;">↓ {a["queda_pct"]}%</span>'
            f"</td></tr>"
            for a in digest["anuncios_queda"]
        )
        anuncios_queda_html = (
            '<div style="background:white; border:1px solid #fecaca; border-radius:8px; '
            'padding:16px; margin-top:20px;">'
            + _section_header("Anuncios com Queda de Vendas", "#b91c1c")
            + '<table style="width:100%; border-collapse:collapse;">'
            '<tr style="background:#fef2f2;"><th style="padding:6px 8px; text-align:left; '
            'font-size:11px; color:#991b1b;">MLB</th>'
            '<th style="padding:6px 8px; text-align:left; font-size:11px; color:#991b1b;">Titulo</th>'
            '<th style="padding:6px 8px; text-align:center; font-size:11px; color:#991b1b;">Vendas (ant → atual)</th>'
            '<th style="padding:6px 8px; text-align:right; font-size:11px; color:#991b1b;">Queda</th>'
            f"</tr>{rows}</table>"
            "</div>"
        )

    # ── Concorrência ──────────────────────────────────────────────────────
    concorrencia_html = ""
    if digest.get("concorrencia_mudancas"):
        rows = "".join(
            f'<tr style="border-bottom:1px solid #f1f5f9;">'
            f'<td style="padding:7px 8px; font-family:monospace; font-size:12px;">'
            f'{c["mlb_concorrente"]}</td>'
            f'<td style="padding:7px 8px; color:#374151; font-size:13px;">{c["titulo"]}</td>'
            f'<td style="padding:7px 8px; text-align:right; font-size:13px; color:#64748b;">'
            f'R$ {c["preco_antes"]:,.2f}</td>'
            f'<td style="padding:7px 8px; text-align:right; font-size:13px; font-weight:600;">'
            f'R$ {c["preco_agora"]:,.2f}</td>'
            f'<td style="padding:7px 8px; text-align:right;">'
            f'<span style="background:{"#fef2f2" if c["variacao"] < 0 else "#f0fdf4"}; '
            f'color:{"#dc2626" if c["variacao"] < 0 else "#15803d"}; padding:2px 8px; '
            f'border-radius:12px; font-weight:700; font-size:12px;">'
            f'{"↓" if c["variacao"] < 0 else "↑"} {abs(c["variacao"])}%</span>'
            f"</td></tr>"
            for c in digest["concorrencia_mudancas"]
        )
        concorrencia_html = (
            '<div style="background:white; border:1px solid #e2e8f0; border-radius:8px; '
            'padding:16px; margin-top:20px;">'
            + _section_header("Mudancas de Preco dos Concorrentes", "#7c3aed")
            + '<table style="width:100%; border-collapse:collapse;">'
            '<tr style="background:#f5f3ff;"><th style="padding:6px 8px; text-align:left; '
            'font-size:11px; color:#5b21b6;">MLB</th>'
            '<th style="padding:6px 8px; text-align:left; font-size:11px; color:#5b21b6;">Titulo</th>'
            '<th style="padding:6px 8px; text-align:right; font-size:11px; color:#5b21b6;">Preco Antes</th>'
            '<th style="padding:6px 8px; text-align:right; font-size:11px; color:#5b21b6;">Preco Agora</th>'
            '<th style="padding:6px 8px; text-align:right; font-size:11px; color:#5b21b6;">Variacao</th>'
            f"</tr>{rows}</table>"
            "</div>"
        )

    # ── Reputação ──────────────────────────────────────────────────────────
    reputacao_html = ""
    if digest.get("reputacao"):
        rep = digest["reputacao"]
        nivel_cores = {
            "Vermelho": ("#fef2f2", "#dc2626"),
            "Laranja": ("#fff7ed", "#ea580c"),
            "Amarelo": ("#fefce8", "#ca8a04"),
            "Verde Claro": ("#f0fdf4", "#16a34a"),
            "Verde": ("#f0fdf4", "#15803d"),
        }
        bg, fg = nivel_cores.get(rep["nivel"], ("#f8fafc", "#374151"))
        tendencia_html = ""
        if rep.get("tendencia"):
            tend_map = {
                "melhora": ("↑ Melhorando", "#15803d"),
                "queda": ("↓ Em queda", "#dc2626"),
                "estavel": ("→ Estavel", "#64748b"),
            }
            tend_label, tend_color = tend_map.get(rep["tendencia"], ("", "#64748b"))
            if tend_label:
                tendencia_html = (
                    f' <span style="color:{tend_color}; font-size:13px; '
                    f'font-weight:600;">{tend_label}</span>'
                )

        reputacao_html = (
            '<div style="background:white; border:1px solid #e2e8f0; border-radius:8px; '
            'padding:16px; margin-top:20px;">'
            + _section_header("Reputacao do Vendedor", "#0f766e")
            + f'<p style="margin:0; font-size:14px; color:#374151;">'
            f'Conta: <strong>{rep["account_nickname"]}</strong> &nbsp;|&nbsp; '
            f'Nivel: <span style="background:{bg}; color:{fg}; padding:2px 10px; '
            f'border-radius:12px; font-weight:700; font-size:13px;">{rep["nivel"]}</span>'
            f'{tendencia_html}'
            f' &nbsp;|&nbsp; Reclamacoes: <strong>{rep["reclamacoes"]:.2f}%</strong></p>'
            "</div>"
        )

    # ── Alertas disparados ────────────────────────────────────────────────
    alertas_html = ""
    if digest.get("alertas_count", 0) > 0:
        alertas_count = digest["alertas_count"]
        alertas_html = (
            '<div style="background:#fffbeb; border:1px solid #fde68a; border-radius:8px; '
            'padding:14px 16px; margin-top:20px; display:flex; align-items:center; gap:12px;">'
            '<span style="font-size:24px;">⚠️</span>'
            f'<p style="margin:0; font-size:14px; color:#92400e;">'
            f'<strong>{alertas_count} alerta{"s" if alertas_count > 1 else ""}</strong> '
            f'foram disparados esta semana. '
            f'<a href="https://msmprofrontend-production.up.railway.app/alertas" '
            f'style="color:#1d4ed8; text-decoration:none; font-weight:600;">Ver alertas →</a>'
            f"</p></div>"
        )

    # ── Sugestão IA da semana ─────────────────────────────────────────────
    ia_sugestao_html = ""
    try:
        sugestao = _gerar_sugestao_ia(digest)
        if sugestao:
            ia_sugestao_html = (
                '<div style="background:linear-gradient(135deg, #f0f9ff, #e0f2fe); '
                'border:1px solid #bae6fd; border-radius:8px; padding:16px; margin-top:20px;">'
                + _section_header("Sugestao da Semana", "#0369a1")
                + f'<p style="margin:0; font-size:14px; color:#0c4a6e; line-height:1.6;">'
                f'💡 {sugestao}</p>'
                "</div>"
            )
    except Exception as e:
        logger.debug("Digest: erro ao gerar sugestao IA: %s", e)

    # ── Montar HTML completo ───────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Resumo Semanal MSM_Pro</title>
</head>
<body style="margin:0; padding:20px; background:#f1f5f9;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <div style="max-width:620px; margin:0 auto;">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#1e40af,#3b82f6); color:white;
                padding:24px 28px; border-radius:12px 12px 0 0;">
      <h1 style="margin:0; font-size:22px; font-weight:700;">
        Resumo Semanal — MSM_Pro
      </h1>
      <p style="margin:6px 0 0; opacity:.85; font-size:14px;">{digest['period']} &nbsp;·&nbsp; {digest['total_anuncios']} anuncios ativos</p>
    </div>

    <!-- KPIs principais -->
    <div style="background:#f8fafc; padding:24px; border:1px solid #e2e8f0; border-top:none;">
      <div style="display:flex; flex-wrap:wrap; gap:12px;">
        {cards}
      </div>

      {top_anuncios_html}
      {anuncios_queda_html}
      {low_stock_html}
      {concorrencia_html}
      {reputacao_html}
      {alertas_html}
      {ia_sugestao_html}
    </div>

    <!-- CTA -->
    <div style="background:#1e293b; color:white; padding:20px 24px; margin-top:0;">
      <p style="margin:0; font-size:14px; color:#e2e8f0; text-align:center;">
        Analise completa com graficos e detalhes no dashboard
      </p>
      <div style="text-align:center; margin-top:12px;">
        <a href="https://msmprofrontend-production.up.railway.app/dashboard"
           style="background:#3b82f6; color:white; text-decoration:none;
                  padding:10px 24px; border-radius:8px; font-weight:600;
                  font-size:14px; display:inline-block;">
          Acessar Dashboard →
        </a>
      </div>
    </div>

    <!-- Footer -->
    <div style="background:#0f172a; color:#475569; padding:14px 24px;
                border-radius:0 0 12px 12px; text-align:center; font-size:11px;">
      <p style="margin:0;">MSM_Pro — Dashboard de Vendas Mercado Livre</p>
      <p style="margin:4px 0 0; font-size:10px; color:#334155;">
        Recebendo este email porque voce tem uma conta MSM_Pro ativa.
      </p>
    </div>

  </div>
</body>
</html>"""


def _gerar_sugestao_ia(digest: dict) -> str | None:
    """Gera uma sugestão baseada nos dados do digest usando templates inteligentes."""
    # Prioridade 1: estoque crítico
    if digest.get("low_stock"):
        worst = digest["low_stock"][0]
        return (
            f'O anuncio <strong>{worst["mlb_id"]}</strong> esta com apenas '
            f'<strong>{worst["stock"]} unidade(s)</strong> em estoque. '
            f"Considere reabastecer antes do fim de semana para nao perder vendas."
        )

    # Prioridade 2: queda de vendas significativa
    if digest.get("anuncios_queda") and digest["anuncios_queda"][0]["queda_pct"] >= 30:
        pior = digest["anuncios_queda"][0]
        return (
            f'O anuncio <strong>{pior["mlb_id"]}</strong> teve queda de '
            f'<strong>{pior["queda_pct"]}%</strong> nas vendas esta semana '
            f'({pior["vendas_anterior"]} → {pior["vendas_atual"]} unidades). '
            f"Analise o historico de preco x conversao para identificar a causa e ajustar a estrategia."
        )

    # Prioridade 3: concorrente reduziu preco
    if digest.get("concorrencia_mudancas"):
        queda_comp = [c for c in digest["concorrencia_mudancas"] if c["variacao"] < -5]
        if queda_comp:
            comp = queda_comp[0]
            return (
                f'O concorrente <strong>{comp["mlb_concorrente"]}</strong> reduziu o preco em '
                f'<strong>{abs(comp["variacao"])}%</strong> (de R$ {comp["preco_antes"]:,.2f} '
                f'para R$ {comp["preco_agora"]:,.2f}). '
                f"Monitore o impacto nas suas vendas nos proximos dias."
            )

    # Prioridade 4: conversão baixa
    if digest.get("conversao", 0) < 1.5 and digest.get("visitas", 0) > 100:
        return (
            f'Sua conversao media esta em <strong>{digest["conversao"]}%</strong> com '
            f'{digest["visitas"]:,} visitas. Taxas abaixo de 2% geralmente indicam '
            f"oportunidade de melhoria no titulo, fotos ou preco do anuncio."
        )

    # Prioridade 5: boa semana
    if digest.get("receita_var") and digest["receita_var"] > 10:
        return (
            f'Semana excelente! Receita cresceu <strong>{digest["receita_var"]}%</strong> '
            f'em relacao a semana anterior. Analise quais anuncios mais contribuiram '
            f"e considere replicar a estrategia para outros produtos."
        )

    return None


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
