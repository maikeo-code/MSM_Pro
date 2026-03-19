import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import and_, cast, desc, func, select
from sqlalchemy import Date as SADate
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.database import get_db
from app.core.deps import get_current_user
from app.intel.models import PriceRecommendation
from app.produtos.models import Product
from app.vendas.models import Listing, ListingSnapshot

from .schemas import (
    ApplyRecommendationRequest,
    ApplyRecommendationResponse,
    DismissRecommendationRequest,
    GenerateResponse,
    PeriodMetrics,
    PeriodsData,
    RecommendationHistoryOut,
    RecommendationListResponse,
    RecommendationOut,
    RecommendationSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intel/pricing", tags=["Intel - Pricing"])


# ─── Helpers ────────────────────────────────────────────────────────────────


def _rec_to_out(rec: PriceRecommendation, listing: Listing, product_sku: str | None = None) -> dict:
    """Converte um PriceRecommendation ORM + Listing em dict compativel com RecommendationOut."""
    # Prioridade SKU: listing.seller_sku > product.sku (via product_id)
    sku = listing.seller_sku or product_sku
    return {
        "id": rec.id,
        "listing_id": rec.listing_id,
        "mlb_id": listing.mlb_id,
        "sku": sku,
        "title": listing.title,
        "thumbnail": listing.thumbnail,
        "current_price": float(rec.current_price),
        "suggested_price": float(rec.suggested_price),
        "price_change_pct": float(rec.price_change_pct),
        "action": rec.action,
        "confidence": rec.confidence,
        "risk_level": rec.risk_level,
        "urgency": rec.urgency,
        "reasoning": rec.reasoning,
        "score": float(rec.score) if rec.score is not None else None,
        "score_breakdown": rec.score_breakdown,
        "conversion_today": float(rec.conversion_today) if rec.conversion_today is not None else None,
        "conversion_7d": float(rec.conversion_7d) if rec.conversion_7d is not None else None,
        "visits_today": rec.visits_today,
        "visits_7d": rec.visits_7d,
        "sales_today": rec.sales_today,
        "sales_7d": rec.sales_7d,
        "stock": rec.stock,
        "stock_days_projection": float(rec.stock_days_projection) if rec.stock_days_projection is not None else None,
        "estimated_daily_sales": float(rec.estimated_daily_sales) if rec.estimated_daily_sales is not None else None,
        "estimated_daily_profit": float(rec.estimated_daily_profit) if rec.estimated_daily_profit is not None else None,
        "health_score": rec.health_score,
        "competitor_avg_price": float(rec.competitor_avg_price) if rec.competitor_avg_price is not None else None,
        "competitor_min_price": float(rec.competitor_min_price) if rec.competitor_min_price is not None else None,
        "status": rec.status,
        "applied_at": rec.applied_at,
        "report_date": rec.report_date,
        "created_at": rec.created_at,
    }


async def _enrich_with_periods(
    db: AsyncSession,
    items: list[dict],
) -> None:
    """
    Enriquece cada item (dict) com periods_data buscando direto dos snapshots.

    Calcula metricas de today, yesterday, last_7d e last_15d sem precisar
    de colunas extras no model PriceRecommendation (zero migrations).
    """
    listing_ids = [item["listing_id"] for item in items]
    if not listing_ids:
        return

    today = date.today()
    yesterday = today - timedelta(days=1)
    date_7d_ago = today - timedelta(days=6)
    date_15d_ago = today - timedelta(days=14)

    async def _aggregate(
        d_from: date, d_to: date
    ) -> dict[UUID, dict]:
        """Agrega visits/sales por listing no intervalo, deduplicando por dia."""
        # Subquery: snapshot mais recente por listing por dia
        latest_per_day = (
            select(
                ListingSnapshot.listing_id,
                cast(ListingSnapshot.captured_at, SADate).label("snap_date"),
                func.max(ListingSnapshot.captured_at).label("max_captured_at"),
            )
            .where(
                ListingSnapshot.listing_id.in_(listing_ids),
                cast(ListingSnapshot.captured_at, SADate) >= d_from,
                cast(ListingSnapshot.captured_at, SADate) <= d_to,
            )
            .group_by(
                ListingSnapshot.listing_id,
                cast(ListingSnapshot.captured_at, SADate),
            )
            .subquery()
        )

        result = await db.execute(
            select(
                ListingSnapshot.listing_id,
                func.coalesce(func.sum(ListingSnapshot.visits), 0).label("visits"),
                func.coalesce(func.sum(ListingSnapshot.sales_today), 0).label("sales"),
            )
            .join(
                latest_per_day,
                (ListingSnapshot.listing_id == latest_per_day.c.listing_id)
                & (ListingSnapshot.captured_at == latest_per_day.c.max_captured_at),
            )
            .where(ListingSnapshot.listing_id.in_(listing_ids))
            .group_by(ListingSnapshot.listing_id)
        )

        out: dict[UUID, dict] = {}
        for row in result.fetchall():
            visits = int(row.visits)
            sales = int(row.sales)
            conversion = round((sales / visits * 100), 2) if visits > 0 else 0.0
            out[row.listing_id] = {
                "visits": visits,
                "sales": sales,
                "conversion": conversion,
                "avg_price": 0.0,
            }
        return out

    # Executar as 4 queries de periodo
    p_today = await _aggregate(today, today)
    p_yesterday = await _aggregate(yesterday, yesterday)
    p_7d = await _aggregate(date_7d_ago, today)
    p_15d = await _aggregate(date_15d_ago, today)

    empty = {"visits": 0, "sales": 0, "conversion": 0.0, "avg_price": 0.0}

    for item in items:
        lid = item["listing_id"]
        item["periods_data"] = PeriodsData(
            today=PeriodMetrics(**(p_today.get(lid, empty))),
            yesterday=PeriodMetrics(**(p_yesterday.get(lid, empty))),
            last_7d=PeriodMetrics(**(p_7d.get(lid, empty))),
            last_15d=PeriodMetrics(**(p_15d.get(lid, empty))),
        )


# ─── GET /intel/pricing/recommendations ────────────────────────────────────


@router.get("/recommendations", response_model=RecommendationListResponse)
async def list_recommendations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    report_date: date | None = Query(
        default=None,
        description="Data do relatorio (default: hoje). Formato: YYYY-MM-DD",
    ),
    action: str | None = Query(
        default=None,
        pattern=r"^(increase|decrease|hold)$",
        description="Filtrar por acao: increase, decrease, hold",
    ),
    confidence: str | None = Query(
        default=None,
        pattern=r"^(high|medium|low)$",
        description="Filtrar por confianca: high, medium, low",
    ),
    sort: str = Query(
        default="sku",
        pattern=r"^(sku|price_change_pct|score|action|confidence)$",
        description="Ordenar por: sku (default), price_change_pct, score, action, confidence",
    ),
) -> RecommendationListResponse:
    """
    Lista recomendacoes de preco para uma data especifica.

    Retorna todas as recomendacoes do usuario para a data solicitada,
    com resumo agregado (total por acao, confianca media).
    """
    target_date = report_date or date.today()

    # Filtros base
    conditions = [
        PriceRecommendation.user_id == current_user.id,
        PriceRecommendation.report_date == target_date,
    ]
    if action:
        conditions.append(PriceRecommendation.action == action)
    if confidence:
        conditions.append(PriceRecommendation.confidence == confidence)

    # Ordenacao
    sort_map = {
        "sku": Listing.seller_sku,
        "price_change_pct": desc(PriceRecommendation.price_change_pct),
        "score": desc(PriceRecommendation.score),
        "action": PriceRecommendation.action,
        "confidence": PriceRecommendation.confidence,
    }
    order_clause = sort_map.get(sort, Listing.seller_sku)

    # Query com join no Listing para pegar mlb_id, title, thumbnail, sku
    stmt = (
        select(PriceRecommendation, Listing)
        .join(Listing, PriceRecommendation.listing_id == Listing.id)
        .where(and_(*conditions))
        .order_by(order_clause)
    )

    result = await db.execute(stmt)
    rows = result.all()

    # Buscar SKUs dos Products vinculados (fallback quando listing.seller_sku e None)
    product_ids = [listing.product_id for _, listing in rows if listing.product_id]
    product_skus: dict[UUID, str] = {}
    if product_ids:
        prod_result = await db.execute(
            select(Product.id, Product.sku).where(Product.id.in_(product_ids))
        )
        for p in prod_result.fetchall():
            product_skus[p.id] = p.sku

    items = [
        _rec_to_out(rec, listing, product_skus.get(listing.product_id) if listing.product_id else None)
        for rec, listing in rows
    ]

    # Enriquecer com dados de periodos (today, yesterday, 7d, 15d) dos snapshots
    await _enrich_with_periods(db, items)

    # Summary
    total = len(items)
    increase_count = sum(1 for i in items if i["action"] == "increase")
    decrease_count = sum(1 for i in items if i["action"] == "decrease")
    hold_count = sum(1 for i in items if i["action"] == "hold")
    high_count = sum(1 for i in items if i["confidence"] == "high")
    avg_confidence = f"{(high_count / total * 100):.0f}%" if total > 0 else "0%"

    return RecommendationListResponse(
        items=items,
        total=total,
        date=target_date,
        summary=RecommendationSummary(
            total=total,
            increase_count=increase_count,
            decrease_count=decrease_count,
            hold_count=hold_count,
            avg_confidence=avg_confidence,
        ),
    )


