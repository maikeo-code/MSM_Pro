from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.database import get_db
from app.core.deps import get_current_user
from app.vendas import service
from app.vendas.schemas import (
    CreatePromotionIn,
    FunnelOut,
    HeatmapOut,
    KpiCompareOut,
    LinkSkuIn,
    ListingAnalysisOut,
    ListingCreate,
    ListingOut,
    MargemResult,
    OrderOut,
    RepricingRuleCreate,
    RepricingRuleOut,
    RepricingRuleUpdate,
    SearchPositionOut,
    SimulatePriceIn,
    SimulatePriceOut,
    SnapshotOut,
    SuggestionApplyIn,
    UpdatePriceIn,
)

router = APIRouter(prefix="/listings", tags=["listings"])


@router.post("/sync")
async def sync_listings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Importa todos os anuncios ativos das contas ML conectadas."""
    return await service.sync_listings_from_ml(db, current_user.id)


@router.get("/", response_model=list[ListingOut])
async def list_listings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: str = Query(
        default="today",
        pattern=r"^(today|7d|15d|30d|60d)$",
        description="Periodo: today (padrao), 7d, 15d, 30d, 60d",
    ),
    page: int = Query(default=1, ge=1, description="Pagina atual (inicio em 1)"),
    per_page: int = Query(
        default=200,
        ge=1,
        le=500,
        description="Itens por pagina (padrao 200 — retorna tudo; reduza para 50 quando paginacao real for necessaria)",
    ),
):
    """Lista todos os anuncios do usuario com o ultimo snapshot ou dados agregados por periodo."""
    return await service.list_listings(db, current_user.id, period=period, page=page, per_page=per_page)


@router.post("/", response_model=ListingOut, status_code=status.HTTP_201_CREATED)
async def create_listing(
    payload: ListingCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Cadastra novo anuncio MLB manualmente."""
    listing = await service.create_listing(db, current_user.id, payload)
    return {
        "id": listing.id,
        "user_id": listing.user_id,
        "product_id": listing.product_id,
        "ml_account_id": listing.ml_account_id,
        "mlb_id": listing.mlb_id,
        "title": listing.title,
        "listing_type": listing.listing_type,
        "price": listing.price,
        "status": listing.status,
        "permalink": listing.permalink,
        "thumbnail": listing.thumbnail,
        "created_at": listing.created_at,
        "updated_at": listing.updated_at,
        "last_snapshot": None,
    }


# ─── Fixed-path routes MUST come before /{mlb_id} to avoid path conflicts ────

@router.get("/export")
async def export_listings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: str = Query(
        default="today",
        pattern=r"^(today|7d|15d|30d|60d)$",
        description="Periodo: today (padrao), 7d, 15d, 30d, 60d",
    ),
):
    """Exporta listings em formato CSV com metricas do periodo solicitado."""
    import csv
    import io

    from fastapi.responses import StreamingResponse

    listings = await service.list_listings(db, current_user.id, period=period)

    def _snap_get(snap, key, default=""):
        """Lê campo de snapshot que pode ser ORM ou dict."""
        if snap is None:
            return default
        val = getattr(snap, key, None)
        if val is None and isinstance(snap, dict):
            val = snap.get(key)
        return val if val is not None else default

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "MLB ID",
        "Titulo",
        "Preco",
        "Estoque",
        "Vendas",
        "Visitas",
        "Conversao %",
        "Receita",
        "Voce Recebe",
    ])

    for item in listings:
        snap = item.get("last_snapshot")
        conv = _snap_get(snap, "conversion_rate")
        conv_str = f"{float(conv):.2f}" if conv not in ("", None) else ""
        writer.writerow([
            item.get("mlb_id", ""),
            item.get("title", ""),
            item.get("price", ""),
            _snap_get(snap, "stock"),
            _snap_get(snap, "sales_today"),
            _snap_get(snap, "visits"),
            conv_str,
            _snap_get(snap, "revenue"),
            item.get("voce_recebe", ""),
        ])

    output.seek(0)
    filename = f"listings_{period}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/kpi/summary")
