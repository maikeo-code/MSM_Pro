"""
Celery tasks para sincronização de dados do Mercado Livre.

Tasks:
  - sync_all_snapshots: sincroniza snapshots de todos os anúncios ativos diariamente
  - sync_recent_snapshots: sincroniza snapshots de anúncios com mudança recente de preço
  - refresh_expired_tokens: renova tokens ML que vão expirar
  - sync_listing_snapshot: sincroniza snapshot de um anúncio específico
  - sync_competitor_snapshots: sincroniza preços dos concorrentes monitorados
  - evaluate_alerts: avalia condições de alerta e dispara notificações
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, select

from app.auth.models import MLAccount
from app.auth.service import refresh_ml_token
from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.mercadolivre.client import MLClient, MLClientError
from app.vendas.models import Listing, ListingSnapshot

logger = logging.getLogger(__name__)


# --- Helpers de instrumentação sync_logs ---

async def _create_sync_log(db, task_name: str, ml_account_id=None):
    """Cria um SyncLog com status 'running' e faz flush para obter o id."""
    from app.core.models import SyncLog
    log = SyncLog(task_name=task_name, ml_account_id=ml_account_id, status="running")
    db.add(log)
    await db.flush()
    return log


async def _finish_sync_log(
    db,
    log,
    status: str,
    items: int = 0,
    failed: int = 0,
    error: str | None = None,
) -> None:
    """Finaliza um SyncLog com status, contadores e duração calculada."""
    log.status = status
    log.items_processed = items
    log.items_failed = failed
    log.error_message = error
    log.finished_at = datetime.now(timezone.utc)
    if log.started_at:
        started = log.started_at
        # garante que ambos os datetimes são aware para subtração segura
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        log.duration_ms = int(
            (log.finished_at - started).total_seconds() * 1000
        )
    await db.commit()


# --- Helper para rodar async dentro do Celery ---

def run_async(coro):
    """Executa coroutine assíncrona dentro de uma task Celery síncrona."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --- Task: Sincronizar snapshot de um anúncio específico ---

