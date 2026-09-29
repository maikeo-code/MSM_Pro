"""Preço BASE de um anúncio via PUT /items/{id} — usado pelo Conselho de Preços do JARVIS.

Diferente de /suggestion_apply (cria promoção PRICE_DISCOUNT, só para baixar) e de PATCH /price
(só grava no banco local). Travas:
- o preço vivo (sale_price) tem que ser o esperado pelo chamador — senão alguém mexeu → 409, sem PUT;
- promoção ativa (regular_amount no sale_price) → 409, sem PUT (a alavanca do conselho é só o preço);
- depois do PUT relê o preço (até 2 leituras) e informa se confirmou.
Toda tentativa fica no PriceChangeLog (source="conselho"), inclusive as recusadas.
"""
import asyncio
import json
import math
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

LEITURAS_DEPOIS = 2


class Conflito(Exception):
    """O ML não está no estado esperado: nada foi alterado. preco_vivo = o que o ML mostra agora (se lido)."""

    def __init__(self, msg: str, preco_vivo: float | None = None):
        super().__init__(msg)
        self.preco_vivo = preco_vivo


def validar_preco(preco: float) -> float:
    if isinstance(preco, bool) or not isinstance(preco, (int, float)) or not math.isfinite(preco) or preco <= 0:
        raise ValueError(f"preço inválido: {preco!r}")
    return round(float(preco), 2)


def _vivo(sp: dict) -> float:
    if not isinstance(sp, dict) or sp.get("amount") is None:
        raise Conflito("não consegui ler o preço vivo (sale_price vazio)")
    if sp.get("regular_amount") is not None:
        raise Conflito(f"promoção ativa (regular_amount={sp['regular_amount']}): preço base não alterado")
    return round(float(sp["amount"]), 2)


async def aplicar_no_ml(client, mlb: str, preco: float, esperado: float, espera_s: float = 3.0) -> dict:
    preco, esperado = validar_preco(preco), validar_preco(esperado)
    antes = _vivo(await client.get_item_sale_price(mlb))
    if abs(antes - esperado) >= 0.005:
        raise Conflito(f"preço vivo {antes} diferente do esperado {esperado}", preco_vivo=antes)
    resposta = await client.update_item_price(mlb, preco)
    lido, n = None, 0
    for n in range(1, LEITURAS_DEPOIS + 1):
        await asyncio.sleep(espera_s)
        sp = await client.get_item_sale_price(mlb)
        lido = round(float(sp["amount"]), 2) if isinstance(sp, dict) and sp.get("amount") is not None else None
        if lido is not None and abs(lido - preco) < 0.005:
            break
    return {"mlb": mlb, "preco_antes": antes, "preco_pedido": preco, "preco_lido_depois": lido,
            "confirmado": lido is not None and abs(lido - preco) < 0.005, "leituras_depois": n,
            "resposta_ml": resposta}


async def aplicar_preco_base(db: AsyncSession, mlb_id: str, user_id: UUID, preco: float, esperado: float,
                             justificativa: str) -> dict:
    from app.auth.models import MLAccount
    from app.mercadolivre.client import MLClient, MLClientError
    from app.vendas.models import PriceChangeLog
    from app.vendas.service import get_listing

    try:
        preco, esperado = validar_preco(preco), validar_preco(esperado)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    listing = await get_listing(db, mlb_id, user_id)
    acc = (await db.execute(select(MLAccount).where(MLAccount.id == listing.ml_account_id))).scalar_one_or_none()
    if not acc or not acc.access_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conta ML sem token")

    def _log(success: bool, erro: str | None, resposta=None, novo=preco):
        db.add(PriceChangeLog(listing_id=listing.id, user_id=user_id, mlb_id=listing.mlb_id,
                              old_price=Decimal(str(esperado)), new_price=Decimal(str(novo)),
                              justification=f"[CONSELHO base] {justificativa}"[:2000], source="conselho",
                              ml_api_response=json.dumps(resposta, default=str)[:4000] if resposta else None,
                              success=success, error_message=erro))

    try:
        async with MLClient(acc.access_token, ml_account_id=str(acc.id)) as client:
            r = await aplicar_no_ml(client, listing.mlb_id, preco, esperado)
    except Conflito as e:
        _log(False, f"recusado: {e}")
        await db.commit()                          # o get_db faria rollback no raise
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail={"motivo": str(e), "preco_vivo": e.preco_vivo})
    except MLClientError as e:
        _log(False, f"ML falhou: {e}")
        await db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"ML falhou: {e}")

    _log(r["confirmado"], None if r["confirmado"] else f"não confirmado: lido {r['preco_lido_depois']}",
         r["resposta_ml"])
    if r["confirmado"]:
        listing.price = Decimal(str(preco))
    await db.flush()
    r.pop("resposta_ml", None)
    return r
