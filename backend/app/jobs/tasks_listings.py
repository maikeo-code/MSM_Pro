"""
Lógica assíncrona para sincronização de snapshots de listings (anúncios).

Funções exportadas:
  - _sync_listing_snapshot_async: sincroniza snapshot de um anúncio específico
  - _sync_all_snapshots_async: sincroniza snapshots de todos os anúncios ativos
  - _sync_recent_snapshots_async: sincroniza anúncios com mudança recente de preço
"""
import logging
from collections import defaultdict
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, select

from app.auth.models import MLAccount
from app.core.database import AsyncSessionLocal
from app.mercadolivre.client import MLClient, MLClientError
from app.vendas.models import Listing, ListingSnapshot

from .tasks_helpers import _create_sync_log, _finish_sync_log

logger = logging.getLogger(__name__)


async def _sync_listing_snapshot_async(
    listing_id: str, visits_override: int | None = None
):
    """
    Lógica assíncrona do sync de snapshot de um anúncio específico.

    visits_override: quando fornecido pelo bulk caller (_sync_all_snapshots_async),
    pula a chamada individual de visitas e usa este valor diretamente.
    """
    async with AsyncSessionLocal() as db:
        # Busca o listing com a conta ML
        result = await db.execute(
            select(Listing).where(Listing.id == listing_id)
        )
        listing = result.scalar_one_or_none()
        if not listing:
            logger.warning(f"Listing {listing_id} não encontrado")
            return {"error": f"Listing {listing_id} não encontrado"}

        # Busca a conta ML
        acc_result = await db.execute(
            select(MLAccount).where(MLAccount.id == listing.ml_account_id)
        )
        account = acc_result.scalar_one_or_none()
        if not account or not account.access_token:
            logger.warning(f"Conta ML não encontrada para listing {listing_id}")
            return {"error": f"Conta ML não encontrada para listing {listing_id}"}

        # Chama a API ML
        client = None
        try:
            client = MLClient(account.access_token)

            # Busca dados do item
            item_data = await client.get_item(listing.mlb_id)
            price = Decimal(str(item_data.get("price", listing.price)))
            stock = item_data.get("available_quantity", 0)
            status = item_data.get("status", listing.status)

            # Extrai category_id e seller_sku do item
            category_id = item_data.get("category_id")
            seller_sku = item_data.get("seller_custom_field")

            # Se seller_custom_field não existe, tenta buscar em attributes com id SELLER_SKU
            if not seller_sku and item_data.get("attributes"):
                for attr in item_data["attributes"]:
                    if attr.get("id") == "SELLER_SKU":
                        seller_sku = attr.get("value_name") or attr.get("value_id")
                        break

            # Extrai original_price e sale_price do item
            original_price_raw = item_data.get("original_price")
            original_price = Decimal(str(original_price_raw)) if original_price_raw else None

            sale_price_data = item_data.get("sale_price")
            sale_price_val = None
            if sale_price_data and isinstance(sale_price_data, dict):
                sp_amount = sale_price_data.get("amount")
                if sp_amount is not None:
                    sale_price_val = Decimal(str(sp_amount))

            # Se sale_price existe e é menor que price, price é o preço original
            if sale_price_val is not None and original_price is None and price > sale_price_val:
                original_price = price

            # Se ainda não tem original_price, buscar via seller-promotions
            # Endpoint: GET /seller-promotions/items/{ITEM_ID}?app_version=v2
            if original_price is None:
                try:
                    promotions = await client.get_item_promotions(listing.mlb_id)
                    for promo in promotions:
                        if promo.get("status") == "started" and promo.get("original_price"):
                            original_price = Decimal(str(promo["original_price"]))
                            # Se a promoção também tem price, pode ser mais preciso que o item price
                            promo_price = promo.get("price")
                            if promo_price is not None:
                                price = Decimal(str(promo_price))
                            break
                except Exception:
                    logger.debug(f"Não conseguiu buscar promoções para {listing.mlb_id}")

            # Busca taxa real via API listing_prices (atualiza no listing)
            if category_id and listing.listing_type:
                listing_type_raw = "gold_special"  # default classico
                if listing.listing_type == "premium":
                    listing_type_raw = "gold_pro"
                elif listing.listing_type == "full":
                    listing_type_raw = "gold_pro"
                try:
                    fees_data = await client.get_listing_fees(
                        price=float(price),
                        category_id=category_id,
                        listing_type_id=listing_type_raw,
                    )
                    if fees_data.get("sale_fee_amount"):
                        listing.sale_fee_amount = Decimal(str(fees_data["sale_fee_amount"]))
                    pct_fee = fees_data.get("percentage_fee")
                    if pct_fee and pct_fee > 0:
                        listing.sale_fee_pct = Decimal(str(pct_fee / 100))
                except Exception:
                    logger.debug(f"Nao conseguiu buscar taxa real para {listing.mlb_id}")

            # Busca visitas do dia
            # Se visits_override foi fornecido pelo chamador bulk, evita N chamadas individuais
            visits = 0
            if visits_override is not None:
                visits = visits_override
            else:
                try:
                    visits_data = await client.get_item_visits(listing.mlb_id, days=1)
                    if visits_data and isinstance(visits_data, list) and visits_data:
                        visits = visits_data[0].get("total", 0)
                except MLClientError:
                    logger.debug(f"Não conseguiu buscar visitas para {listing.mlb_id}")

            # Busca pedidos PAGOS (unidades vendidas + receita + frete)
            sales_today = 0
            orders_count = 0
            revenue = Decimal("0")
            total_shipping_cost = Decimal("0")
            shipping_orders_count = 0
            mlb_normalized = listing.mlb_id.upper().replace("-", "")
            try:
                paid_orders = await client.get_item_orders_by_status(
                    listing.mlb_id, account.ml_user_id, days=1, status="paid"
                )
                for order in paid_orders:
                    # orders_count incrementa 1 por PEDIDO (nao por item).
                    # Um pedido com 2 unidades = 1 pedido, 2 unidades vendidas.
                    order_matched = False
                    for oi in order.get("order_items", []):
                        # Normaliza ambos os lados para comparacao exata
                        item_id = oi.get("item", {}).get("id", "").upper().replace("-", "")
                        if item_id == mlb_normalized:
                            qty = oi.get("quantity", 1)
                            unit_price = Decimal(str(oi.get("unit_price", 0)))
                            sales_today += qty
                            revenue += unit_price * qty
                            order_matched = True
                    if order_matched:
                        orders_count += 1
                        # Extrai shipping cost do pedido
                        shipping_data = order.get("shipping", {})
                        ship_cost = shipping_data.get("cost") or 0
                        if ship_cost:
                            total_shipping_cost += Decimal(str(ship_cost))
                            shipping_orders_count += 1
            except MLClientError:
                logger.debug(f"Nao conseguiu buscar pedidos pagos para {listing.mlb_id}")

            avg_selling_price = (revenue / sales_today) if sales_today > 0 else None

            # Busca pedidos CANCELADOS (conta pedidos + soma valor)
            cancelled_orders = 0
            cancelled_revenue = Decimal("0")
            try:
                cancelled_data = await client.get_item_orders_by_status(
                    listing.mlb_id, account.ml_user_id, days=1, status="cancelled"
                )
                for order in cancelled_data:
                    # cancelled_orders conta PEDIDOS cancelados (não itens).
                    for oi in order.get("order_items", []):
                        item_id = oi.get("item", {}).get("id", "").upper().replace("-", "")
                        if item_id == mlb_normalized:
                            cancelled_orders += 1
                            qty = oi.get("quantity", 1)
                            unit_price = Decimal(str(oi.get("unit_price", 0)))
                            cancelled_revenue += unit_price * qty
                            break  # 1 pedido = 1 cancelamento, independente da qtd de itens
            except MLClientError:
                logger.debug(f"Não conseguiu buscar pedidos cancelados para {listing.mlb_id}")

            # Busca DEVOLUÇÕES (status returned/refunded)
            returns_count = 0
            returns_revenue = Decimal("0")
            try:
                returned_data = await client.get_item_orders_by_status(
                    listing.mlb_id, account.ml_user_id, days=1, status="returned"
                )
                for order in returned_data:
                    for oi in order.get("order_items", []):
                        item_id = oi.get("item", {}).get("id", "").upper().replace("-", "")
                        if item_id == mlb_normalized:
                            returns_count += 1
                            qty = oi.get("quantity", 1)
                            unit_price = Decimal(str(oi.get("unit_price", 0)))
                            returns_revenue += unit_price * qty
                            break
            except MLClientError:
                logger.debug(f"Não conseguiu buscar devoluções para {listing.mlb_id}")

            # Busca perguntas
            questions_count = 0
            try:
                questions_data = await client.get_item_questions(listing.mlb_id)
                if isinstance(questions_data, dict):
                    questions_count = questions_data.get("total", 0)
            except MLClientError:
                logger.debug(f"Não conseguiu buscar perguntas para {listing.mlb_id}")

            # Calcula taxa de conversão
            conversion_rate = None
            if visits > 0 and sales_today > 0:
                conversion_rate = Decimal(str(round((sales_today / visits) * 100, 4)))

            # Upsert snapshot: atualiza se já existe do mesmo dia, senão insere
            from datetime import date as date_alias

            from sqlalchemy import Date, cast

            existing_snap_result = await db.execute(
                select(ListingSnapshot).where(
                    ListingSnapshot.listing_id == listing.id,
                    cast(ListingSnapshot.captured_at, Date) == date_alias.today(),
                ).order_by(ListingSnapshot.captured_at.desc()).limit(1)
            )
            existing_snap = existing_snap_result.scalar_one_or_none()
            if existing_snap:
                existing_snap.price = price
                existing_snap.visits = visits
                existing_snap.sales_today = sales_today
                existing_snap.questions = questions_count
                existing_snap.stock = stock
                existing_snap.conversion_rate = conversion_rate
                existing_snap.orders_count = orders_count
                existing_snap.revenue = revenue
                existing_snap.avg_selling_price = avg_selling_price
                existing_snap.cancelled_orders = cancelled_orders
                existing_snap.cancelled_revenue = cancelled_revenue
                existing_snap.returns_count = returns_count
                existing_snap.returns_revenue = returns_revenue
                existing_snap.captured_at = datetime.now(timezone.utc)
            else:
                snapshot = ListingSnapshot(
                    listing_id=listing.id,
                    price=price,
                    visits=visits,
                    sales_today=sales_today,
                    questions=questions_count,
                    stock=stock,
                    conversion_rate=conversion_rate,
                    orders_count=orders_count,
                    revenue=revenue,
                    avg_selling_price=avg_selling_price,
                    cancelled_orders=cancelled_orders,
                    cancelled_revenue=cancelled_revenue,
                    returns_count=returns_count,
                    returns_revenue=returns_revenue,
                )
                db.add(snapshot)

            # Atualiza preco, status e campos de desconto do listing
            listing.price = price
            listing.original_price = original_price
            listing.sale_price = sale_price_val
            listing.status = status
            listing.category_id = category_id
            listing.seller_sku = seller_sku
            # Atualiza frete medio real quando disponivel
            if shipping_orders_count > 0:
                listing.avg_shipping_cost = (
                    total_shipping_cost / shipping_orders_count
                ).quantize(Decimal("0.01"))
            # Calcula quality_score
            from app.vendas.service import calculate_quality_score_quick

            listing.quality_score = calculate_quality_score_quick(listing)
            listing.updated_at = datetime.now(timezone.utc)

            await db.commit()
            logger.info(f"Snapshot sincronizado para {listing.mlb_id}: R$ {price}")

            return {
                "success": True,
                "listing_id": listing_id,
                "mlb_id": listing.mlb_id,
                "price": float(price),
                "visits": visits,
                "sales_today": sales_today,
                "orders_count": orders_count,
                "revenue": float(revenue),
                "cancelled_orders": cancelled_orders,
                "cancelled_revenue": float(cancelled_revenue),
                "returns_count": returns_count,
                "returns_revenue": float(returns_revenue),
            }

        except MLClientError as e:
            logger.error(f"Erro ML ao sincronizar {listing.mlb_id}: {e}")
            await db.rollback()
            return {"error": str(e), "listing_id": listing_id}
        except Exception as e:
            logger.exception(f"Erro inesperado ao sincronizar {listing_id}: {e}")
            await db.rollback()
            return {"error": str(e), "listing_id": listing_id}
        finally:
            if client:
                await client.close()


