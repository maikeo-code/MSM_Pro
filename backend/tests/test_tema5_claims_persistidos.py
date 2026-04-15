"""
Tema 5 — Claims persistidos localmente (reclamacoes).

Valida:
1. Model Claim criado e aceita persistencia
2. list_claims_from_db filtra por status, mlb_id, claim_type
3. mark_claim_resolved marca resolucao e rejeita tipo invalido
4. find_similar_resolved_claims busca historico do mesmo mlb
5. get_claim_stats retorna contadores
6. Join com Listing enriquece thumbnail/permalink
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.atendimento.models import Claim
from app.atendimento.service_claims import (
    find_similar_resolved_claims,
    get_claim_stats,
    list_claims_from_db,
    mark_claim_resolved,
)
from app.auth.models import MLAccount, User
from app.vendas.models import Listing


async def _make_user_account(db):
    u = User(id=uuid4(), email=f"u{uuid4().hex[:8]}@t.com", hashed_password="x")
    db.add(u)
    acc = MLAccount(
        id=uuid4(),
        user_id=u.id,
        ml_user_id="12345",
        nickname="T",
        access_token="x",
        refresh_token="y",
    )
    db.add(acc)
    await db.flush()
    return u, acc


async def _make_claim(
    db, account_id, *, claim_id="CLM-1", mlb="MLB-1",
    status="open", resolution_type=None, claim_type="reclamacao",
    resolved_days_ago=None,
):
    c = Claim(
        id=uuid4(),
        ml_claim_id=claim_id,
        ml_account_id=account_id,
        claim_type=claim_type,
        status=status,
        reason="produto_nao_recebido",
        mlb_id=mlb,
        date_created=datetime.now(timezone.utc) - timedelta(days=3),
        resolution_type=resolution_type,
        resolved_at=(
            datetime.now(timezone.utc) - timedelta(days=resolved_days_ago)
            if resolved_days_ago is not None else None
        ),
    )
    db.add(c)
    return c


# ─── Model basico ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_claim_model_pode_ser_persistido(db):
    u, acc = await _make_user_account(db)
    await _make_claim(db, acc.id)
    await db.commit()

    from sqlalchemy import select
    r = await db.execute(select(Claim))
    claims = r.scalars().all()
    assert len(claims) == 1
    assert claims[0].ml_claim_id == "CLM-1"


# ─── list_claims_from_db ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_claims_filtro_status(db):
    u, acc = await _make_user_account(db)
    await _make_claim(db, acc.id, claim_id="A", status="open")
    await _make_claim(db, acc.id, claim_id="B", status="closed")
    await _make_claim(db, acc.id, claim_id="C", status="open")
    await db.commit()

    items, total = await list_claims_from_db(db, u.id, status="open")
    assert total == 2
    assert all(i["status"] == "open" for i in items)


@pytest.mark.asyncio
async def test_list_claims_filtro_mlb_id(db):
    u, acc = await _make_user_account(db)
    await _make_claim(db, acc.id, claim_id="A", mlb="MLB-1")
    await _make_claim(db, acc.id, claim_id="B", mlb="MLB-2")
    await db.commit()

    items, total = await list_claims_from_db(db, u.id, mlb_id="MLB-1")
    assert total == 1
    assert items[0]["mlb_id"] == "MLB-1"


@pytest.mark.asyncio
async def test_list_claims_paginacao(db):
    u, acc = await _make_user_account(db)
    for i in range(5):
        await _make_claim(db, acc.id, claim_id=f"C{i}")
    await db.commit()

    items, total = await list_claims_from_db(db, u.id, limit=2, offset=0)
    assert total == 5
    assert len(items) == 2


@pytest.mark.asyncio
async def test_list_claims_enriquece_thumbnail_via_join(db):
    u, acc = await _make_user_account(db)
    listing = Listing(
        id=uuid4(),
        user_id=u.id,
        ml_account_id=acc.id,
        mlb_id="MLB-COM-IMG",
        title="Fone Teste",
        price=Decimal("100"),
        status="active",
        thumbnail="https://http2.mlstatic.com/x.jpg",
        permalink="https://produto.mercadolivre.com.br/MLB-COM-IMG",
    )
    db.add(listing)
    await _make_claim(db, acc.id, mlb="MLB-COM-IMG")
    await db.commit()

    items, _ = await list_claims_from_db(db, u.id)
    assert len(items) == 1
    assert items[0]["item_thumbnail"] == "https://http2.mlstatic.com/x.jpg"
    assert items[0]["item_permalink"] == "https://produto.mercadolivre.com.br/MLB-COM-IMG"
    assert items[0]["item_title"] == "Fone Teste"


@pytest.mark.asyncio
async def test_list_claims_sem_listing_retorna_none(db):
    u, acc = await _make_user_account(db)
    await _make_claim(db, acc.id, mlb="MLB-SEM-LISTING")
    await db.commit()

    items, _ = await list_claims_from_db(db, u.id)
    assert items[0]["item_thumbnail"] is None
    assert items[0]["item_permalink"] is None


# ─── mark_claim_resolved ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mark_claim_resolved_salva_metadata(db):
    u, acc = await _make_user_account(db)
    c = await _make_claim(db, acc.id)
    await db.commit()

    updated = await mark_claim_resolved(
        db, u.id, c.id,
        resolution_type="refund",
        notes="Devolucao imediata processada",
    )
    assert updated.resolution_type == "refund"
    assert updated.resolved_at is not None
    assert updated.resolution_notes == "Devolucao imediata processada"


@pytest.mark.asyncio
async def test_mark_claim_resolved_tipo_invalido(db):
    u, acc = await _make_user_account(db)
    c = await _make_claim(db, acc.id)
    await db.commit()

    with pytest.raises(ValueError, match="invalido"):
        await mark_claim_resolved(db, u.id, c.id, resolution_type="xpto")


@pytest.mark.asyncio
async def test_mark_claim_resolved_usuario_errado(db):
    u, acc = await _make_user_account(db)
    c = await _make_claim(db, acc.id)
    await db.commit()

    other_user_id = uuid4()
    with pytest.raises(ValueError, match="nao encontrado"):
        await mark_claim_resolved(
            db, other_user_id, c.id, resolution_type="refund"
        )


# ─── find_similar_resolved_claims ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_find_similar_resolved_do_mesmo_mlb(db):
    u, acc = await _make_user_account(db)
    # Duas claims resolvidas do mesmo MLB + uma nao resolvida
    await _make_claim(
        db, acc.id, claim_id="R1", mlb="MLB-X",
        resolution_type="refund", resolved_days_ago=5,
    )
    await _make_claim(
        db, acc.id, claim_id="R2", mlb="MLB-X",
        resolution_type="replace", resolved_days_ago=2,
    )
    await _make_claim(db, acc.id, claim_id="NR", mlb="MLB-X")  # sem resolution_type
    # Claim resolvida mas de outro MLB
    await _make_claim(
        db, acc.id, claim_id="R-OUTRO", mlb="MLB-Y",
        resolution_type="refund", resolved_days_ago=1,
    )
    await db.commit()

    similar = await find_similar_resolved_claims(db, u.id, "MLB-X")
    assert len(similar) == 2
    # Mais recente primeiro
    assert similar[0]["ml_claim_id"] == "R2"
    assert similar[1]["ml_claim_id"] == "R1"


# ─── get_claim_stats ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stats_contadores(db):
    u, acc = await _make_user_account(db)
    await _make_claim(db, acc.id, claim_id="1", status="open")
    await _make_claim(db, acc.id, claim_id="2", status="waiting_for_seller_response")
    await _make_claim(
        db, acc.id, claim_id="3", status="closed",
        resolution_type="refund", resolved_days_ago=1,
    )
    await db.commit()

    stats = await get_claim_stats(db, u.id)
    assert stats["total"] == 3
    assert stats["open"] == 2  # open + waiting_for_seller_response
    assert stats["resolved"] == 1
    assert stats["unresolved"] == 2


@pytest.mark.asyncio
async def test_stats_sem_claims_retorna_zeros(db):
    u, _ = await _make_user_account(db)
    await db.commit()
    stats = await get_claim_stats(db, u.id)
    assert stats == {"total": 0, "open": 0, "resolved": 0, "unresolved": 0}
