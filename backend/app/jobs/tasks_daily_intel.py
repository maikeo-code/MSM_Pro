"""
Daily Intel Report — enviado diariamente as 08:00 BRT (11:00 UTC).

Pipeline:
1. Collector: busca dados de TODOS os anuncios ativos (SQL)
2. Score Calculator: calcula score + health_score para cada anuncio
3. AI Analyzer: refina com Claude (quando disponivel)
4. Salva em price_recommendations (PostgreSQL)
5. Report Builder: monta HTML
6. Envia email via SMTP
7. Salva log em daily_report_logs

Expira recomendacoes antigas (pending > 3 dias).
"""
import asyncio
import logging
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, update, cast, func
from sqlalchemy import Date as SADate

from app.auth.models import User
from app.core.database import AsyncSessionLocal
from app.core.email import send_html_email
from app.intel.models import DailyReportLog, PriceRecommendation
from app.intel.pricing.service_collector import collect_daily_data
from app.intel.pricing.service_report import (
    _build_summary,
    build_daily_report_html,
)
from app.intel.pricing.service_score import (
    calculate_health_score,
    calculate_recommendation_score,
)
from app.vendas.models import Listing, ListingSnapshot

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_daily_conversion_sparkline(
    listing_id, listing_ids_cache: dict, db
) -> list[float]:
    """
    Busca conversao diaria dos ultimos 7 dias para sparkline.

    Retorna lista de 7 floats (conversao por dia).
    """
    if listing_id in listing_ids_cache:
        return listing_ids_cache[listing_id]

    today = datetime.now(timezone.utc).date()
    date_from = today - timedelta(days=6)

    # Snapshot mais recente por dia
    latest_per_day = (
        select(
            ListingSnapshot.listing_id,
            cast(ListingSnapshot.captured_at, SADate).label("snap_date"),
            func.max(ListingSnapshot.captured_at).label("max_captured_at"),
        )
        .where(
            ListingSnapshot.listing_id == listing_id,
            cast(ListingSnapshot.captured_at, SADate) >= date_from,
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
            cast(ListingSnapshot.captured_at, SADate).label("snap_date"),
            ListingSnapshot.visits,
            ListingSnapshot.sales_today,
        )
        .join(
            latest_per_day,
            (ListingSnapshot.listing_id == latest_per_day.c.listing_id)
            & (ListingSnapshot.captured_at == latest_per_day.c.max_captured_at),
        )
        .where(ListingSnapshot.listing_id == listing_id)
        .order_by(cast(ListingSnapshot.captured_at, SADate).asc())
    )

    values: list[float] = []
    for row in result.fetchall():
        visits = int(row.visits or 0)
        sales = int(row.sales_today or 0)
        conv = round(sales / visits * 100, 2) if visits > 0 else 0.0
        values.append(conv)

    listing_ids_cache[listing_id] = values
    return values


async def _try_analyze_with_ai(anuncios_with_scores: list[dict]) -> list[dict]:
    """
    Tenta refinar recomendacoes com IA (Claude).

    Se o modulo service_analyzer existir, usa-o.
    Caso contrario, gera reasoning baseado em templates.
    """
    try:
        from app.intel.pricing.service_analyzer import analyze_with_ai

        return await analyze_with_ai(anuncios_with_scores)
    except ImportError:
        logger.info(
            "service_analyzer nao disponivel — usando reasoning por template."
        )
        return _generate_template_reasoning(anuncios_with_scores)
    except Exception as exc:
        logger.warning(
            "Erro ao chamar IA analyzer: %s — fallback para templates.", exc
        )
        return _generate_template_reasoning(anuncios_with_scores)


