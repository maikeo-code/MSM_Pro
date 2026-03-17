"""
Lógica assíncrona para sincronização de pedidos do Mercado Livre.

Funções exportadas:
  - _sync_orders_async: para cada conta ML ativa, busca pedidos recentes e faz upsert na tabela orders
"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.auth.models import MLAccount
from app.core.database import AsyncSessionLocal
from app.mercadolivre.client import MLClient, MLClientError
from app.vendas.models import Listing

from .tasks_helpers import _create_sync_log, _finish_sync_log

logger = logging.getLogger(__name__)


async def _sync_orders_async():
    """
    Para cada ml_account ativa:
    1. Busca pedidos dos ultimos 2 dias via /orders/search
    2. Para cada order: upsert na tabela Order com todos os campos
    3. Extrai sale_fee do order_items, shipping_cost dos payments e calcula net_amount
    """
    from app.vendas.models import Order

    date_from = (datetime.now(timezone.utc) - timedelta(days=2)).strftime(
        "%Y-%m-%dT%H:%M:%S.000-03:00"
    )

    async with AsyncSessionLocal() as db:
        sync_log = await _create_sync_log(db, "sync_orders")

        try:
            acc_result = await db.execute(
                select(MLAccount).where(MLAccount.is_active == True)  # noqa: E712
            )
            accounts = acc_result.scalars().all()

            logger.info(f"Sincronizando pedidos para {len(accounts)} contas ML")

            total_created, total_updated, total_errors = 0, 0, 0

            for account in accounts:
                if not account.access_token:
                    logger.warning(
                        f"Sem token ML para conta {account.nickname} — pulando"
                    )
                    continue

                client = MLClient(account.access_token)
                try:
                    offset = 0
                    limit = 50
                    while True:
                        try:
                            response = await client.get_orders(
                                seller_id=account.ml_user_id,
                                date_from=date_from,
                                offset=offset,
                                limit=limit,
                            )
                        except MLClientError as e:
                            logger.warning(
                                f"Erro ML ao buscar pedidos para {account.nickname}: {e}"
                            )
                            break

                        results = response.get("results", [])
                        if not results:
                            break

                        for order_raw in results:
                            try:
                                ml_order_id = str(order_raw.get("id", ""))
                                if not ml_order_id:
                                    continue

                                # Extrai dados do primeiro item do pedido
                                order_items = order_raw.get("order_items", [])
                                if not order_items:
                                    continue

                                first_item = order_items[0]
                                mlb_id_raw = (
                                    first_item.get("item", {}).get("id", "") or ""
                                )
                                mlb_id = mlb_id_raw.upper().replace("-", "")
                                if not mlb_id.startswith("MLB"):
                                    mlb_id = f"MLB{mlb_id}"

                                quantity = int(first_item.get("quantity", 1))
                                unit_price = Decimal(
                                    str(first_item.get("unit_price", 0))
                                )

                                # sale_fee do order_item (taxa de venda)
                                sale_fee_raw = first_item.get("sale_fee", 0) or 0
                                sale_fee = Decimal(str(sale_fee_raw))

                                total_amount = Decimal(
                                    str(order_raw.get("total_amount", 0))
                                )
                                buyer_nickname = (
                                    order_raw.get("buyer", {}).get("nickname", "") or ""
                                )

                                # Data de criacao do pedido
                                order_date_str = order_raw.get("date_created", "")
                                try:
                                    order_date = datetime.fromisoformat(
                                        order_date_str.replace("Z", "+00:00")
                                    )
                                except (ValueError, AttributeError):
                                    order_date = datetime.now(timezone.utc)

                                # Status de pagamento e data de aprovacao
                                payments = order_raw.get("payments", [])
                                payment_status = "pending"
                                payment_date = None
                                if payments:
                                    first_payment = payments[0]
                                    payment_status = (
                                        first_payment.get("status", "pending") or "pending"
                                    )
                                    payment_date_str = first_payment.get("date_approved")
                                    if payment_date_str:
                                        try:
                                            payment_date = datetime.fromisoformat(
                                                payment_date_str.replace("Z", "+00:00")
                                            )
                                        except (ValueError, AttributeError):
                                            payment_date = None

                                # Status de envio e data de entrega
                                shipping_data = order_raw.get("shipping", {}) or {}
                                shipping_status = (
                                    shipping_data.get("status", "to_be_agreed")
                                    or "to_be_agreed"
                                )
                                # shipping_cost nao vem no /orders/search — padrao 0
                                # O frete real e calculado pelo listing.avg_shipping_cost
                                shipping_cost = Decimal("0")
                                delivery_date = None
                                delivery_date_str = (
                                    shipping_data.get("date_delivered")
                                    or (
                                        shipping_data.get(
                                            "estimated_delivery_time", {}
                                        ).get("date")
                                        if isinstance(
                                            shipping_data.get("estimated_delivery_time"),
                                            dict,
                                        )
                                        else None
                                    )
                                )
                                if delivery_date_str:
                                    try:
                                        delivery_date = datetime.fromisoformat(
                                            delivery_date_str.replace("Z", "+00:00")
                                        )
                                    except (ValueError, AttributeError):
                                        delivery_date = None

                                net_amount = total_amount - sale_fee - shipping_cost

                                # Tenta encontrar o listing_id correspondente
                                listing_result = await db.execute(
                                    select(Listing).where(Listing.mlb_id == mlb_id)
                                )
                                listing = listing_result.scalar_one_or_none()
                                listing_id = listing.id if listing else None

                                # Upsert: atualiza se ja existe, cria se nao existe
                                existing_result = await db.execute(
                                    select(Order).where(
                                        Order.ml_order_id == ml_order_id
                                    )
                                )
                                existing_order = existing_result.scalar_one_or_none()

                                if existing_order:
                                    # Atualiza apenas campos mutaveis
                                    existing_order.shipping_status = shipping_status
                                    existing_order.payment_status = payment_status
                                    if payment_date:
                                        existing_order.payment_date = payment_date
                                    if delivery_date:
                                        existing_order.delivery_date = delivery_date
                                    total_updated += 1
                                else:
                                    new_order = Order(
                                        ml_order_id=ml_order_id,
                                        ml_account_id=account.id,
                                        listing_id=listing_id,
                                        mlb_id=mlb_id,
                                        buyer_nickname=buyer_nickname,
                                        quantity=quantity,
                                        unit_price=unit_price,
                                        total_amount=total_amount,
                                        sale_fee=sale_fee,
                                        shipping_cost=shipping_cost,
                                        net_amount=net_amount,
                                        payment_status=payment_status,
                                        shipping_status=shipping_status,
                                        order_date=order_date,
                                        payment_date=payment_date,
                                        delivery_date=delivery_date,
                                    )
                                    db.add(new_order)
                                    total_created += 1

                            except Exception as e:
                                logger.error(
                                    f"Erro ao processar pedido {order_raw.get('id', '?')}: {e}"
                                )
                                total_errors += 1

                        await db.flush()

                        paging = response.get("paging", {})
                        total_available = paging.get("total", 0)
                        offset += limit
                        if offset >= total_available:
                            break

                finally:
                    await client.close()

            await _finish_sync_log(
                db,
                sync_log,
                status="success",
                items=total_created + total_updated,
                failed=total_errors,
            )
            logger.info(
                f"Sync orders: {total_created} criados, "
                f"{total_updated} atualizados, {total_errors} erros"
            )
            return {
                "success": True,
                "created": total_created,
                "updated": total_updated,
                "errors": total_errors,
            }

        except Exception as exc:
            logger.error(f"Erro em _sync_orders_async: {exc}")
            await _finish_sync_log(
                db, sync_log, status="failed", error=str(exc)
            )
            raise