async def get_kpi_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Retorna KPIs agregados para hoje, ontem e anteontem."""
    return await service.get_kpi_by_period(db, current_user.id)


@router.get("/kpi/compare")
async def get_kpi_compare(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period_a: str = Query(
        default="7d",
        pattern=r"^(7d|15d|30d)$",
        description="Periodo A: 7d, 15d ou 30d",
    ),
    period_b: str = Query(
        default="prev",
        pattern=r"^(prev|7d|15d|30d)$",
        description="Periodo B: prev (anterior equivalente), 7d, 15d ou 30d",
    ),
):
    """
    Compara KPIs entre dois periodos e retorna variacao percentual para cada metrica.

    Exemplos:
    - period_a=7d&period_b=prev  → ultimos 7 dias vs 7 dias anteriores
    - period_a=30d&period_b=7d   → ultimos 30 dias vs ultimos 7 dias
    - period_a=15d&period_b=prev → ultimos 15 dias vs 15 dias anteriores
    """
    return await service.get_kpi_compare(db, current_user.id, period_a, period_b)


@router.get("/analytics/funnel", response_model=FunnelOut)
async def get_funnel(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: str = Query(default="7d", pattern=r"^(7d|15d|30d|60d)$", description="Periodo do funil"),
):
    """Retorna dados do funil de conversao: visitas, vendas, conversao, receita."""
    period_map = {"7d": 7, "15d": 15, "30d": 30, "60d": 60}
    days = period_map.get(period, 7)
    return await service.get_funnel_analytics(db, current_user.id, days)


@router.get("/analytics/heatmap", response_model=HeatmapOut)
async def get_heatmap(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: str = Query(
        default="30d",
        pattern=r"^(7d|15d|30d|60d|90d)$",
        description="Periodo: 7d, 15d, 30d (padrao), 60d, 90d",
    ),
):
    """
    Retorna heatmap de vendas por dia da semana nos ultimos N dias.
    Util para identificar quais dias geram mais vendas.
    Resposta: distribuicao 7 dias com total, media semanal e pico.
    """
    period_map = {"7d": 7, "15d": 15, "30d": 30, "60d": 60, "90d": 90}
    days = period_map.get(period, 30)
    return await service.get_sales_heatmap(db, current_user.id, days)


# ─── Orders ──────────────────────────────────────────────────────────────────

@router.get("/orders/", response_model=list[OrderOut])
async def list_orders(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: str = Query(
        default="7d",
        pattern=r"^(1d|2d|7d|15d|30d|60d)$",
        description="Periodo: 1d, 2d, 7d (padrao), 15d, 30d, 60d",
    ),
    mlb_id: str | None = Query(default=None, description="Filtrar por anuncio MLB"),
):
    """
    Lista pedidos individuais sincronizados do Mercado Livre.
    Filtros: periodo e mlb_id. Ordenado por data de criacao descendente.
    """
    from sqlalchemy import and_, select

    from app.auth.models import MLAccount
    from app.vendas.models import Order

    period_map = {"1d": 1, "2d": 2, "7d": 7, "15d": 15, "30d": 30, "60d": 60}
    days = period_map.get(period, 7)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Subquery: ids das contas ML do usuario
    acc_result = await db.execute(
        select(MLAccount.id).where(
            and_(
                MLAccount.user_id == current_user.id,
                MLAccount.is_active == True,  # noqa: E712
            )
        )
    )
    account_ids = [row[0] for row in acc_result.fetchall()]
    if not account_ids:
        return []

    conditions = [
        Order.ml_account_id.in_(account_ids),
        Order.order_date >= cutoff,
    ]
    if mlb_id:
        mlb_normalized = mlb_id.upper().replace("-", "")
        if not mlb_normalized.startswith("MLB"):
            mlb_normalized = f"MLB{mlb_normalized}"
        conditions.append(Order.mlb_id == mlb_normalized)

    result = await db.execute(
        select(Order)
        .where(and_(*conditions))
        .order_by(Order.order_date.desc())
        .limit(500)
    )
    orders = result.scalars().all()
    return orders


# ─── Repricing Rules ─────────────────────────────────────────────────────────


@router.get("/repricing-rules", response_model=list[RepricingRuleOut])
async def list_repricing_rules(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    listing_id: UUID | None = Query(default=None, description="Filtrar por listing UUID"),
    active_only: bool = Query(default=False, description="Retornar apenas regras ativas"),
):
    """
    Lista todas as regras de reprecificação do usuário.

    Filtros opcionais:
    - listing_id: restringir a um anúncio específico
    - active_only: retornar apenas regras ativas (padrão false = todas)
    """
    from app.vendas.service_price import list_repricing_rules as _list

    return await _list(db, current_user.id, listing_id=listing_id, active_only=active_only)


@router.post(
    "/repricing-rules",
    response_model=RepricingRuleOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_repricing_rule(
    payload: RepricingRuleCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Cria nova regra de reprecificação para um anúncio.

    Tipos suportados:
    - FIXED_MARKUP: preço = custo * value (ex: value=1.4 → 40% markup)
    - COMPETITOR_DELTA: preço = preco_concorrente + value (ex: value=-2.00 → R$2 abaixo)
    - FLOOR_CEILING: limita o preço entre min_price e max_price

    Apenas uma regra ativa por tipo por anúncio é permitida.
    """
    from app.vendas.service_price import create_repricing_rule as _create

    result = await _create(db, current_user.id, payload)
    await db.commit()
    return result