def _generate_template_reasoning(anuncios: list[dict]) -> list[dict]:
    """Gera reasoning baseado em regras/templates (sem IA)."""
    for anuncio in anuncios:
        rec = anuncio.get("recommendation", {})
        action = rec.get("action", "hold")
        breakdown = rec.get("breakdown", {})
        confidence = rec.get("confidence", "low")

        parts: list[str] = []

        conv_trend = breakdown.get("conv_trend", 0)
        visit_trend = breakdown.get("visit_trend", 0)
        comp_score = breakdown.get("comp_score", 0)
        stock_score = breakdown.get("stock_score", 0)

        if action == "increase":
            if conv_trend > 0:
                parts.append("Conversao em tendencia de alta")
            if visit_trend > 0:
                parts.append("visitas crescendo")
            if comp_score > 0:
                parts.append(
                    "preco abaixo da media dos concorrentes"
                )
            if stock_score > 0:
                parts.append("estoque baixo pressiona preco para cima")
            if not parts:
                parts.append("Metricas indicam espaco para aumento de preco")

        elif action == "decrease":
            if conv_trend < 0:
                parts.append("Conversao em tendencia de queda")
            if visit_trend < 0:
                parts.append("visitas em declinio")
            if comp_score < 0:
                parts.append(
                    "preco acima da media dos concorrentes"
                )
            if stock_score < 0:
                parts.append("estoque alto sugere necessidade de giro")
            if not parts:
                parts.append(
                    "Metricas indicam necessidade de reducao de preco"
                )

        else:
            parts.append("Metricas estaveis")
            if confidence == "low":
                parts.append("dados insuficientes para recomendar mudanca")
            else:
                parts.append("nao ha sinais claros para ajuste de preco")

        reasoning = ". ".join(parts) + "."
        rec["reasoning"] = reasoning

        # Detectar oportunidade
        if (
            action == "increase"
            and comp_score > 0.02
            and conv_trend > 0
        ):
            anuncio["opportunity_alert"] = (
                "Oportunidade: preco abaixo dos concorrentes com conversao crescente — "
                "margem para aumento."
            )

    return anuncios


async def _expire_old_recommendations(db) -> int:
    """Marca recomendacoes pending com mais de 3 dias como expired."""
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=3)
    result = await db.execute(
        update(PriceRecommendation)
        .where(
            PriceRecommendation.status == "pending",
            PriceRecommendation.report_date < cutoff,
        )
        .values(status="expired")
    )
    count = result.rowcount
    if count:
        logger.info("Expirou %d recomendacoes antigas (pending > 3 dias).", count)
    return count


async def _save_recommendation(db, user_id, anuncio: dict, report_date: date) -> None:
    """Salva ou atualiza PriceRecommendation no banco."""
    rec = anuncio.get("recommendation", {})
    listing_id = anuncio["listing_id"]

    # Verifica se ja existe para evitar duplicata (uq_recommendation_listing_date)
    existing = await db.execute(
        select(PriceRecommendation).where(
            PriceRecommendation.listing_id == listing_id,
            PriceRecommendation.report_date == report_date,
        )
    )
    existing_rec = existing.scalar_one_or_none()

    periods = anuncio.get("periods", {})
    p_today = periods.get("today", {})
    p_7d = periods.get("last_7d", {})

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
        score_breakdown=rec.get("breakdown"),
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
        ai_model=anuncio.get("ai_model", "template-rules"),
        report_date=report_date,
    )

    if existing_rec:
        for k, v in values.items():
            setattr(existing_rec, k, v)
    else:
        values["listing_id"] = listing_id
        db.add(PriceRecommendation(**values))


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------