async def _sync_all_snapshots_async():
    """
    Busca todos os listings ativos e sincroniza snapshots de cada um.

    Otimização de visitas: em vez de N chamadas individuais (1 por anúncio),
    faz 1 chamada bulk por conta ML usando get_items_visits_bulk().
    O resultado é passado como visits_override para cada task individual,
    evitando o overhead de rate-limit N vezes.

    IMPORTANTE: O sync roda às 06:00 BRT. Para ter dados completos de "ontem",
    buscamos visitas do DIA ANTERIOR inteiro (não do dia atual parcial).

    Usa Redis lock para evitar execução duplicada entre workers.
    """
    # Import local para evitar circular import (tasks.py importa esta função)
    from app.jobs.tasks import sync_listing_snapshot

    async with AsyncSessionLocal() as db:
        sync_log = await _create_sync_log(db, "sync_all_snapshots")

        try:
            result = await db.execute(
                select(Listing).where(Listing.status == "active")
            )
            listings = result.scalars().all()

            logger.info(f"Iniciando sincronização de {len(listings)} anúncios ativos")

            # Agrupar listings por ml_account_id para fazer 1 chamada bulk por conta
            listings_by_account: dict[str, list] = defaultdict(list)
            for listing in listings:
                listings_by_account[str(listing.ml_account_id)].append(listing)

            # Para cada conta, buscar token e chamar bulk de visitas
            # visits_map: mlb_id (normalizado) -> total do dia anterior
            # O sync roda às 06:00 BRT. Buscamos visitas do DIA ANTERIOR completo.
            visits_map: dict[str, int] = {}
            yesterday = date_type.today() - timedelta(days=1)
            yesterday_str = yesterday.isoformat()

            for account_id, account_listings in listings_by_account.items():
                acc_result = await db.execute(
                    select(MLAccount).where(MLAccount.id == account_id)
                )
                account = acc_result.scalar_one_or_none()
                if not account or not account.access_token:
                    logger.warning(
                        f"Sem token ML para conta {account_id} — visitas bulk puladas"
                    )
                    continue

                mlb_ids = [
                    lst.mlb_id.upper().replace("-", "")
                    for lst in account_listings
                ]
                # Garante prefixo MLB
                mlb_ids = [
                    mid if mid.startswith("MLB") else f"MLB{mid}"
                    for mid in mlb_ids
                ]

                client = MLClient(account.access_token)
                try:
                    # Buscar visitas do DIA ANTERIOR (completo)
                    bulk_result = await client.get_items_visits_bulk(
                        mlb_ids, date_from=yesterday_str, date_to=yesterday_str
                    )
                    visits_map.update(bulk_result)
                    logger.info(
                        f"Visitas bulk OK para conta {account_id} (dia anterior {yesterday_str}): "
                        f"{len(bulk_result)} itens retornados"
                    )
                except Exception as e:
                    logger.warning(
                        f"Falha no bulk de visitas para conta {account_id}: {e} — "
                        "tasks usarão chamada individual como fallback"
                    )
                finally:
                    await client.close()

            # Despachar tasks individuais com visits_override quando disponível
            dispatched = []
            for listing in listings:
                mlb_normalized = listing.mlb_id.upper().replace("-", "")
                if not mlb_normalized.startswith("MLB"):
                    mlb_normalized = f"MLB{mlb_normalized}"

                # Se o bulk retornou dado para este item, passa como override;
                # caso contrário, a task buscará individualmente (fallback seguro)
                visits_val = visits_map.get(mlb_normalized)

                sync_listing_snapshot.delay(str(listing.id), visits_override=visits_val)
                dispatched.append(str(listing.id))

            logger.info(f"Enfileiradas {len(dispatched)} tasks de snapshot")

            await _finish_sync_log(db, sync_log, status="success", items=len(dispatched))
            return {
                "success": True,
                "dispatched": len(dispatched),
                "listing_ids": dispatched,
            }

        except Exception as exc:
            logger.error(f"Erro em _sync_all_snapshots_async: {exc}")
            await _finish_sync_log(
                db, sync_log, status="failed", error=str(exc)
            )
            raise


async def _sync_recent_snapshots_async():
    """Sincroniza apenas anúncios que tiveram mudança nas últimas horas."""
    # Import local para evitar circular import (tasks.py importa esta função)
    from app.jobs.tasks import sync_listing_snapshot

    async with AsyncSessionLocal() as db:
        # Busca listings ativos que foram atualizados nas últimas 2 horas
        threshold = datetime.now(timezone.utc) - timedelta(hours=2)

        result = await db.execute(
            select(Listing).where(
                and_(
                    Listing.status == "active",
                    Listing.updated_at >= threshold,
                )
            )
        )
        listings = result.scalars().all()

        logger.info(f"Sincronizando {len(listings)} anúncios com mudança recente")

        for listing in listings:
            sync_listing_snapshot.delay(str(listing.id))

        return {
            "success": True,
            "synced": len(listings),
        }
