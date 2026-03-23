from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.concorrencia.models import Competitor, CompetitorSnapshot
from app.concorrencia.schemas import CompetitorCreate, CompetitorHistoryOut, CompetitorOut
from app.mercadolivre.client import MLClient, MLClientError
from app.vendas.models import Listing


async def _enrich_competitor_from_ml(
    competitor: Competitor,
    ml_token: str,
) -> None:
    """
    Busca dados reais do concorrente na API ML e popula title, seller_nickname, thumbnail.
    Erros de API são silenciados — se falhar, o competitor é salvo com dados parciais.
    """
    try:
        async with MLClient(ml_token) as client:
            item_data = await client.get_item(competitor.mlb_id)

            # Extrai título
            if "title" in item_data:
                competitor.title = item_data["title"]

            # Extrai seller_nickname (seller.nickname)
            if "seller" in item_data and isinstance(item_data["seller"], dict):
                competitor.seller_nickname = item_data["seller"].get("nickname")

            # Extrai thumbnail URL
            if "thumbnail" in item_data:
                competitor.thumbnail = item_data["thumbnail"]
    except MLClientError as e:
        # Log silencioso — o concorrente é criado mesmo se o enriquecimento falhar
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Falha ao enriquecer competitor {competitor.mlb_id}: {str(e)}"
        )
    except Exception as e:
        # Qualquer outro erro também é silencioso
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Erro inesperado ao enriquecer competitor {competitor.mlb_id}: {str(e)}"
        )


async def add_competitor(
    db: AsyncSession,
    user_id: UUID,
    listing_id: UUID,
    competitor_mlb_id: str,
    ml_token: str | None = None,
) -> Competitor:
    """
    Vincula um concorrente (MLB externo) a um listing do usuário.
    Se ml_token for fornecido, busca e enriquece dados reais do concorrente imediatamente.
    """
    # Valida que o listing pertence ao usuário
    listing_result = await db.execute(
        select(Listing).where(
            Listing.id == listing_id,
            Listing.user_id == user_id,
        )
    )
    listing = listing_result.scalar_one_or_none()
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing não encontrado ou não pertence ao usuário",
        )

    # Normaliza MLB ID
    competitor_id = competitor_mlb_id.upper().replace("-", "")
    if not competitor_id.startswith("MLB"):
        competitor_id = f"MLB{competitor_id}"

    # Verifica se já existe
    existing_result = await db.execute(
        select(Competitor).where(
            Competitor.listing_id == listing_id,
            Competitor.mlb_id == competitor_id,
        )
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Concorrente '{competitor_id}' já vinculado a este listing",
        )

    competitor = Competitor(
        listing_id=listing_id,
        mlb_id=competitor_id,
        is_active=True,
    )

    # Enriquece com dados da API ML se token for fornecido
    if ml_token:
        await _enrich_competitor_from_ml(competitor, ml_token)

    db.add(competitor)
    await db.flush()
    await db.refresh(competitor)
    return competitor


async def get_all_competitors(
    db: AsyncSession,
    user_id: UUID,
) -> list[Competitor]:
    """Lista todos os concorrentes ativos do usuário."""
    result = await db.execute(
        select(Competitor)
        .join(Listing, Competitor.listing_id == Listing.id)
        .where(
            Listing.user_id == user_id,
            Competitor.is_active == True,  # noqa: E712
        )
        .order_by(Competitor.created_at.desc())
        .limit(200)
    )
    return list(result.scalars().all())


async def get_competitors_by_listing(
    db: AsyncSession,
    user_id: UUID,
    listing_id: UUID,
) -> list[Competitor]:
    """
    Lista concorrentes vinculados a um listing específico.
    """
    # Valida que o listing pertence ao usuário
    listing_result = await db.execute(
        select(Listing).where(
            Listing.id == listing_id,
            Listing.user_id == user_id,
        )
    )
    listing = listing_result.scalar_one_or_none()
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing não encontrado",
        )

    result = await db.execute(
        select(Competitor)
        .where(
            Competitor.listing_id == listing_id,
            Competitor.is_active == True,  # noqa: E712
        )
        .order_by(Competitor.created_at.desc())
    )
    return list(result.scalars().all())


async def get_competitors_by_sku(
    db: AsyncSession,
    user_id: UUID,
    product_id: UUID,
) -> list[Competitor]:
    """
    Lista concorrentes vinculados a um SKU (retorna todos os competidores
    dos listings desse SKU).
    """
    from app.produtos.models import Product

    # Valida que o SKU pertence ao usuário
    product_result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.user_id == user_id,
        )
    )
    product = product_result.scalar_one_or_none()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SKU não encontrado",
        )

    # Busca listings do SKU
    listings_result = await db.execute(
        select(Listing).where(
            Listing.product_id == product_id,
            Listing.user_id == user_id,
        )
    )
    listings = listings_result.scalars().all()

    if not listings:
        return []

    listing_ids = [l.id for l in listings]

    # Busca competidores de todos esses listings
    competitors_result = await db.execute(
        select(Competitor)
        .where(
            Competitor.listing_id.in_(listing_ids),
            Competitor.is_active == True,  # noqa: E712
        )
        .order_by(Competitor.created_at.desc())
    )
    return list(competitors_result.scalars().all())


async def remove_competitor(
    db: AsyncSession,
    user_id: UUID,
    competitor_id: UUID,
) -> None:
    """
    Remove um concorrente vinculado (soft-delete via is_active=False).
    """
    # Busca o competidor e valida que pertence a um listing do usuário
    competitor_result = await db.execute(
        select(Competitor)
        .join(Listing, Competitor.listing_id == Listing.id)
        .where(
            Competitor.id == competitor_id,
            Listing.user_id == user_id,
        )
    )
    competitor = competitor_result.scalar_one_or_none()
    if not competitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Concorrente não encontrado",
        )

    competitor.is_active = False
    await db.flush()


async def get_competitor_history(
    db: AsyncSession,
    user_id: UUID,
    competitor_id: UUID,
    days: int = 30,
) -> CompetitorHistoryOut:
    """
    Retorna o historico de snapshots de um concorrente nos ultimos N dias.
    Validacao de ownership via join com Listing.
    """
    # Valida que o competitor pertence a um listing do usuario
    comp_result = await db.execute(
        select(Competitor)
        .join(Listing, Competitor.listing_id == Listing.id)
        .where(
            Competitor.id == competitor_id,
            Listing.user_id == user_id,
        )
    )
    competitor = comp_result.scalar_one_or_none()
    if not competitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Concorrente nao encontrado ou nao pertence ao usuario",
        )

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    snaps_result = await db.execute(
        select(CompetitorSnapshot)
        .where(
            CompetitorSnapshot.competitor_id == competitor_id,
            CompetitorSnapshot.captured_at >= cutoff,
        )
        .order_by(CompetitorSnapshot.captured_at.asc())
    )
    snapshots = snaps_result.scalars().all()

    from app.concorrencia.schemas import CompetitorHistoryItem

    history = [
        CompetitorHistoryItem(
            date=snap.captured_at,
            price=snap.price,
            sold_quantity=snap.sold_quantity,
            sales_delta=snap.sales_delta,
        )
        for snap in snapshots
    ]

    return CompetitorHistoryOut(
        competitor_id=competitor_id,
        mlb_id=competitor.mlb_id,
        title=competitor.title,
        days=days,
        history=history,
    )
