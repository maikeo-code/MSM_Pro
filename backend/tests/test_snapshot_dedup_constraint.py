"""
Trava de regressão (Fase 0 do plano anti-inflação de KPIs).

Garante a invariante introduzida na migration 0033: NO MÁXIMO 1 snapshot por
anúncio por dia (BRT). É esta trava que impede a duplicação que inflava
visitas/vendas (ex.: 9 snapshots no dia 08/06 → 128 mil visitas).

São testes em SQLite (mesma engine dos demais), validando o model + listener +
UniqueConstraint(listing_id, snapshot_day).
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.auth.models import MLAccount, User
from app.vendas.models import Listing, ListingSnapshot


async def _setup_listing(db):
    user = User(id=uuid4(), email=f"{uuid4()}@t.com", hashed_password="x")
    db.add(user)
    ml = MLAccount(
        id=uuid4(), user_id=user.id, ml_user_id="1",
        nickname="t", access_token="x", refresh_token="y",
    )
    db.add(ml)
    listing = Listing(
        id=uuid4(), user_id=user.id, ml_account_id=ml.id,
        mlb_id="MLB1", title="t", price=Decimal("100"), status="active",
    )
    db.add(listing)
    await db.flush()
    return listing


@pytest.mark.asyncio
async def test_listener_popula_snapshot_day_em_brt(db):
    """captured_at 02:00 UTC do dia 09 → snapshot_day = 08 (BRT, -3h)."""
    listing = await _setup_listing(db)
    snap = ListingSnapshot(
        id=uuid4(), listing_id=listing.id, price=Decimal("100"),
        captured_at=datetime(2026, 6, 9, 2, 0, tzinfo=timezone.utc),
    )
    db.add(snap)
    await db.commit()
    assert snap.snapshot_day == date(2026, 6, 8)


@pytest.mark.asyncio
async def test_constraint_impede_dois_snapshots_no_mesmo_dia(db):
    """O 2º snapshot do mesmo anúncio no mesmo dia deve ser REJEITADO."""
    listing = await _setup_listing(db)
    ca = datetime(2026, 6, 9, 15, 0, tzinfo=timezone.utc)  # 12:00 BRT, dia 09
    db.add(ListingSnapshot(
        id=uuid4(), listing_id=listing.id, price=Decimal("100"), visits=10, captured_at=ca,
    ))
    await db.commit()

    db.add(ListingSnapshot(
        id=uuid4(), listing_id=listing.id, price=Decimal("100"), visits=999, captured_at=ca,
    ))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


@pytest.mark.asyncio
async def test_constraint_permite_dias_distintos(db):
    """Snapshots do mesmo anúncio em dias diferentes são permitidos."""
    listing = await _setup_listing(db)
    db.add(ListingSnapshot(
        id=uuid4(), listing_id=listing.id, price=Decimal("100"),
        captured_at=datetime(2026, 6, 9, 15, 0, tzinfo=timezone.utc),
    ))
    db.add(ListingSnapshot(
        id=uuid4(), listing_id=listing.id, price=Decimal("100"),
        captured_at=datetime(2026, 6, 10, 15, 0, tzinfo=timezone.utc),
    ))
    await db.commit()  # não deve levantar

    from sqlalchemy import select, func
    total = await db.scalar(
        select(func.count()).select_from(ListingSnapshot).where(
            ListingSnapshot.listing_id == listing.id
        )
    )
    assert total == 2