# ─── POST /intel/pricing/recommendations/{id}/apply ────────────────────────


@router.post(
    "/recommendations/{recommendation_id}/apply",
    response_model=ApplyRecommendationResponse,
)
async def apply_recommendation(
    recommendation_id: Annotated[UUID, Path(description="UUID da recomendacao")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApplyRecommendationResponse:
    """
    Aplica o preco sugerido de uma recomendacao na API do Mercado Livre.

    Altera o preco do anuncio via API ML, registra no price_change_log e
    marca a recomendacao como 'applied'.
    """
    # Buscar recomendacao
    result = await db.execute(
        select(PriceRecommendation).where(
            and_(
                PriceRecommendation.id == recommendation_id,
                PriceRecommendation.user_id == current_user.id,
            )
        )
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recomendacao nao encontrada",
        )

    if rec.status == "applied":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Recomendacao ja foi aplicada",
        )

    # Buscar listing para pegar mlb_id
    listing_result = await db.execute(
        select(Listing).where(Listing.id == rec.listing_id)
    )
    listing = listing_result.scalar_one_or_none()
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anuncio vinculado nao encontrado",
        )

    # Aplicar preco via service_price
    from app.vendas.service_price import apply_price_suggestion

    apply_result = None
    try:
        apply_result = await apply_price_suggestion(
            db,
            listing.mlb_id,
            current_user.id,
            float(rec.suggested_price),
            f"Recomendacao Intel #{str(recommendation_id)[:8]}: {rec.reasoning[:100]}",
        )
        ml_success = apply_result.get("ml_api_success", False) if isinstance(apply_result, dict) else getattr(apply_result, "ml_api_success", False)
    except Exception as e:
        logger.error("Erro ao aplicar recomendacao %s: %s", recommendation_id, e)
        ml_success = False

    # Atualizar status da recomendacao
    rec.status = "applied"
    rec.applied_at = datetime.now(timezone.utc)
    rec.applied_price = rec.suggested_price

    # Vincular ao price_change_log se disponivel
    log_id = None
    if apply_result is not None and isinstance(apply_result, dict):
        log_id = apply_result.get("log_id")
    elif apply_result is not None and hasattr(apply_result, "log_id"):
        log_id = apply_result.log_id
    if log_id:
        rec.price_change_log_id = log_id

    await db.commit()

    return ApplyRecommendationResponse(
        recommendation_id=rec.id,
        mlb_id=listing.mlb_id,
        old_price=float(rec.current_price),
        new_price=float(rec.suggested_price),
        ml_api_success=ml_success,
        message="Preco aplicado com sucesso" if ml_success else "Erro ao aplicar preco na API ML",
    )


