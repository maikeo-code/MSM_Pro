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
            # ── ITENS de terceiro: /items/{id} dá 403; usar MULTIGET com attributes
            # (caminho sancionado, doc "Busca de itens"). Verbose [{code, body}].
            item_ids = [t for t in COMPETITOR_TARGETS if not is_catalog_id(t)]
            items_map: dict[str, dict] = {}  # id_ml -> {code, body}

            async def _multiget_into(ids: list[str], attributes: str) -> None:
                for start in range(0, len(ids), 20):  # multiget: máx 20 por chamada
                    batch = ids[start:start + 20]
                    try:
                        verbose = await client.get_items_multiget(batch, attributes=attributes)
                        for entry in verbose:
                            body = entry.get("body") or {}
                            bid = str(body.get("id") or "").upper().replace("-", "")
                            if bid:
                                items_map[bid] = entry
                    except Exception as exc:
                        logger.warning(f"Multiget itens falhou (batch {start}, attrs={attributes}): {exc}")

            # 1ª tentativa: campos ricos. Se algum vier code!=200, pode ser atributo
            # restrito p/ terceiro (ex.: sold_quantity) — 2ª tentativa só id,price.
            await _multiget_into(item_ids, "id,price,available_quantity,sold_quantity,status")
            retry_ids = [
                iid for iid in item_ids
                if (items_map.get(iid.upper().replace("-", "")) or {}).get("code") != 200
            ]
            if retry_ids:
                await _multiget_into(retry_ids, "id,price")

            for id_ml in COMPETITOR_TARGETS:
                kind = "catalog" if is_catalog_id(id_ml) else "item"
                try:
                    if is_catalog_id(id_ml):
                        data = await client.get_product(id_ml)
                        bbw = data.get("buy_box_winner") or {}
                        price = bbw.get("price")
                        avail = bbw.get("available_quantity")
                        status = "active" if bbw else (data.get("status") or "unknown")
                        is_buy_box = True
                        # sold_quantity de concorrente é inacessível (get_item terceiro
                        # = 403) — fica NULL.
                        sold = None
                        # Fallback quando buy_box_winner vem vazio: /products/{id}/items
                        # lista as publicações concorrentes (results[0] ~ vencedor).
                        if price is None:
                            try:
                                pit = await client.get_product_items(id_ml)
                                results = pit.get("results") or []
                                if results:
                                    win = results[0]
                                    price = win.get("price")
                                    avail = win.get("available_quantity", avail)
                                    status = "active"
                            except Exception as exc:
                                logger.debug(
                                    f"/products/{id_ml}/items falhou: {exc}"
                                )
                    else:
                        # Item de terceiro via multiget. code!=200 => falha explícita.
                        entry = items_map.get(id_ml.upper().replace("-", ""))
                        if not entry:
                            raise RuntimeError("ausente no multiget")
                        code = entry.get("code")
                        body = entry.get("body") or {}
                        if code != 200:
                            raise RuntimeError(f"multiget code {code}")
                        price = body.get("price")
                        sold = body.get("sold_quantity")
                        avail = body.get("available_quantity")  # bucketizado
                        status = body.get("status")
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
