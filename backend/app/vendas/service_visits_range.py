"""Visitas por dia de UM anúncio num período — read-only, não grava nada.

Usado pelo Conselho de Preços (JARVIS) para preencher dias sem snapshot.
NÃO usar /listings/backfill-snapshots para isso: ele sobrescreve preço/estoque
do dia antigo com os de hoje e usa /visits/items (lifetime).
"""
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

MAX_DIAS = 60


def validar_periodo(date_from: date, date_to: date, hoje: date) -> int:
    if date_to < date_from:
        raise ValueError("date_to antes de date_from")
    if date_to >= hoje:
        raise ValueError("date_to tem que ser um dia já fechado (antes de hoje)")
    dias = (date_to - date_from).days + 1
    if dias > MAX_DIAS:
        raise ValueError(f"período máximo é {MAX_DIAS} dias")
    return dias


async def visitas_por_dia(db: AsyncSession, user_id, mlb: str, date_from: date, date_to: date) -> dict | None:
    """None = anúncio não pertence a nenhuma conta do usuário (qualquer status)."""
    from app.auth.models import MLAccount
    from app.mercadolivre.client import MLClient
    from app.vendas.models import Listing

    mlb_norm = mlb.upper().replace("-", "")
    if not mlb_norm.startswith("MLB"):
        mlb_norm = f"MLB{mlb_norm}"
    row = (
        await db.execute(
            select(Listing.mlb_id, Listing.status, MLAccount)
            .join(MLAccount, MLAccount.id == Listing.ml_account_id)
            .where(MLAccount.user_id == user_id, func.upper(func.replace(Listing.mlb_id, "-", "")) == mlb_norm)
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    _, status, acc = row
    async with MLClient(acc.access_token, ml_account_id=str(acc.id)) as client:
        dias = await client.get_item_visits_range(mlb_norm, date_from, date_to)
    return {
        "mlb": mlb_norm,
        "conta": acc.nickname,
        "status_anuncio": status,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "dias": dias,
        "dias_faltando": [
            d.isoformat()
            for d in (date.fromordinal(o) for o in range(date_from.toordinal(), date_to.toordinal() + 1))
            if d.isoformat() not in dias
        ],
        "fonte": "ML /items/{id}/visits/time_window",
    }