@celery_app.task(
    name="app.jobs.tasks.sync_listing_snapshot",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def sync_listing_snapshot(self, listing_id: str, visits_override: int | None = None):
    """
    Sincroniza snapshot de um anúncio específico.
    Chama a API ML e salva o snapshot no banco.

    visits_override: quando fornecido pelo bulk caller (_sync_all_snapshots_async),
    pula a chamada individual de visitas e usa este valor diretamente.
    """
    try:
        return run_async(_sync_listing_snapshot_async(listing_id, visits_override=visits_override))
    except Exception as exc:
        logger.error(f"Erro ao sincronizar snapshot de {listing_id}: {exc}")
        # Retry com backoff exponencial
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


async def _sync_listing_snapshot_async(listing_id: str, visits_override: int | None = None):
    """Lógica assíncrona do sync de snapshot."""
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
            from sqlalchemy import cast, Date
            from datetime import date as date_type
            existing_snap_result = await db.execute(
                select(ListingSnapshot).where(
                    ListingSnapshot.listing_id == listing.id,
                    cast(ListingSnapshot.captured_at, Date) == date_type.today(),
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
                listing.avg_shipping_cost = (total_shipping_cost / shipping_orders_count).quantize(
                    Decimal("0.01")
                )
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


# --- Task: Sincronizar snapshots de todos os anúncios ---

@celery_app.task(name="app.jobs.tasks.sync_all_snapshots", bind=True)
def sync_all_snapshots(self):
    """
    Sincroniza snapshots de todos os anúncios ativos.
    Executado diariamente às 06:00 BRT.
    """
    try:
        return run_async(_sync_all_snapshots_async())
    except Exception as exc:
        logger.error(f"Erro em sync_all_snapshots: {exc}")
        raise


async def _sync_all_snapshots_async():
    """
    Busca todos os listings ativos e sincroniza snapshots de cada um.

    Otimização de visitas: em vez de N chamadas individuais (1 por anúncio),
    faz 1 chamada bulk por conta ML usando get_items_visits_bulk().
    O resultado é passado como visits_override para cada task individual,
    evitando o overhead de rate-limit N vezes.
    """
    from datetime import date as date_type
    from collections import defaultdict

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
            # visits_map: mlb_id (normalizado) -> total do dia
            visits_map: dict[str, int] = {}
            today_str = date_type.today().isoformat()

            for account_id, account_listings in listings_by_account.items():
                acc_result = await db.execute(
                    select(MLAccount).where(MLAccount.id == account_id)
                )
                account = acc_result.scalar_one_or_none()
                if not account or not account.access_token:
                    logger.warning(f"Sem token ML para conta {account_id} — visitas bulk puladas")
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
                    bulk_result = await client.get_items_visits_bulk(
                        mlb_ids, date_from=today_str, date_to=today_str
                    )
                    visits_map.update(bulk_result)
                    logger.info(
                        f"Visitas bulk OK para conta {account_id}: "
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


# --- Task: Sincronizar snapshots recentes (horária) ---

@celery_app.task(name="app.jobs.tasks.sync_recent_snapshots")
def sync_recent_snapshots():
    """
    Sincroniza snapshots de anúncios com mudança recente de preço.
    Executado a cada hora para capturar mudanças rápidas.
    """
    try:
        return run_async(_sync_recent_snapshots_async())
    except Exception as exc:
        logger.error(f"Erro em sync_recent_snapshots: {exc}")
        raise


async def _sync_recent_snapshots_async():
    """Sincroniza apenas anúncios que tiveram mudança nas últimas horas."""
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


# --- Task: Renovar tokens ML expirados ---

@celery_app.task(name="app.jobs.tasks.refresh_expired_tokens", bind=True)
def refresh_expired_tokens(self):
    """
    Renova tokens ML que vão expirar nas próximas 2 horas.
    Executado a cada 4 horas.
    """
    try:
        return run_async(_refresh_expired_tokens_async())
    except Exception as exc:
        logger.error(f"Erro em refresh_expired_tokens: {exc}")
        raise


async def _refresh_expired_tokens_async():
    """Busca contas ML com token prestes a expirar e renova."""
    threshold = datetime.now(timezone.utc) + timedelta(hours=2)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MLAccount).where(
                and_(
                    MLAccount.is_active == True,  # noqa: E712
                    MLAccount.token_expires_at <= threshold,
                    MLAccount.refresh_token.isnot(None),
                )
            )
        )
        accounts = result.scalars().all()

        logger.info(f"Renovando tokens para {len(accounts)} contas ML")

        refreshed = []
        errors = []

        for account in accounts:
            try:
                token_data = await refresh_ml_token(account)

                account.access_token = token_data["access_token"]
                account.refresh_token = token_data.get("refresh_token", account.refresh_token)
                expires_in = token_data.get("expires_in", 21600)  # 6h padrão
                account.token_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=expires_in
                )

                logger.info(f"Token renovado para conta {account.nickname}")
                refreshed.append(str(account.id))

            except Exception as e:
                logger.error(f"Erro ao renovar token de {account.nickname}: {e}")
                errors.append({"account_id": str(account.id), "nickname": account.nickname, "error": str(e)})

        await db.commit()

        logger.info(f"Renovação concluída: {len(refreshed)} sucesso, {len(errors)} erros")
        return {
            "success": True,
            "refreshed": len(refreshed),
            "errors": len(errors),
            "error_details": errors,
        }


# --- Task: Sincronizar snapshots dos concorrentes ---

@celery_app.task(name="app.jobs.tasks.sync_competitor_snapshots", bind=True)
def sync_competitor_snapshots(self):
    """
    Sincroniza o preço atual de todos os concorrentes ativos.
    Executado diariamente às 07:00 BRT (10:00 UTC), após o sync principal.
    """
    try:
        return run_async(_sync_competitor_snapshots_async())
    except Exception as exc:
        logger.error(f"Erro em sync_competitor_snapshots: {exc}")
        raise


async def _sync_competitor_snapshots_async():
    """
    Busca todos os Competitor ativos, chama a API ML para cada um e salva
    CompetitorSnapshot com preço atual, visitas e sales_delta.

    Visitas: endpoint GET /items/{id}/visits/time_window?last=1&unit=day é público
    — não precisa de token do dono. Busca em batch via get_items_visits_bulk()
    antes do loop principal para evitar N chamadas individuais.
    """
    from datetime import date as date_type

    from app.concorrencia.models import Competitor, CompetitorSnapshot

    async with AsyncSessionLocal() as db:
        sync_log = await _create_sync_log(db, "sync_competitor_snapshots")

        try:
            # Carrega todos competitors ativos com o listing para acessar a conta ML
            result = await db.execute(
                select(Competitor)
                .join(Listing, Competitor.listing_id == Listing.id)
                .where(Competitor.is_active == True)  # noqa: E712
            )
            competitors = result.scalars().all()

            logger.info(f"Iniciando sync de {len(competitors)} concorrentes")

            if not competitors:
                await _finish_sync_log(db, sync_log, status="success", items=0)
                return {"success": True, "synced": 0, "errors": 0}

            # --- Busca visitas de todos os concorrentes em batch (endpoint público) ---
            # Normaliza mlb_ids para o formato MLB<numero>
            comp_mlb_ids = []
            for c in competitors:
                mid = c.mlb_id.upper().replace("-", "")
                if not mid.startswith("MLB"):
                    mid = f"MLB{mid}"
                comp_mlb_ids.append(mid)

            today_str = date_type.today().isoformat()

            # Precisa de qualquer token válido para usar o cliente HTTP (mesmo sendo endpoint público)
            # Busca a primeira conta ML ativa disponível
            visits_data: dict[str, int] = {}
            first_acc_result = await db.execute(
                select(MLAccount).where(MLAccount.is_active == True).limit(1)  # noqa: E712
            )
            first_account = first_acc_result.scalar_one_or_none()
            if first_account and first_account.access_token:
                bulk_client = MLClient(first_account.access_token)
                try:
                    visits_data = await bulk_client.get_items_visits_bulk(
                        comp_mlb_ids, date_from=today_str, date_to=today_str
                    )
                    logger.info(
                        f"Visitas bulk concorrentes OK: {len(visits_data)} itens retornados"
                    )
                except Exception as e:
                    logger.warning(
                        f"Falha no bulk de visitas para concorrentes: {e} — "
                        "visitas serão salvas como 0"
                    )
                finally:
                    await bulk_client.close()
            else:
                logger.warning("Nenhuma conta ML ativa encontrada — visitas de concorrentes serão 0")

            # --- Loop principal: busca preço e dados de cada concorrente ---
            synced, errors = 0, 0

            for comp in competitors:
                try:
                    # Busca listing para pegar a conta ML com token
                    listing_result = await db.execute(
                        select(Listing).where(Listing.id == comp.listing_id)
                    )
                    listing = listing_result.scalar_one_or_none()
                    if not listing:
                        continue

                    # Pega token da conta ML do listing
                    acc_result = await db.execute(
                        select(MLAccount).where(MLAccount.id == listing.ml_account_id)
                    )
                    account = acc_result.scalar_one_or_none()
                    if not account or not account.access_token:
                        logger.warning(
                            f"Sem token ML para listing {listing.mlb_id} "
                            f"(concorrente {comp.mlb_id})"
                        )
                        continue

                    client = MLClient(account.access_token)
                    try:
                        item_data = await client.get_item(comp.mlb_id)
                    except MLClientError as e:
                        logger.warning(f"Erro ML ao buscar concorrente {comp.mlb_id}: {e}")
                        errors += 1
                        continue
                    finally:
                        await client.close()

                    current_price = Decimal(str(item_data.get("price", 0)))
                    current_sold = item_data.get("sold_quantity", 0) or 0

                    # Calcula sales_delta: diferença de sold_quantity em relação ao snapshot anterior
                    prev_snap_result = await db.execute(
                        select(CompetitorSnapshot)
                        .where(CompetitorSnapshot.competitor_id == comp.id)
                        .order_by(CompetitorSnapshot.captured_at.desc())
                        .limit(1)
                    )
                    prev_snap = prev_snap_result.scalar_one_or_none()

                    # sold_quantity cresce monotonicamente; delta = hoje - snapshot_anterior
                    # Se não há snapshot anterior ou sold_quantity não foi registrado, delta = 0
                    sales_delta = 0
                    if prev_snap is not None and prev_snap.sold_quantity is not None:
                        delta = current_sold - prev_snap.sold_quantity
                        # Delta nunca pode ser negativo (ML pode resetar contadores em itens pausados)
                        sales_delta = max(0, delta)

                    # Atualiza title do competitor se ainda não foi preenchido
                    if not comp.title:
                        comp.title = item_data.get("title", "")
                    if not comp.seller_id:
                        seller = item_data.get("seller_id")
                        if seller:
                            comp.seller_id = str(seller)

                    # Recupera visitas do resultado bulk (endpoint público — time_window last=1 day)
                    comp_mlb_normalized = comp.mlb_id.upper().replace("-", "")
                    if not comp_mlb_normalized.startswith("MLB"):
                        comp_mlb_normalized = f"MLB{comp_mlb_normalized}"
                    comp_visits = visits_data.get(comp_mlb_normalized, 0)

                    snap = CompetitorSnapshot(
                        competitor_id=comp.id,
                        price=current_price,
                        visits=comp_visits,
                        sales_delta=sales_delta,
                        sold_quantity=current_sold,
                    )
                    db.add(snap)
                    synced += 1

                except Exception as e:
                    logger.error(f"Erro inesperado ao sincronizar concorrente {comp.mlb_id}: {e}")
                    errors += 1

            await _finish_sync_log(
                db, sync_log, status="success", items=synced, failed=errors
            )
            logger.info(f"Sync concorrentes: {synced} ok, {errors} erros")
            return {"success": True, "synced": synced, "errors": errors}

        except Exception as exc:
            logger.error(f"Erro em _sync_competitor_snapshots_async: {exc}")
            await _finish_sync_log(
                db, sync_log, status="failed", error=str(exc)
            )
            raise


# --- Task: Avaliar alertas e disparar notificações ---

@celery_app.task(name="app.jobs.tasks.evaluate_alerts", bind=True)
def evaluate_alerts(self):
    """
    Avalia todas as configurações de alerta ativas.
    Executado a cada 2 horas.
    """
    try:
        return run_async(_evaluate_alerts_async())
    except Exception as exc:
        logger.error(f"Erro em evaluate_alerts: {exc}")
        raise


# --- Task: Sincronizar reputacao do vendedor ---

@celery_app.task(name="app.jobs.tasks.sync_reputation", bind=True)
def sync_reputation(self):
    """
    Sincroniza reputacao de todas as contas ML ativas.
    Executado diariamente as 06:30 BRT (09:30 UTC).
    """
    try:
        return run_async(_sync_reputation_async())
    except Exception as exc:
        logger.error(f"Erro em sync_reputation: {exc}")
        raise


async def _sync_reputation_async():
    """Busca reputacao de cada conta ML ativa e salva snapshot."""
    from app.reputacao.service import fetch_and_save_reputation

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MLAccount).where(MLAccount.is_active == True)  # noqa: E712
        )
        accounts = result.scalars().all()

        logger.info(f"Sincronizando reputacao de {len(accounts)} contas ML")

        synced, errors_count = 0, 0
        for account in accounts:
            try:
                snapshot = await fetch_and_save_reputation(db, account)
                if snapshot:
                    synced += 1
            except Exception as e:
                logger.error(f"Erro ao sincronizar reputacao de {account.nickname}: {e}")
                errors_count += 1

        await db.commit()
        logger.info(f"Reputacao: {synced} sincronizadas, {errors_count} erros")
        return {"success": True, "synced": synced, "errors": errors_count}


