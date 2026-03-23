import logging
import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.vendas.models import Listing, ListingSnapshot
from .schemas import InsightItem, InsightsResponse
from .service_pareto import get_pareto_analysis


def _make_insight(
    insight_type: str,
    title: str,
    description: str,
    priority: str,
) -> InsightItem:
    return InsightItem(
        id=str(uuid.uuid4()),
        type=insight_type,
        title=title,
        description=description,
        priority=priority,
        created_at=datetime.now(timezone.utc),
    )


async def generate_insights(
    db: AsyncSession,
    user_id: UUID,
) -> InsightsResponse:
    """
    Generate up to 5 actionable insights for the user's portfolio.

    Checks performed (in order of priority):
    1. Revenue concentration risk  (from Pareto)
    2. Listings with zero sales in the last 7 days
    3. Listings with declining conversion rate (last 7d vs prior 7d)
    """
    insights: list[InsightItem] = []

    # ── 1. Concentration risk from Pareto ───────────────────────────────────
    try:
        pareto = await get_pareto_analysis(db, user_id, days=30)

        if pareto.concentration_risk == "high":
            insights.append(
                _make_insight(
                    insight_type="concentration_risk",
                    title="Alto risco de concentracao de receita",
                    description=(
                        f"Apenas {pareto.core_count} anuncio(s) respondem por "
                        f"{pareto.core_revenue_pct:.1f}% da sua receita dos ultimos 30 dias. "
                        "Diversifique seu portfolio para reduzir exposicao."
                    ),
                    priority="high",
                )
            )
        elif pareto.concentration_risk == "medium":
            insights.append(
                _make_insight(
                    insight_type="concentration_risk",
                    title="Concentracao de receita moderada",
                    description=(
                        f"{pareto.core_count} anuncio(s) representam "
                        f"{pareto.core_revenue_pct:.1f}% da receita. "
                        "Considere fortalecer anuncios secundarios."
                    ),
                    priority="medium",
                )
            )
    except Exception:
        logger.exception("Erro ao gerar insight de concentracao")

    # ── 2. Zero-sales listings in the last 7 days ───────────────────────────
    cutoff_7d = datetime.now(timezone.utc) - timedelta(days=7)
    try:
        zero_sales_stmt = (
            select(Listing.mlb_id, Listing.title)
            .join(ListingSnapshot, ListingSnapshot.listing_id == Listing.id)
            .where(
                and_(
                    Listing.user_id == user_id,
                    ListingSnapshot.captured_at >= cutoff_7d,
                )
            )
            .group_by(Listing.mlb_id, Listing.title)
            .having(func.sum(ListingSnapshot.sales_today) == 0)
            .limit(10)
        )

        zero_result = await db.execute(zero_sales_stmt)
        zero_rows = zero_result.fetchall()

        if zero_rows:
            count = len(zero_rows)
            titles_sample = ", ".join(r.mlb_id for r in zero_rows[:3])
            suffix = f" e mais {count - 3}" if count > 3 else ""
            insights.append(
                _make_insight(
                    insight_type="zero_sales",
                    title=f"{count} anuncio(s) sem vendas nos ultimos 7 dias",
                    description=(
                        f"Os seguintes anuncios nao registraram vendas: "
                        f"{titles_sample}{suffix}. "
                        "Verifique estoque, preco e visibilidade."
                    ),
                    priority="high" if count >= 3 else "medium",
                )
            )
    except Exception:
        logger.exception("Erro ao gerar insight de vendas zero")

    # ── 3. Declining conversion rate ────────────────────────────────────────
    try:
        cutoff_14d = datetime.now(timezone.utc) - timedelta(days=14)

        conv_stmt = (
            select(
                Listing.mlb_id,
                Listing.title,
                func.avg(
                    ListingSnapshot.conversion_rate
                ).filter(ListingSnapshot.captured_at >= cutoff_7d).label("conv_recent"),
                func.avg(
                    ListingSnapshot.conversion_rate
                ).filter(
                    and_(
                        ListingSnapshot.captured_at >= cutoff_14d,
                        ListingSnapshot.captured_at < cutoff_7d,
                    )
                ).label("conv_prior"),
            )
            .join(ListingSnapshot, ListingSnapshot.listing_id == Listing.id)
            .where(
                and_(
                    Listing.user_id == user_id,
                    ListingSnapshot.captured_at >= cutoff_14d,
                    ListingSnapshot.conversion_rate.isnot(None),
                )
            )
            .group_by(Listing.mlb_id, Listing.title)
        )

        conv_result = await db.execute(conv_stmt)
        conv_rows = conv_result.fetchall()

        declining = [
            row
            for row in conv_rows
            if row.conv_recent is not None
            and row.conv_prior is not None
            and float(row.conv_prior) > 0
            and float(row.conv_recent) < float(row.conv_prior) * 0.8
        ]

        if declining:
            count = len(declining)
            sample = ", ".join(r.mlb_id for r in declining[:3])
            suffix = f" e mais {count - 3}" if count > 3 else ""
            insights.append(
                _make_insight(
                    insight_type="declining_conversion",
                    title=f"Queda de conversao detectada em {count} anuncio(s)",
                    description=(
                        f"Os anuncios {sample}{suffix} tiveram queda de mais de 20% "
                        "na taxa de conversao nos ultimos 7 dias em relacao aos 7 dias anteriores. "
                        "Revise preco, titulo e fotos."
                    ),
                    priority="medium",
                )
            )
    except Exception:
        logger.exception("Erro ao gerar insight de conversao")

    # Sort by priority weight and return top 5
    priority_order = {"high": 0, "medium": 1, "low": 2}
    insights.sort(key=lambda i: priority_order.get(i.priority, 9))
    top_insights = insights[:5]

    return InsightsResponse(
        insights=top_insights,
        generated_at=datetime.now(timezone.utc),
    )
