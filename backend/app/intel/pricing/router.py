import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

# Timezone BRT (UTC-3)
BRT = timezone(timedelta(hours=-3))

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
    ConversionIndex,
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
    # Extract conversion_index from score_breakdown JSON (stored together)
    # BUG 4: Criar copia para nao mutar dict do ORM
    raw_breakdown = rec.score_breakdown or {}
    if isinstance(raw_breakdown, dict):
        raw_breakdown = {**raw_breakdown}  # shallow copy
    ci_raw = raw_breakdown.pop("conversion_index", None) if isinstance(raw_breakdown, dict) else None

    # has_active_promotion: buscar do listing snapshot mais recente ou null se não disponível
    # Por enquanto, retornar None (pode ser enriquecido depois se necessário)
    has_active_promotion = None

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
        "score_breakdown": raw_breakdown if raw_breakdown else None,
        "conversion_index": ci_raw,
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
        "has_active_promotion": has_active_promotion,
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

    today = datetime.now(BRT).date()
    yesterday = today - timedelta(days=1)
    day_before_yesterday = today - timedelta(days=2)
    d3 = today - timedelta(days=3)
    d4 = today - timedelta(days=4)
    d5 = today - timedelta(days=5)
    d6 = today - timedelta(days=6)
    date_7d_ago = today - timedelta(days=6)
    date_15d_ago = today - timedelta(days=14)
    date_30d_ago = today - timedelta(days=29)

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
                "revenue": 0.0,  # BUG 2: field missing, default to 0.0
            }
        return out

    # Executar as 10 queries de periodo (6 dias individuais + 3 agregados)
    p_today = await _aggregate(today, today)
    p_yesterday = await _aggregate(yesterday, yesterday)
    p_day_before = await _aggregate(day_before_yesterday, day_before_yesterday)
    p_d3 = await _aggregate(d3, d3)
    p_d4 = await _aggregate(d4, d4)
    p_d5 = await _aggregate(d5, d5)
    p_d6 = await _aggregate(d6, d6)
    p_7d = await _aggregate(date_7d_ago, today)
    p_15d = await _aggregate(date_15d_ago, today)
    p_30d = await _aggregate(date_30d_ago, today)

    empty = {"visits": 0, "sales": 0, "conversion": 0.0, "avg_price": 0.0, "revenue": 0.0}

    for item in items:
        lid = item["listing_id"]
        item["periods_data"] = PeriodsData(
            today=PeriodMetrics(**(p_today.get(lid, empty))),
            yesterday=PeriodMetrics(**(p_yesterday.get(lid, empty))),
            day_before=PeriodMetrics(**(p_day_before.get(lid, empty))),
            d3=PeriodMetrics(**(p_d3.get(lid, empty))),
            d4=PeriodMetrics(**(p_d4.get(lid, empty))),
            d5=PeriodMetrics(**(p_d5.get(lid, empty))),
            d6=PeriodMetrics(**(p_d6.get(lid, empty))),
            last_7d=PeriodMetrics(**(p_7d.get(lid, empty))),
            last_15d=PeriodMetrics(**(p_15d.get(lid, empty))),
            last_30d=PeriodMetrics(**(p_30d.get(lid, empty))),
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
    target_date = report_date or datetime.now(BRT).date()

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
    ml_account_id: UUID | None = Query(default=None, description="ID da conta ML (opcional para multi-conta)"),
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

    # Extract promotion info from apply result
    has_active_promotion = None
    promo_warning = None
    if apply_result is not None and isinstance(apply_result, dict):
        has_active_promotion = apply_result.get("has_active_promotion")
        promo_warning = apply_result.get("promo_warning")

    promo_finish = None
    if apply_result is not None and isinstance(apply_result, dict):
        promo_finish = apply_result.get("promotion_finish_date", "")[:10]

    if ml_success:
        message = f"Promocao de desconto criada com sucesso (valida ate {promo_finish})"
        if promo_warning:
            message = f"{message}. {promo_warning}"
    else:
        message = "Erro ao criar promocao na API ML"

    return ApplyRecommendationResponse(
        recommendation_id=rec.id,
        mlb_id=listing.mlb_id,
        old_price=float(rec.current_price),
        new_price=float(rec.suggested_price),
        ml_api_success=ml_success,
        message=message,
        has_active_promotion=has_active_promotion,
        promo_warning=promo_warning,
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

    cutoff = datetime.now(BRT).date() - timedelta(days=days)

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


# ─── GET /intel/pricing/email/status ───────────────────────────────────────


@router.get("/email/status")
async def email_status(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """
    Retorna o status da configuracao SMTP atual.

    Nao expoe credenciais — apenas indica se esta configurado e qual host/porta.
    """
    from app.core.config import settings
    from app.core.email import is_smtp_configured

    configured = is_smtp_configured()

    return {
        "configured": configured,
        "host": settings.smtp_host or None,
        "port": settings.smtp_port if configured else None,
        "user": settings.smtp_user or None,
        "from": settings.smtp_from or settings.smtp_user or None,
        "default_to": settings.smtp_to,
        "message": (
            "SMTP configurado e pronto para envio."
            if configured
            else (
                "SMTP nao configurado. Configure as variaveis de ambiente: "
                "SMTP_HOST, SMTP_USER, SMTP_PASS. "
                "Para Gmail: SMTP_HOST=smtp.gmail.com, SMTP_PORT=587, "
                "SMTP_PASS=<App Password de 16 caracteres>."
            )
        ),
    }


# ─── POST /intel/pricing/email/test ────────────────────────────────────────


@router.post("/email/test")
async def test_email(
    current_user: Annotated[User, Depends(get_current_user)],
    to: str | None = None,
) -> dict:
    """
    Envia um email de teste para verificar se o SMTP esta funcionando.

    Se `to` nao for fornecido, usa o email do usuario logado.
    Requer que SMTP esteja configurado.
    """
    import asyncio

    from app.core.config import settings
    from app.core.email import is_smtp_configured, send_html_email

    if not is_smtp_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "SMTP nao configurado. "
                "Defina SMTP_HOST, SMTP_USER e SMTP_PASS nas variaveis de ambiente. "
                "Para Gmail use uma App Password (nao a senha normal)."
            ),
        )

    recipient = to or current_user.email

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head><meta charset="UTF-8"/><title>Teste SMTP MSM_Pro</title></head>
    <body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:20px;">
      <div style="max-width:500px;margin:0 auto;background:#fff;border-radius:8px;
                  overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1);">
        <div style="background:#1e40af;color:#fff;padding:24px 32px;">
          <h1 style="margin:0;font-size:20px;">MSM_Pro — Teste SMTP</h1>
        </div>
        <div style="padding:32px;color:#333;line-height:1.6;">
          <p>Este email confirma que o SMTP esta configurado corretamente.</p>
          <p><strong>Host:</strong> {settings.smtp_host}:{settings.smtp_port}</p>
          <p><strong>Remetente:</strong> {settings.smtp_from or settings.smtp_user}</p>
          <p><strong>Destinatario:</strong> {recipient}</p>
          <p style="margin-top:24px;color:#666;font-size:14px;">
            O Daily Intel Report sera enviado diariamente as 08:00 BRT.
          </p>
        </div>
        <div style="background:#f0f0f0;padding:16px 32px;font-size:12px;
                    color:#888;text-align:center;">
          MSM_Pro — Dashboard de Inteligencia de Vendas
        </div>
      </div>
    </body>
    </html>
    """

    sent = await asyncio.to_thread(
        send_html_email,
        to=recipient,
        subject="[MSM_Pro] Teste de configuracao SMTP",
        html=html,
    )

    if sent:
        logger.info("Email de teste enviado para %s por %s", recipient, current_user.email)
        return {
            "success": True,
            "message": f"Email de teste enviado para {recipient}.",
            "recipient": recipient,
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"Falha ao enviar email para {recipient}. "
                "Verifique os logs do backend para detalhes."
            ),
        )


from fastapi.responses import HTMLResponse as _HTMLResponse  # noqa: E402

@router.get("/daily-report", response_class=_HTMLResponse)
async def daily_report_html(
    current_user: Annotated[User, Depends(get_current_user)],
    report_date: str | None = Query(None, description="YYYY-MM-DD (default: hoje BRT)"),
):
    """
    Renderiza o Daily Intel Report em HTML diretamente no navegador,
    sem precisar de SMTP. Usa o mesmo pipeline da task agendada.
    """
    from fastapi.responses import HTMLResponse
    from app.intel.pricing.service_collector import collect_daily_data
    from app.intel.pricing.service_score import (
        calculate_recommendation_score,
        calculate_health_score,
    )
    from app.intel.pricing.service_report import _build_summary, build_daily_report_html
    from app.intel.pricing.service_weights import get_adaptive_weights
    from app.jobs.tasks_daily_intel import (
        _try_analyze_with_ai,
        _get_daily_conversion_sparkline,
    )
    from app.core.database import AsyncSessionLocal

    if report_date:
        try:
            target_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="report_date deve ser YYYY-MM-DD",
            )
    else:
        target_date = datetime.now(BRT).date()

    anuncios = await collect_daily_data(current_user.id)
    if not anuncios:
        return HTMLResponse(
            content=(
                "<html><body style='font-family:sans-serif;padding:40px'>"
                "<h2>Daily Intel Report</h2>"
                "<p>Sem anuncios ativos para gerar relatorio.</p>"
                "</body></html>"
            ),
            status_code=200,
        )

    async with AsyncSessionLocal() as db_w:
        weights = await get_adaptive_weights(db_w, current_user.id)

    for anuncio in anuncios:
        rec_score = calculate_recommendation_score(anuncio, weights=weights)
        anuncio["recommendation"] = rec_score
        anuncio["health_score"] = calculate_health_score(anuncio)

    try:
        anuncios = await _try_analyze_with_ai(anuncios)
    except Exception as exc:
        logger.warning("AI analyzer falhou no daily-report HTML: %s", exc)

    sparkline_cache: dict = {}
    async with AsyncSessionLocal() as db_s:
        for anuncio in anuncios:
            anuncio["sparkline_values"] = await _get_daily_conversion_sparkline(
                anuncio["listing_id"], sparkline_cache, db_s
            )

    summary = _build_summary(anuncios)
    html = build_daily_report_html(anuncios, summary, target_date)
    return HTMLResponse(content=html, status_code=200)