# --- Task: Sincronizar pedidos individuais ---

@celery_app.task(name="app.jobs.tasks.sync_orders", bind=True)
def sync_orders(self):
    """
    Sincroniza pedidos individuais dos ultimos 2 dias.
    Para cada conta ML ativa, busca pedidos recentes e os salva na tabela orders.
    Executado a cada 2 horas.
    """
    try:
        return run_async(_sync_orders_async())
    except Exception as exc:
        logger.error(f"Erro em sync_orders: {exc}")
        raise


async def _sync_orders_async():
    """
    Para cada ml_account ativa:
    1. Busca pedidos dos ultimos 2 dias via /orders/search
    2. Para cada order: upsert na tabela Order com todos os campos
    3. Extrai sale_fee do order_items, shipping_cost do payments e calcula net_amount
    """
    from datetime import date as date_type

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
                    logger.warning(f"Sem token ML para conta {account.nickname} — pulando")
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
                                unit_price = Decimal(str(first_item.get("unit_price", 0)))

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
                                    shipping_data.get("date_delivered") or
                                    shipping_data.get("estimated_delivery_time", {}).get("date")
                                    if isinstance(shipping_data.get("estimated_delivery_time"), dict)
                                    else None
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
                                    select(Order).where(Order.ml_order_id == ml_order_id)
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


