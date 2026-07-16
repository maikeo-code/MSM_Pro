from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.concorrencia import service
from app.concorrencia.schemas import CompetitorCreate, CompetitorHistoryOut, CompetitorOut
from app.core.database import get_db
from app.core.deps import get_current_user

router = APIRouter(prefix="/competitors", tags=["competitors"])


@router.get("/", response_model=list[CompetitorOut])
async def list_all_competitors(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Lista todos os concorrentes ativos do usuário."""
    return await service.get_all_competitors(db, current_user.id)


@router.post("/", response_model=CompetitorOut, status_code=status.HTTP_201_CREATED)
async def add_competitor(
    payload: CompetitorCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Vincula um concorrente (MLB externo) a um listing do usuário.
    Busca dados reais do concorrente na API ML para enriquecer os dados (título, seller, thumbnail).
    """
    from sqlalchemy import select
    from app.auth.models import MLAccount
    from app.vendas.models import Listing

    # Busca o listing para obter a conta ML vinculada
    listing_result = await db.execute(
        select(Listing).where(
            Listing.id == payload.listing_id,
            Listing.user_id == current_user.id,
        )
    )
    listing = listing_result.scalar_one_or_none()

    # Busca o token da conta ML do listing
    ml_token = None
    if listing and listing.ml_account_id:
        ml_account_result = await db.execute(
            select(MLAccount).where(MLAccount.id == listing.ml_account_id)
        )
        ml_account = ml_account_result.scalar_one_or_none()
        if ml_account and ml_account.access_token:
            ml_token = ml_account.access_token

    competitor = await service.add_competitor(
        db,
        current_user.id,
        payload.listing_id,
        payload.competitor_mlb_id,
        ml_token=ml_token,
    )
    await db.commit()
    return competitor


@router.get("/listing/{listing_id}", response_model=list[CompetitorOut])
async def get_competitors_by_listing(
    listing_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Lista concorrentes vinculados a um listing específico.
    """
    competitors = await service.get_competitors_by_listing(
        db, current_user.id, listing_id
    )
    return competitors


@router.get("/sku/{product_id}", response_model=list[CompetitorOut])
async def get_competitors_by_sku(
    product_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Lista concorrentes vinculados a um SKU (produto).
    Retorna todos os concorrentes dos listings desse SKU.
    """
    competitors = await service.get_competitors_by_sku(
        db, current_user.id, product_id
    )
    return competitors


@router.delete("/{competitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_competitor(
    competitor_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Remove um concorrente vinculado.
    """
    await service.remove_competitor(db, current_user.id, competitor_id)
    await db.commit()


@router.get("/{competitor_id}/history", response_model=CompetitorHistoryOut)
async def get_competitor_history(
    competitor_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365, description="Numero de dias de historico"),
):
    """
    Retorna historico de preco e vendas de um concorrente nos ultimos N dias.
    Util para gerar grafico de preco ao longo do tempo.
    """
    return await service.get_competitor_history(db, current_user.id, competitor_id, days)


@router.post("/prices/collect")
async def collect_competitor_prices_now(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Dispara a coleta de preço de concorrentes AGORA (síncrono) e retorna o resultado.

    Gatilho manual da task `collect_competitor_prices` (também agendada 09:30 UTC).
    Roda inline (~15 chamadas ML, <30s) para popular `competitor_prices` na hora e
    devolver {collected, failed, day}.
    """
    from app.jobs.tasks_competitor_prices import _collect_competitor_prices_async

    return await _collect_competitor_prices_async()


@router.get("/prices")
async def list_competitor_prices(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    day: str | None = Query(default=None, description="Dia YYYY-MM-DD (default: hoje BRT)"),
):
    """Lista as linhas de `competitor_prices` de um dia (inspeção da coleta)."""
    from datetime import date as _date, datetime as _dt, timedelta as _td, timezone as _tz

    from sqlalchemy import select

    from app.concorrencia.models import CompetitorPrice

    brt = _tz(_td(hours=-3))
    target = _date.fromisoformat(day) if day else _dt.now(brt).date()

    rows = (
        await db.execute(
            select(CompetitorPrice)
            .where(CompetitorPrice.day == target)
            .order_by(CompetitorPrice.id_ml)
        )
    ).scalars().all()

    return {
        "day": str(target),
        "count": len(rows),
        "rows": [
            {
                "id_ml": r.id_ml,
                "price": float(r.price) if r.price is not None else None,
                "sold_quantity": r.sold_quantity,
                "available_quantity": r.available_quantity,
                "status": r.status,
                "is_buy_box": r.is_buy_box,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ],
    }


class _ScrapedPrice(BaseModel):
    id_ml: str
    price: float | None = None
    sold_quantity: int | None = None
    available_quantity: int | None = None
    status: str | None = "active"
    is_buy_box: bool = False


@router.post("/prices/ingest")
async def ingest_competitor_prices(
    payload: list[_ScrapedPrice],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    day: str | None = Query(default=None, description="Dia YYYY-MM-DD (default: hoje BRT)"),
):
    """Ingestão de preços de concorrente raspados EXTERNAMENTE (scraper local).

    A API pública do ML retorna 403 para item de terceiro; o preço vem do JSON-LD
    da página pública, que só é acessível de um IP residencial (o Railway cai no
    muro anti-bot). Por isso um scraper local extrai e faz POST aqui. Upsert por
    (id_ml, day). Ver [[feature-competitor-prices]].
    """
    from datetime import date as _date, datetime as _dt, timedelta as _td, timezone as _tz

    from app.jobs.tasks_competitor_prices import _upsert_competitor_price

    brt = _tz(_td(hours=-3))
    target = _date.fromisoformat(day) if day else _dt.now(brt).date()

    for row in payload:
        await _upsert_competitor_price(
            db, row.id_ml, target, row.price, row.sold_quantity,
            row.available_quantity, row.status, row.is_buy_box,
        )
    await db.commit()
    return {"ingested": len(payload), "day": str(target)}
