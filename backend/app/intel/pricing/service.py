"""
Orchestrator service for generating price recommendations on demand.

Called by the /generate endpoint in router.py.
Delegates to the same pipeline as tasks_daily_intel.py but runs in-process.
"""
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intel.models import PriceRecommendation
from app.intel.pricing.service_collector import collect_daily_data
from app.intel.pricing.service_score import (
    calculate_health_score,
    calculate_recommendation_score,
)

logger = logging.getLogger(__name__)


async def generate_price_recommendations(db: AsyncSession, user_id: UUID) -> int:
    """
    Generate price recommendations for all active listings of a user.

    Returns the number of recommendations generated.
    """
    today = datetime.now(timezone.utc).date()

    # 1. Collect data
    anuncios = await collect_daily_data(user_id, db=db)
    if not anuncios:
        return 0

    # 2. Calculate scores
    for anuncio in anuncios:
        rec_score = calculate_recommendation_score(anuncio)
        anuncio["recommendation"] = rec_score
        anuncio["health_score"] = calculate_health_score(anuncio)

    # 3. Try AI refinement
    try:
        from app.intel.pricing.service_analyzer import analyze_with_ai

        anuncios = await analyze_with_ai(anuncios)
    except Exception as exc:
        logger.warning("AI analyzer unavailable: %s — using scores only.", exc)
        # Add reasoning to recommendations that don't have it
        for anuncio in anuncios:
            rec = anuncio.get("recommendation", {})
            if "reasoning" not in rec:
                rec["reasoning"] = _simple_reasoning(rec)
                anuncio["recommendation"] = rec

    # 4. Save to DB
    count = 0
    for anuncio in anuncios:
        rec = anuncio.get("recommendation", {})
        listing_id = anuncio["listing_id"]
        periods = anuncio.get("periods", {})
        p_today = periods.get("today", {})
        p_7d = periods.get("last_7d", {})

        # Check for existing recommendation (unique constraint)
        existing = await db.execute(
            select(PriceRecommendation).where(
                PriceRecommendation.listing_id == listing_id,
                PriceRecommendation.report_date == today,
            )
        )
        existing_rec = existing.scalar_one_or_none()

        values = dict(
            user_id=user_id,
            current_price=Decimal(str(anuncio.get("current_price", 0))),
            suggested_price=Decimal(str(rec.get("suggested_price", 0))),
            price_change_pct=Decimal(str(rec.get("price_change_pct", 0))),
            action=rec.get("action", "hold"),
            confidence=rec.get("confidence", "low"),
            risk_level=rec.get("risk_level", "low"),
            urgency=rec.get("urgency", "monitor"),
            reasoning=rec.get("reasoning", ""),
            score=Decimal(str(rec.get("score", 0))),
            score_breakdown={
                **(rec.get("breakdown") or {}),
                "conversion_index": rec.get("conversion_index"),
            },
            conversion_today=Decimal(str(p_today.get("conversion", 0))),
            conversion_7d=Decimal(str(p_7d.get("conversion", 0))),
            visits_today=p_today.get("visits", 0),
            visits_7d=p_7d.get("visits", 0),
            sales_today=p_today.get("sales", 0),
            sales_7d=p_7d.get("sales", 0),
            stock=anuncio.get("stock", 0),
            stock_days_projection=(
                Decimal(str(anuncio["stock_days_projection"]))
                if anuncio.get("stock_days_projection") is not None
                else None
            ),
            estimated_daily_sales=Decimal(str(rec.get("estimated_daily_sales", 0))),
            estimated_daily_profit=Decimal(str(rec.get("estimated_daily_profit", 0))),
            health_score=anuncio.get("health_score"),
            competitor_avg_price=(
                Decimal(str(anuncio["competitor_avg_price"]))
                if anuncio.get("competitor_avg_price") is not None
                else None
            ),
            competitor_min_price=(
                Decimal(str(anuncio["competitor_min_price"]))
                if anuncio.get("competitor_min_price") is not None
                else None
            ),
            status="pending",
            ai_model=anuncio.get("ai_model", "manual-generate"),
            report_date=today,
        )

        if existing_rec:
            for k, v in values.items():
                setattr(existing_rec, k, v)
        else:
            values["listing_id"] = listing_id
            db.add(PriceRecommendation(**values))

        count += 1

    await db.commit()
    logger.info(
        "Generated %d price recommendations for user %s.", count, user_id
    )
    return count


def _simple_reasoning(rec: dict) -> str:
    """Generate simple reasoning text when AI is not available."""
    action = rec.get("action", "hold")
    pct = rec.get("price_change_pct", 0)
    if action == "increase":
        return f"Recomendacao de aumento de {abs(pct):.1f}% baseada em metricas de conversao e concorrencia."
    elif action == "decrease":
        return f"Recomendacao de reducao de {abs(pct):.1f}% baseada em metricas de conversao e concorrencia."
    return "Manter preco atual. Metricas estaveis."