# --- Task: Sincronizar campanhas de ads ---

@celery_app.task(name="app.jobs.tasks.sync_ads", bind=True)
def sync_ads(self):
    """
    Sincroniza campanhas e metricas de ads do Mercado Livre.
    Para cada conta ML ativa, chama ads/service.sync_ads_from_ml().
    Executado diariamente as 10:00 UTC (07:00 BRT).
    """
    try:
        return run_async(_sync_ads_async())
    except Exception as exc:
        logger.error(f"Erro em sync_ads: {exc}")
        raise


async def _sync_ads_async():
    """
    Para cada ml_account ativa:
    1. Cria MLClient com o token da conta
    2. Chama ads.service.sync_ads_from_ml() que faz upsert de AdCampaign e AdSnapshot
    """
    from app.ads.service import sync_ads_from_ml

    async with AsyncSessionLocal() as db:
        acc_result = await db.execute(
            select(MLAccount).where(MLAccount.is_active == True)  # noqa: E712
        )
        accounts = acc_result.scalars().all()

        logger.info(f"Sincronizando ads para {len(accounts)} contas ML")

        total_campaigns, total_snapshots, total_errors = 0, 0, 0

        for account in accounts:
            if not account.access_token:
                logger.warning(
                    f"Sem token ML para conta {account.nickname} — ads pulados"
                )
                continue

            client = MLClient(account.access_token)
            try:
                result = await sync_ads_from_ml(db, client, account)
                total_campaigns += result.get("synced_campaigns", 0)
                total_snapshots += result.get("synced_snapshots", 0)
                logger.info(
                    f"Ads sync OK para {account.nickname}: "
                    f"{result.get('synced_campaigns', 0)} campanhas, "
                    f"{result.get('synced_snapshots', 0)} snapshots"
                )
            except Exception as e:
                logger.error(f"Erro ao sincronizar ads de {account.nickname}: {e}")
                total_errors += 1
            finally:
                await client.close()

        logger.info(
            f"Sync ads: {total_campaigns} campanhas, "
            f"{total_snapshots} snapshots, {total_errors} erros"
        )
        return {
            "success": True,
            "total_campaigns": total_campaigns,
            "total_snapshots": total_snapshots,
            "errors": total_errors,
        }


