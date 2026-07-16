"""Coleta diária de preço de concorrentes -> tabela flat competitor_prices.

Reusa MLClient (token + refresh prontos). Para cada id_ml alvo:
  - item (MLB+10díg)     → GET /items/{id}     → price, sold_quantity,
                            available_quantity, status; is_buy_box=false
  - catálogo (MLBU/8díg) → GET /products/{id}   → buy_box_winner (preço/vendedor
                            vencedor); is_buy_box=true

Upsert por (id_ml, day). Roda 1x/dia. Ver [[feature-competitor-prices]].
"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.auth.models import MLAccount
from app.concorrencia.competitor_targets import COMPETITOR_TARGETS, is_catalog_id
from app.concorrencia.models import CompetitorPrice
from app.core.database import AsyncSessionLocal
from app.mercadolivre.client import MLClient

from .tasks_helpers import _create_sync_log, _finish_sync_log

# Timezone BRT (UTC-3) — o "dia" da coleta é o dia BRT.
BRT = timezone(timedelta(hours=-3))

logger = logging.getLogger(__name__)


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


async def _upsert_competitor_price(
    db, id_ml: str, day, price, sold, avail, status, is_buy_box: bool
) -> None:
    """Upsert de uma linha por (id_ml, day)."""
    existing = (
        await db.execute(
            select(CompetitorPrice).where(
                CompetitorPrice.id_ml == id_ml,
                CompetitorPrice.day == day,
            )
        )
    ).scalar_one_or_none()

    price_dec = _to_decimal(price)
    now = datetime.now(timezone.utc)
    if existing:
        existing.price = price_dec
        existing.sold_quantity = sold
        existing.available_quantity = avail
        existing.status = status
        existing.is_buy_box = is_buy_box
        existing.updated_at = now
    else:
        db.add(
            CompetitorPrice(
                id_ml=id_ml,
                day=day,
                price=price_dec,
                sold_quantity=sold,
                available_quantity=avail,
                status=status,
                is_buy_box=is_buy_box,
                updated_at=now,
            )
        )


async def _collect_competitor_prices_async():
    """Coleta preço/estoque dos concorrentes alvo e grava em competitor_prices."""
    today = datetime.now(BRT).date()

    async with AsyncSessionLocal() as db:
        sync_log = await _create_sync_log(db, "collect_competitor_prices")

        # Leituras públicas (/items, /products) — qualquer conta ativa com token serve.
        account = (
            await db.execute(
                select(MLAccount).where(
                    MLAccount.is_active == True,  # noqa: E712
                    MLAccount.access_token.isnot(None),
                )
            )
        ).scalars().first()

        if not account:
            await _finish_sync_log(
                db, sync_log, status="failed", error="Nenhuma conta ML ativa com token"
            )
            return {"error": "Nenhuma conta ML ativa com token"}

        client = MLClient(account.access_token, ml_account_id=str(account.id))
        ok = 0
        failed = 0
        details: list[dict] = []
        try:
            for id_ml in COMPETITOR_TARGETS:
                kind = "catalog" if is_catalog_id(id_ml) else "item"
                try:
                    if is_catalog_id(id_ml):
                        data = await client.get_product(id_ml)
                        bbw = data.get("buy_box_winner") or {}
                        price = bbw.get("price")
                        avail = bbw.get("available_quantity")
                        # Se há vencedor de buy box o produto está ativo; senão usa
                        # o status do produto (ou 'unknown').
                        status = "active" if bbw else (data.get("status") or "unknown")
                        is_buy_box = True
                        # buy_box_winner NÃO expõe sold_quantity (confirmado na doc
                        # oficial ML: concorrencia-em-catalogo). Busca no item vencedor
                        # (1 call extra por catálogo — só 4 alvos). Falha aqui não
                        # perde a linha: mantém price/available do buy_box_winner.
                        sold = None
                        winner_item_id = bbw.get("item_id")
                        if winner_item_id:
                            try:
                                witem = await client.get_item(winner_item_id)
                                sold = witem.get("sold_quantity")
                                if avail is None:
                                    avail = witem.get("available_quantity")
                            except Exception:
                                logger.debug(
                                    f"Não obteve sold_quantity do vencedor {winner_item_id}"
                                )
                    else:
                        data = await client.get_item(id_ml)
                        price = data.get("price")
                        sold = data.get("sold_quantity")
                        avail = data.get("available_quantity")
                        status = data.get("status")
                        is_buy_box = False

                    await _upsert_competitor_price(
                        db, id_ml, today, price, sold, avail, status, is_buy_box
                    )
                    ok += 1
                    details.append({
                        "id_ml": id_ml, "kind": kind, "ok": True,
                        "price": float(price) if price is not None else None,
                    })
                except Exception as exc:
                    failed += 1
                    logger.warning(f"Falha ao coletar concorrente {id_ml}: {exc}")
                    details.append({
                        "id_ml": id_ml, "kind": kind, "ok": False,
                        "error": f"{type(exc).__name__}: {str(exc)[:180]}",
                    })

            await db.commit()
            await _finish_sync_log(
                db, sync_log, status="success", items=ok, failed=failed
            )
            logger.info(
                f"Coleta de concorrentes: {ok} ok, {failed} falha(s) em {today}"
            )
            return {
                "success": True, "collected": ok, "failed": failed,
                "day": str(today), "details": details,
            }
        except Exception as exc:
            logger.error(f"Erro em _collect_competitor_prices_async: {exc}")
            await db.rollback()
            await _finish_sync_log(db, sync_log, status="failed", error=str(exc))
            raise
        finally:
            await client.close()