@router.put("/repricing-rules/{rule_id}", response_model=RepricingRuleOut)
async def update_repricing_rule(
    rule_id: UUID,
    payload: RepricingRuleUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Atualiza campos de uma regra de reprecificação existente.

    Apenas os campos enviados no body são alterados (patch semântico via PUT).
    Para desativar a regra, envie is_active=false.
    """
    from app.vendas.service_price import update_repricing_rule as _update

    result = await _update(db, current_user.id, rule_id, payload)
    await db.commit()
    return result


@router.delete("/repricing-rules/{rule_id}")
async def delete_repricing_rule(
    rule_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Desativa (soft delete) uma regra de reprecificação.

    O registro é mantido no banco para auditoria — apenas is_active=false é aplicado.
    """
    from app.vendas.service_price import delete_repricing_rule as _delete

    result = await _delete(db, current_user.id, rule_id)
    await db.commit()
    return result


# ─── Dynamic path routes ─────────────────────────────────────────────────────

@router.get("/{mlb_id}/search-position", response_model=SearchPositionOut)
async def get_search_position(
    mlb_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    keyword: str = Query(..., min_length=2, max_length=200, description="Palavra-chave para buscar no ML"),
):
    """
    Retorna a posicao de um anuncio nos resultados de busca do ML para uma keyword.

    Busca ate 200 resultados (4 paginas x 50) na Search API publica do ML.
    Se o anuncio aparecer, retorna sua posicao (1-based), a pagina e o total de resultados.
    Se nao aparecer nos primeiros 200, retorna found=false.

    Util para monitorar visibilidade organica: se voce esta em top-5, top-10, etc.
    """
    from app.vendas.service_analytics import get_search_position as _get_search_position

    return await _get_search_position(db, mlb_id, current_user.id, keyword)


@router.get("/{mlb_id}", response_model=ListingOut)
async def get_listing(
    mlb_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Busca um anuncio especifico."""
    listing = await service.get_listing(db, mlb_id, current_user.id)
    return listing


@router.get("/{mlb_id}/snapshots", response_model=list[SnapshotOut])
async def get_snapshots(
    mlb_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    dias: int = Query(default=30, ge=1, le=365, description="Numero de dias de historico"),
):
    """Retorna historico de snapshots de um anuncio."""
    return await service.get_listing_snapshots(db, mlb_id, current_user.id, dias)


@router.get("/{mlb_id}/analysis", response_model=ListingAnalysisOut)
async def get_analysis(
    mlb_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365, description="Numero de dias de historico"),
):
    """
    Retorna analise completa de um anuncio:
    - Dados do listing e SKU
    - Snapshots historicos
    - Faixas de preco e margem otima
    - Projecao de estoque
    - Promocoes ativas
    - Dados de publicidade
    - Concorrente vinculado
    - Alertas inteligentes
    """
    return await service.get_listing_analysis(db, mlb_id, current_user.id, days)


@router.get("/{mlb_id}/margem", response_model=MargemResult)
async def get_margem(
    mlb_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    preco: Decimal = Query(..., description="Preco para calcular a margem"),
):
    """Calcula margem para um anuncio com preco informado."""
    return await service.get_margem(db, mlb_id, current_user.id, preco)


@router.get("/{mlb_id}/health")
async def get_listing_health(
    mlb_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=7, le=90),
):
    """Retorna score de saude do anuncio com checklist acionavel."""
    from sqlalchemy import select

    from app.produtos.models import Product

    try:
        listing = await service.get_listing(db, mlb_id, current_user.id)
    except Exception:
        return {
            "mlb_id": mlb_id,
            "score": 0,
            "max_score": 100,
            "status": "critical",
            "label": "Critico",
            "color": "red",
            "checks": [{"item": "Anuncio nao encontrado", "ok": False, "points": 0, "max": 100}],
        }

    product = None
    if listing.product_id:
        prod_result = await db.execute(select(Product).where(Product.id == listing.product_id))
        product = prod_result.scalar_one_or_none()

    snapshots_db = await service.get_listing_snapshots(db, mlb_id, current_user.id, days)
    snapshots = [
        {
            "visits": s.visits,
            "sales_today": s.sales_today,
            "stock": s.stock,
            "conversion_rate": float(s.conversion_rate) if s.conversion_rate else 0,
        }
        for s in snapshots_db
    ]

    health = service._calculate_health_score(listing, snapshots, product)
    health["mlb_id"] = mlb_id
    health["listing_title"] = listing.title
    return health


@router.patch("/{mlb_id}/price")
async def update_price(
    mlb_id: str,
    payload: UpdatePriceIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Altera o preco de um anuncio."""
    return await service.update_listing_price(
        db, mlb_id, current_user.id, Decimal(str(payload.price))
    )


@router.post("/{mlb_id}/promotions")
async def create_promotion(
    mlb_id: str,
    payload: CreatePromotionIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Cria ou renova promocao para um anuncio."""
    return await service.create_or_update_promotion(
        db,
        mlb_id,
        current_user.id,
        payload.discount_pct,
        payload.start_date,
        payload.end_date,
        payload.promotion_id,
    )


@router.post("/{mlb_id}/suggestion_apply")
async def suggestion_apply(
    mlb_id: str,
    payload: SuggestionApplyIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Aplica sugestão de preço da IA: altera preço na API do ML e salva log.
    Respeita original_price/sale_price — se houver promoção ativa, a API pode desativá-la.
    """
    return await service.apply_price_suggestion(
        db, mlb_id, current_user.id, payload.new_price, payload.justification
    )


@router.get("/{mlb_id}/price-history")
async def get_price_history(
    mlb_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200, description="Numero maximo de registros"),
):
    """Retorna historico de mudancas de preco de um anuncio, mais recentes primeiro."""
    from sqlalchemy import desc, select

    from app.vendas.models import PriceChangeLog

    listing = await service.get_listing(db, mlb_id, current_user.id)

    result = await db.execute(
        select(PriceChangeLog)
        .where(PriceChangeLog.listing_id == listing.id)
        .order_by(desc(PriceChangeLog.created_at))
        .limit(limit)
    )
    changes = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "mlb_id": c.mlb_id,
            "old_price": float(c.old_price) if c.old_price is not None else None,
            "new_price": float(c.new_price) if c.new_price is not None else None,
            "source": c.source,
            "justification": c.justification,
            "success": c.success,
            "error_message": c.error_message,
            "changed_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in changes
    ]


@router.post("/{mlb_id}/simulate-price", response_model=SimulatePriceOut)
async def simulate_price(
    mlb_id: str,
    payload: SimulatePriceIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Simula o impacto financeiro de alterar o preco de um anuncio.

    Analisa historico de 90 dias de snapshots, calcula elasticidade por faixa de preco,
    interpola vendas estimadas para o preco alvo e retorna receita e margem projetadas.

    Se houver menos de 7 snapshots historicos, retorna estimativa com is_estimated=true.
    """
    return await service.simulate_price(db, mlb_id, current_user.id, payload.target_price)


@router.patch("/{mlb_id}/sku", response_model=ListingOut)
async def link_sku(
    mlb_id: str,
    payload: LinkSkuIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Vincula ou desvincula um SKU/produto a um anuncio. Enviar product_id=null para desvincular."""
    result = await service.link_sku_to_listing(db, mlb_id, current_user.id, payload.product_id)
    await db.commit()
    return result