async def _send_daily_intel_report_async() -> dict:
    """Executa o pipeline completo do daily intel report."""
    start = time.monotonic()
    today = datetime.now(timezone.utc).date()

    async with AsyncSessionLocal() as db:
        # 0. Expirar recomendacoes antigas
        await _expire_old_recommendations(db)
        await db.commit()

    # Buscar usuarios ativos
    async with AsyncSessionLocal() as db:
        users_result = await db.execute(
            select(User).where(User.is_active == True)  # noqa: E712
        )
        users = users_result.scalars().all()

    total_sent = 0
    total_errors = 0
    total_recommendations = 0

    for user in users:
        try:
            result = await _process_user(user, today)
            if result:
                total_sent += 1 if result.get("email_sent") else 0
                total_recommendations += result.get("recommendations_count", 0)
        except Exception as exc:
            logger.error(
                "Erro ao processar daily intel para user %s: %s",
                user.email,
                exc,
            )
            total_errors += 1

    elapsed_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "Daily Intel Report concluido em %dms — %d/%d usuarios, %d recs, %d erros.",
        elapsed_ms,
        total_sent,
        len(users),
        total_recommendations,
        total_errors,
    )

    return {
        "sent": total_sent,
        "total_users": len(users),
        "total_recommendations": total_recommendations,
        "errors": total_errors,
        "elapsed_ms": elapsed_ms,
    }


async def _process_user(user, report_date: date) -> dict | None:
    """Processa pipeline completo para um usuario."""
    user_start = time.monotonic()

    # 1. Collect data
    anuncios = await collect_daily_data(user.id)
    if not anuncios:
        logger.info(
            "Daily Intel ignorado para %s — sem anuncios ativos.", user.email
        )
        return None

    # 1b. Get adaptive weights
    from app.intel.pricing.service_weights import get_adaptive_weights, DEFAULT_WEIGHTS

    async with AsyncSessionLocal() as db_weights:
        weights = await get_adaptive_weights(db_weights, user.id)

    # 2. Calculate scores with adaptive weights
    for anuncio in anuncios:
        rec_score = calculate_recommendation_score(anuncio, weights=weights)
        anuncio["recommendation"] = rec_score
        anuncio["health_score"] = calculate_health_score(anuncio)

    # 3. AI Analyzer (ou fallback por templates)
    anuncios = await _try_analyze_with_ai(anuncios)

    # 4. Fetch sparkline data
    sparkline_cache: dict = {}
    async with AsyncSessionLocal() as db:
        for anuncio in anuncios:
            anuncio["sparkline_values"] = await _get_daily_conversion_sparkline(
                anuncio["listing_id"], sparkline_cache, db
            )

    # 5. Save recommendations to DB
    async with AsyncSessionLocal() as db:
        for anuncio in anuncios:
            await _save_recommendation(db, user.id, anuncio, report_date)
        await db.commit()

    # 6. Build HTML
    summary = _build_summary(anuncios)
    html = build_daily_report_html(anuncios, summary, report_date)

    # 7. Send email
    subject = (
        f"Intel Diario — {summary['total_vendas']} vendas, "
        f"{summary['increase_count']} aumentar, "
        f"{summary['decrease_count']} diminuir "
        f"({report_date.strftime('%d/%m')})"
    )

    email_sent = await asyncio.to_thread(
        send_html_email, to=user.email, subject=subject, html=html
    )

    # 8. Save DailyReportLog
    elapsed_user = int((time.monotonic() - user_start) * 1000)

    # Encode adaptive weights info (auditable)
    is_adaptive = weights != DEFAULT_WEIGHTS
    ai_model_label = "adaptive-weights" if is_adaptive else "template-rules"

    async with AsyncSessionLocal() as db:
        log = DailyReportLog(
            user_id=user.id,
            report_date=report_date,
            total_listings=len(anuncios),
            recommendations_count=len(anuncios),
            increase_count=summary["increase_count"],
            decrease_count=summary["decrease_count"],
            hold_count=summary["hold_count"],
            email_sent=email_sent,
            email_sent_at=datetime.now(timezone.utc) if email_sent else None,
            ai_model_used=ai_model_label,
            processing_time_ms=elapsed_user,
        )
        db.add(log)
        await db.commit()

    if is_adaptive:
        logger.info(
            "Adaptive weights used for %s: %s", user.email, weights
        )

    logger.info(
        "Daily Intel enviado para %s — %d anuncios, %dms.",
        user.email,
        len(anuncios),
        elapsed_user,
    )

    return {
        "email_sent": email_sent,
        "recommendations_count": len(anuncios),
        "elapsed_ms": elapsed_user,
    }
