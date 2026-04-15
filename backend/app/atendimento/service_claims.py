"""
Service de persistencia de claims (reclamacoes e devolucoes) — Tema 5.

Responsavel por:
- Sincronizar claims da API ML para a tabela `claims`
- Listar claims persistidos com filtros
- Buscar claims similares (historico de solucoes)
- Marcar resolucao/notas quando usuario resolve

A logica de fetch em tempo real continua em `service.py` (funcao
`get_all_atendimentos`). Este arquivo complementa com persistencia.
"""
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.atendimento.models import Claim
from app.auth.models import MLAccount
from app.mercadolivre.client import MLClient, MLClientError

logger = logging.getLogger(__name__)


def _parse_dt(value: str | None) -> datetime:
    """Converte string ISO 8601 para datetime UTC."""
    if not value:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def _extract_buyer(payload: dict) -> tuple[int | None, str | None]:
    """Tenta extrair buyer_id/nickname de multiplos formatos do payload ML."""
    # Formato 1: players[].role == 'complainant'
    players = payload.get("players") or []
    if isinstance(players, list):
        for p in players:
            if isinstance(p, dict) and p.get("role") == "complainant":
                uid = p.get("user_id")
                try:
                    return (int(uid) if uid else None, str(uid) if uid else None)
                except (ValueError, TypeError):
                    return (None, str(uid) if uid else None)
    # Formato 2: buyer direto
    buyer = payload.get("buyer") or {}
    if buyer:
        try:
            bid = buyer.get("id")
            return (
                int(bid) if bid else None,
                buyer.get("nickname"),
            )
        except (ValueError, TypeError):
            pass
    return (None, None)


def _extract_order_and_item(payload: dict) -> tuple[str | None, str | None]:
    """Extrai ml_order_id e mlb_id do payload de claim."""
    resource = payload.get("resource") or {}
    if not isinstance(resource, dict):
        return (None, None)
    order_id = resource.get("order_id")
    item_id = resource.get("item_id")
    return (
        str(order_id) if order_id else None,
        str(item_id) if item_id else None,
    )


async def sync_claims_for_account(
    db: AsyncSession,
    account: MLAccount,
    claim_type: str = "reclamacao",
) -> dict:
    """
    Sincroniza claims de uma conta ML para o banco local (upsert por ml_claim_id).

    Busca claims em varios statuses relevantes (open, opened,
    waiting_for_seller_response) e tambem closed para historico.
    """
    if not account.access_token:
        return {"synced": 0, "new": 0, "updated": 0, "errors": 0}

    synced = 0
    new = 0
    updated = 0
    errors = 0

    statuses_to_search = [
        "open", "opened", "waiting_for_seller_response", "closed"
    ]

    try:
        async with MLClient(account.access_token) as client:
            for st in statuses_to_search:
                try:
                    data = await client.get_claims(
                        seller_id=str(account.ml_user_id),
                        status=st,
                        limit=50,
                    )
                except MLClientError as exc:
                    logger.warning(
                        "Sync claims: falha status=%s conta=%s: %s",
                        st, account.id, exc,
                    )
                    errors += 1
                    continue
                except Exception as exc:
                    logger.error(
                        "Sync claims: erro inesperado status=%s conta=%s: %s",
                        st, account.id, exc, exc_info=True,
                    )
                    errors += 1
                    continue

                claims_raw = data.get("data") or data.get("results") or []
                if not isinstance(claims_raw, list):
                    continue

                for raw in claims_raw:
                    # Filtrar apenas claims do tipo desejado
                    if claim_type == "reclamacao":
                        if str(raw.get("claim_type", "")).lower() == "return":
                            continue

                    claim_id = str(raw.get("id") or "")
                    if not claim_id:
                        continue

                    buyer_id, buyer_nick = _extract_buyer(raw)
                    order_id, mlb = _extract_order_and_item(raw)

                    reason = (
                        raw.get("reason_id")
                        or raw.get("subject")
                        or raw.get("reason")
                    )
                    description = raw.get("description") or raw.get("text")

                    ml_suggestion = None
                    resolution = raw.get("resolution")
                    if isinstance(resolution, dict):
                        ml_suggestion = (
                            resolution.get("reason")
                            or resolution.get("benefited")
                            or None
                        )

                    # Upsert
                    existing_q = await db.execute(
                        select(Claim).where(Claim.ml_claim_id == claim_id)
                    )
                    existing = existing_q.scalar_one_or_none()

                    if existing is None:
                        c = Claim(
                            id=uuid4(),
                            ml_claim_id=claim_id,
                            ml_account_id=account.id,
                            claim_type=claim_type,
                            status=str(raw.get("status", "open")).lower(),
                            reason=reason,
                            description=description,
                            ml_order_id=order_id,
                            mlb_id=mlb,
                            item_title=None,
                            buyer_id=buyer_id,
                            buyer_nickname=buyer_nick,
                            date_created=_parse_dt(raw.get("date_created")),
                            date_updated=_parse_dt(raw.get("last_updated"))
                            if raw.get("last_updated") else None,
                            ml_suggestion=ml_suggestion,
                            raw_payload=raw,
                        )
                        db.add(c)
                        new += 1
                    else:
                        existing.status = str(raw.get("status", existing.status)).lower()
                        if raw.get("last_updated"):
                            existing.date_updated = _parse_dt(raw.get("last_updated"))
                        if ml_suggestion and not existing.ml_suggestion:
                            existing.ml_suggestion = ml_suggestion
                        existing.raw_payload = raw
                        updated += 1

                    synced += 1

            await db.commit()

    except Exception as exc:
        logger.error(
            "Sync claims: erro geral conta=%s: %s",
            account.id, exc, exc_info=True,
        )
        errors += 1

    return {
        "synced": synced,
        "new": new,
        "updated": updated,
        "errors": errors,
    }