async def _evaluate_alerts_async():
    """
    Busca todos os alert_configs ativos, avalia cada condição e,
    se disparada, cria AlertEvent e envia email se canal = 'email'.
    """
    from app.alertas.models import AlertConfig
    from app.alertas.service import evaluate_single_alert
    from app.auth.models import User
    from app.core.email import send_alert_email

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AlertConfig).where(AlertConfig.is_active == True)  # noqa: E712
        )
        configs = result.scalars().all()

        logger.info(f"Avaliando {len(configs)} alertas ativos")

        triggered, skipped, errors_count = 0, 0, 0

        for config in configs:
            try:
                event = await evaluate_single_alert(db, config)

                if event is None:
                    skipped += 1
                    continue

                triggered += 1

                # Envia email se canal = 'email'
                if config.channel == "email":
                    # Busca o email do usuário
                    user_result = await db.execute(
                        select(User).where(User.id == config.user_id)
                    )
                    user = user_result.scalar_one_or_none()
                    if user and user.email:
                        sent = send_alert_email(
                            to=user.email,
                            subject=f"MSM_Pro — Alerta: {config.alert_type}",
                            body=event.message,
                        )
                        if sent:
                            event.sent_at = datetime.now(timezone.utc)

            except Exception as e:
                logger.error(f"Erro ao avaliar alerta {config.id}: {e}")
                errors_count += 1

        # Detectar stock-out de concorrentes apos avaliar alertas configurados
        stockout_triggered = await _check_competitor_stockout(db)
        triggered += stockout_triggered

        await db.commit()
        logger.info(
            f"Avaliação concluída: {triggered} disparados, "
            f"{skipped} sem condição, {errors_count} erros"
        )
        return {
            "success": True,
            "triggered": triggered,
            "skipped": skipped,
            "errors": errors_count,
        }