# ─── POST /intel/pricing/recommendations/{id}/dismiss ──────────────────────


@router.post("/recommendations/{recommendation_id}/dismiss")
async def dismiss_recommendation(
    recommendation_id: Annotated[UUID, Path(description="UUID da recomendacao")],
    payload: DismissRecommendationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """
    Marca uma recomendacao como 'dismissed' (descartada pelo usuario).

    Opcionalmente aceita um motivo para registro.
    """
    result = await db.execute(
        select(PriceRecommendation).where(
            and_(
                PriceRecommendation.id == recommendation_id,
                PriceRecommendation.user_id == current_user.id,
            )
        )
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recomendacao nao encontrada",
        )

    if rec.status in ("applied", "dismissed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Recomendacao ja esta com status '{rec.status}'",
        )

    rec.status = "dismissed"
    if payload.reason:
        rec.reasoning = f"{rec.reasoning} | Dismissed: {payload.reason}"

    await db.commit()

    return {"status": "dismissed"}


# ─── GET /intel/pricing/recommendations/history/{mlb_id} ───────────────────


@router.get(
    "/recommendations/history/{mlb_id}",
    response_model=RecommendationHistoryOut,
)
async def recommendation_history(
    mlb_id: Annotated[str, Path(min_length=3, max_length=30, description="MLB ID do anuncio")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(
        default=30,
        ge=1,
        le=365,
        description="Numero de dias de historico (default: 30)",
    ),
) -> RecommendationHistoryOut:
    """
    Retorna historico de recomendacoes para um anuncio especifico.

    Ordenado por report_date descendente (mais recente primeiro).
    """
    # Normalizar mlb_id
    mlb_normalized = mlb_id.upper().replace("-", "")
    if not mlb_normalized.startswith("MLB"):
        mlb_normalized = f"MLB{mlb_normalized}"

    # Buscar listing
    listing_result = await db.execute(
        select(Listing).where(
            and_(
                Listing.user_id == current_user.id,
                Listing.mlb_id == mlb_normalized,
            )
        )
    )
    listing = listing_result.scalar_one_or_none()
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anuncio {mlb_id} nao encontrado",
        )

    cutoff = date.today() - timedelta(days=days)

    stmt = (
        select(PriceRecommendation)
        .where(
            and_(
                PriceRecommendation.listing_id == listing.id,
                PriceRecommendation.user_id == current_user.id,
                PriceRecommendation.report_date >= cutoff,
            )
        )
        .order_by(desc(PriceRecommendation.report_date))
    )

    result = await db.execute(stmt)
    recs = result.scalars().all()

    # Buscar SKU do Product vinculado (fallback)
    product_sku = None
    if listing.product_id:
        prod_result = await db.execute(
            select(Product.sku).where(Product.id == listing.product_id)
        )
        product_sku = prod_result.scalar_one_or_none()

    items = [_rec_to_out(rec, listing, product_sku) for rec in recs]

    return RecommendationHistoryOut(items=items, total=len(items))


# ─── POST /intel/pricing/recommendations/generate ──────────────────────────


@router.post("/recommendations/generate", response_model=GenerateResponse)
async def generate_recommendations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GenerateResponse:
    """
    Forca a geracao manual de recomendacoes de preco (sem esperar Celery).

    Dispara a analise para todos os anuncios ativos do usuario e retorna
    o numero de recomendacoes geradas.
    """
    start_ms = time.monotonic_ns() // 1_000_000

    try:
        # Importar service de geracao (sera criado por outro agente)
        from app.intel.pricing.service import generate_price_recommendations

        count = await generate_price_recommendations(db, current_user.id)
    except ImportError:
        # Service ainda nao implementado — retornar placeholder
        logger.warning("intel.pricing.service nao encontrado — retornando placeholder")
        count = 0
    except Exception as e:
        logger.error("Erro ao gerar recomendacoes: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao gerar recomendacoes: {str(e)}",
        )

    elapsed_ms = (time.monotonic_ns() // 1_000_000) - start_ms

    return GenerateResponse(
        status="completed",
        recommendations_count=count,
        processing_time_ms=elapsed_ms,
        message=f"{count} recomendacoes geradas com sucesso" if count > 0 else "Nenhuma recomendacao gerada (service pendente ou sem dados)",
    )
