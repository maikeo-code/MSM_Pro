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
    ListingAnalysisOut,
    ListingCreate,
    ListingOut,
    MargemResult,
    SnapshotOut,
    UpdatePriceIn,
)

router = APIRouter(prefix="/listings", tags=["listings"])


@router.post("/sync")
async def sync_listings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Importa todos os anúncios ativos das contas ML conectadas."""
    return await service.sync_listings_from_ml(db, current_user.id)


@router.get("/", response_model=list[ListingOut])
async def list_listings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Lista todos os anúncios do usuário com o último snapshot."""
    return await service.list_listings(db, current_user.id)


@router.post("/", response_model=ListingOut, status_code=status.HTTP_201_CREATED)
async def create_listing(
    payload: ListingCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Cadastra novo anúncio MLB manualmente."""
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


@router.get("/{mlb_id}", response_model=ListingOut)
async def get_listing(
    mlb_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Busca um anúncio específico."""
    listing = await service.get_listing(db, mlb_id, current_user.id)
    return listing


@router.get("/{mlb_id}/snapshots", response_model=list[SnapshotOut])
async def get_snapshots(
    mlb_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    dias: int = Query(default=30, ge=1, le=365, description="Número de dias de histórico"),
):
    """Retorna histórico de snapshots de um anúncio."""
    return await service.get_listing_snapshots(db, mlb_id, current_user.id, dias)


@router.get("/{mlb_id}/analysis", response_model=ListingAnalysisOut)
async def get_analysis(
    mlb_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365, description="Número de dias de histórico"),
):
    """
    Retorna análise completa de um anúncio:
    - Dados do listing e SKU
    - Snapshots históricos
    - Faixas de preço e margem ótima
    - Projeção de estoque
    - Promoções ativas
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
    preco: Decimal = Query(..., description="Preço para calcular a margem"),
):
    """Calcula margem para um anúncio com preço informado."""
    return await service.get_margem(db, mlb_id, current_user.id, preco)


@router.get("/{mlb_id}/health")
async def get_listing_health(
    mlb_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=7, le=90),
):
    """Retorna score de saúde do anúncio com checklist acionável."""
    from sqlalchemy import select

    from app.produtos.models import Product

    try:
        listing = await service.get_listing(db, mlb_id, current_user.id)
    except Exception:
        # Listing não encontrado — retorna score zerado
        return {
            "mlb_id": mlb_id,
            "score": 0,
            "max_score": 100,
            "status": "critical",
            "label": "Crítico",
            "color": "red",
            "checks": [{"item": "Anúncio não encontrado", "ok": False, "points": 0, "max": 100}],
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
    """Altera o preço de um anúncio."""
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
    """Cria ou renova promoção para um anúncio."""
    return await service.create_or_update_promotion(
        db,
        mlb_id,
        current_user.id,
        payload.discount_pct,
        payload.start_date,
        payload.end_date,
        payload.promotion_id,
    )


@router.get("/kpi/summary")
async def get_kpi_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Retorna KPIs agregados para hoje, ontem e anteontem."""
    return await service.get_kpi_by_period(db, current_user.id)