async def _check_competitor_stockout(db) -> int:
    """
    Detecta possiveis stock-outs de concorrentes monitorados.

    Logica:
    1. Para cada Competitor ativo, busca os ultimos 3 CompetitorSnapshots.
    2. Se sold_quantity nao mudou por 3 snapshots consecutivos -> possivel stock-out.
    3. Gera AlertEvent do tipo 'competitor_stockout' vinculado ao listing do concorrente.
    4. Nao duplica: verifica se ja existe AlertEvent gerado nas ultimas 24h para o mesmo concorrente.

    Retorna a quantidade de alertas gerados.
    """
    from app.alertas.models import AlertConfig, AlertEvent
    from app.concorrencia.models import Competitor, CompetitorSnapshot
    from app.auth.models import User

    triggered = 0

    try:
        # Busca todos os competitors ativos com seus listings
        result = await db.execute(
            select(Competitor)
            .join(Listing, Competitor.listing_id == Listing.id)
            .where(Competitor.is_active == True)  # noqa: E712
        )
        competitors = result.scalars().all()

        for comp in competitors:
            try:
                # Busca os ultimos 3 snapshots do concorrente
                snaps_result = await db.execute(
                    select(CompetitorSnapshot)
                    .where(CompetitorSnapshot.competitor_id == comp.id)
                    .order_by(CompetitorSnapshot.captured_at.desc())
                    .limit(3)
                )
                snaps = snaps_result.scalars().all()

                if len(snaps) < 3:
                    # Nao tem historico suficiente para detectar stock-out
                    continue

                # Verifica se sold_quantity nao mudou nos 3 ultimos snapshots
                sold_quantities = [s.sold_quantity for s in snaps if s.sold_quantity is not None]
                if len(sold_quantities) < 3:
                    continue

                is_static = sold_quantities[0] == sold_quantities[1] == sold_quantities[2]
                if not is_static:
                    continue

                # Verifica se ja existe alerta de stock-out gerado nas ultimas 24h
                cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)

                # Busca AlertConfig do tipo competitor_stockout para o listing deste concorrente
                # Se nao existir, cria um sistema automatico
                existing_event_result = await db.execute(
                    select(AlertEvent)
                    .join(AlertConfig, AlertEvent.alert_config_id == AlertConfig.id)
                    .where(
                        AlertConfig.listing_id == comp.listing_id,
                        AlertConfig.alert_type == "competitor_stockout",
                        AlertEvent.triggered_at >= cutoff_24h,
                    )
                    .limit(1)
                )
                existing_event = existing_event_result.scalar_one_or_none()

                if existing_event:
                    # Ja gerou alerta recentemente, pula
                    continue

                # Busca ou cria AlertConfig para este listing do tipo competitor_stockout
                config_result = await db.execute(
                    select(AlertConfig)
                    .where(
                        AlertConfig.listing_id == comp.listing_id,
                        AlertConfig.alert_type == "competitor_stockout",
                    )
                    .limit(1)
                )
                config = config_result.scalar_one_or_none()

                if not config:
                    # Busca o user_id a partir do listing
                    listing_result = await db.execute(
                        select(Listing).where(Listing.id == comp.listing_id)
                    )
                    listing = listing_result.scalar_one_or_none()
                    if not listing:
                        continue

                    config = AlertConfig(
                        user_id=listing.user_id,
                        listing_id=comp.listing_id,
                        alert_type="competitor_stockout",
                        channel="email",
                        is_active=True,
                    )
                    db.add(config)
                    await db.flush()

                # Cria o AlertEvent de stock-out
                comp_title = comp.title or comp.mlb_id
                message = (
                    f"Concorrente '{comp_title}' possivelmente sem estoque. "
                    f"Quantidade vendida nao mudou nos ultimos 3 snapshots "
                    f"({sold_quantities[2]} -> {sold_quantities[1]} -> {sold_quantities[0]}). "
                    f"Oportunidade de ajuste de preco ou aumento de exposicao."
                )

                event = AlertEvent(
                    alert_config_id=config.id,
                    message=message,
                )
                db.add(event)
                triggered += 1

                logger.info(
                    f"Alerta de stock-out gerado: concorrente {comp.mlb_id} "
                    f"(listing {comp.listing_id})"
                )

            except Exception as e:
                logger.error(f"Erro ao verificar stock-out do concorrente {comp.mlb_id}: {e}")

    except Exception as e:
        logger.error(f"Erro geral em _check_competitor_stockout: {e}")

    return triggered