async def list_claims_from_db(
    db: AsyncSession,
    user_id: UUID,
    status: str | None = None,
    mlb_id: str | None = None,
    claim_type: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[dict], int]:
    """
    Lista claims persistidos com filtros e paginacao.

    Enriquece cada claim com thumbnail/permalink do Listing vinculado
    (mesma logica de Tema 4 em perguntas).
    """
    from app.vendas.models import Listing

    filters = [MLAccount.user_id == user_id]
    if status:
        filters.append(Claim.status == status)
    if mlb_id:
        filters.append(Claim.mlb_id == mlb_id)
    if claim_type:
        filters.append(Claim.claim_type == claim_type)

    # Count
    count_q = (
        select(func.count(Claim.id))
        .select_from(Claim)
        .join(MLAccount, Claim.ml_account_id == MLAccount.id)
        .where(and_(*filters))
    )
    count_result = await db.execute(count_q)
    total = count_result.scalar() or 0

    # List with JOIN to Listing
    q = (
        select(
            Claim,
            Listing.thumbnail.label("listing_thumbnail"),
            Listing.permalink.label("listing_permalink"),
            Listing.title.label("listing_title"),
        )
        .join(MLAccount, Claim.ml_account_id == MLAccount.id)
        .outerjoin(
            Listing,
            and_(
                Listing.mlb_id == Claim.mlb_id,
                Listing.ml_account_id == Claim.ml_account_id,
            ),
        )
        .where(and_(*filters))
        .order_by(desc(Claim.date_created))
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(q)
    rows = result.all()

    items: list[dict] = []
    for row in rows:
        c: Claim = row[0]
        items.append(
            {
                "id": c.id,
                "ml_claim_id": c.ml_claim_id,
                "ml_account_id": c.ml_account_id,
                "claim_type": c.claim_type,
                "status": c.status,
                "reason": c.reason,
                "description": c.description,
                "ml_order_id": c.ml_order_id,
                "mlb_id": c.mlb_id,
                "item_title": c.item_title or row.listing_title,
                "item_thumbnail": row.listing_thumbnail,
                "item_permalink": row.listing_permalink,
                "buyer_id": c.buyer_id,
                "buyer_nickname": c.buyer_nickname,
                "date_created": c.date_created,
                "date_updated": c.date_updated,
                "resolved_at": c.resolved_at,
                "resolution_type": c.resolution_type,
                "resolution_notes": c.resolution_notes,
                "ml_suggestion": c.ml_suggestion,
                "synced_at": c.synced_at,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
            }
        )

    return items, total


async def find_similar_resolved_claims(
    db: AsyncSession,
    user_id: UUID,
    mlb_id: str,
    limit: int = 5,
) -> list[dict]:
    """
    Busca claims ja resolvidas para o MESMO anuncio — serve de base
    para sugerir solucao para uma nova reclamacao no mesmo produto.
    """
    q = (
        select(Claim)
        .join(MLAccount, Claim.ml_account_id == MLAccount.id)
        .where(
            MLAccount.user_id == user_id,
            Claim.mlb_id == mlb_id,
            Claim.resolution_type.isnot(None),
        )
        .order_by(desc(Claim.resolved_at))
        .limit(limit)
    )
    result = await db.execute(q)
    claims = result.scalars().all()

    return [
        {
            "ml_claim_id": c.ml_claim_id,
            "reason": c.reason,
            "resolution_type": c.resolution_type,
            "resolution_notes": c.resolution_notes,
            "ml_suggestion": c.ml_suggestion,
            "resolved_at": c.resolved_at,
        }
        for c in claims
    ]


async def mark_claim_resolved(
    db: AsyncSession,
    user_id: UUID,
    claim_id: UUID,
    resolution_type: str,
    notes: str | None = None,
) -> Claim:
    """
    Marca um claim como resolvido localmente (nao altera no ML).
    Serve para construir historico de como o vendedor costuma resolver.

    resolution_type: refund | replace | partial_refund | kept | ml_suggested
    """
    VALID = {"refund", "replace", "partial_refund", "kept", "ml_suggested"}
    if resolution_type not in VALID:
        raise ValueError(
            f"resolution_type invalido. Use: {', '.join(sorted(VALID))}"
        )

    result = await db.execute(
        select(Claim)
        .join(MLAccount, Claim.ml_account_id == MLAccount.id)
        .where(
            Claim.id == claim_id,
            MLAccount.user_id == user_id,
        )
    )
    claim = result.scalar_one_or_none()
    if not claim:
        raise ValueError("Claim nao encontrado ou sem permissao")

    claim.resolution_type = resolution_type
    if notes:
        claim.resolution_notes = notes
    claim.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return claim


async def get_claim_stats(
    db: AsyncSession,
    user_id: UUID,
) -> dict[str, Any]:
    """Estatisticas agregadas de claims (para badges/dashboard)."""
    base = (
        select(Claim)
        .join(MLAccount, Claim.ml_account_id == MLAccount.id)
        .where(MLAccount.user_id == user_id)
    )

    total_q = await db.execute(
        select(func.count(Claim.id))
        .select_from(Claim)
        .join(MLAccount, Claim.ml_account_id == MLAccount.id)
        .where(MLAccount.user_id == user_id)
    )
    total = total_q.scalar() or 0

    open_statuses = ["open", "opened", "waiting_for_seller_response"]
    open_q = await db.execute(
        select(func.count(Claim.id))
        .select_from(Claim)
        .join(MLAccount, Claim.ml_account_id == MLAccount.id)
        .where(
            MLAccount.user_id == user_id,
            Claim.status.in_(open_statuses),
        )
    )
    open_count = open_q.scalar() or 0

    resolved_q = await db.execute(
        select(func.count(Claim.id))
        .select_from(Claim)
        .join(MLAccount, Claim.ml_account_id == MLAccount.id)
        .where(
            MLAccount.user_id == user_id,
            Claim.resolution_type.isnot(None),
        )
    )
    resolved = resolved_q.scalar() or 0

    return {
        "total": total,
        "open": open_count,
        "resolved": resolved,
        "unresolved": total - resolved,
    }
