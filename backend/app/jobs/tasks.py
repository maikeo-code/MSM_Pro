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

            # Busca pedidos PAGOS (unidades vendidas + receita)
            sales_today = 0
            orders_count = 0
            revenue = Decimal("0")
            mlb_normalized = listing.mlb_id.upper().replace("-", "")
            try:
                paid_orders = await client.get_item_orders_by_status(
                    listing.mlb_id, account.ml_user_id, days=1, status="paid"
                )
                for order in paid_orders:
                    for oi in order.get("order_items", []):
                        # Normaliza ambos os lados para comparação exata —
                        # a API pode retornar o item_id com ou sem hífen
                        item_id = oi.get("item", {}).get("id", "").upper().replace("-", "")
                        if item_id == mlb_normalized:
                            qty = oi.get("quantity", 1)
                            unit_price = Decimal(str(oi.get("unit_price", 0)))
                            sales_today += qty
                            orders_count += 1
                            revenue += unit_price * qty
            except MLClientError:
                logger.debug(f"Não conseguiu buscar pedidos pagos para {listing.mlb_id}")

            avg_selling_price = (revenue / sales_today) if sales_today > 0 else None

            # Busca pedidos CANCELADOS
            cancelled_orders = 0
            try:
                cancelled_data = await client.get_item_orders_by_status(
                    listing.mlb_id, account.ml_user_id, days=1, status="cancelled"
                )
                for order in cancelled_data:
                    for oi in order.get("order_items", []):
                        item_id = oi.get("item", {}).get("id", "").upper().replace("-", "")
                        if item_id == mlb_normalized:
                            cancelled_orders += 1
            except MLClientError:
                logger.debug(f"Não conseguiu buscar pedidos cancelados para {listing.mlb_id}")

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
                )
                db.add(snapshot)

            # Atualiza preço, status e campos de desconto do listing
            listing.price = price
            listing.original_price = original_price
            listing.sale_price = sale_price_val
            listing.status = status
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
        return {
            "success": True,
            "dispatched": len(dispatched),
            "listing_ids": dispatched,
        }


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
    CompetitorSnapshot com preço atual e sales_delta.

    Não precisa de token próprio — usa o token da conta vinculada ao listing.
    """
    from app.concorrencia.models import Competitor, CompetitorSnapshot

    async with AsyncSessionLocal() as db:
        # Carrega todos competitors ativos com o listing para acessar a conta ML
        result = await db.execute(
            select(Competitor)
            .join(Listing, Competitor.listing_id == Listing.id)
            .where(Competitor.is_active == True)  # noqa: E712
        )
        competitors = result.scalars().all()

        logger.info(f"Iniciando sync de {len(competitors)} concorrentes")

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
                current_sold = item_data.get("sold_quantity", 0)

                # Calcula sales_delta: diferença de sold_quantity em relação ao snapshot anterior
                prev_snap_result = await db.execute(
                    select(CompetitorSnapshot)
                    .where(CompetitorSnapshot.competitor_id == comp.id)
                    .order_by(CompetitorSnapshot.captured_at.desc())
                    .limit(1)
                )
                prev_snap = prev_snap_result.scalar_one_or_none()
                # sold_quantity não fica no snapshot — estimativa pelo delta de price
                # Usa 0 quando não há histórico anterior
                sales_delta = 0
                if prev_snap is None:
                    sales_delta = 0
                else:
                    # sold_quantity cresce monotonicamente; delta = hoje - ontem
                    # Como não persistimos sold_quantity, usamos 0 como fallback seguro
                    sales_delta = 0

                # Atualiza title do competitor se ainda não foi preenchido
                if not comp.title:
                    comp.title = item_data.get("title", "")
                if not comp.seller_id:
                    seller = item_data.get("seller_id")
                    if seller:
                        comp.seller_id = str(seller)

                snap = CompetitorSnapshot(
                    competitor_id=comp.id,
                    price=current_price,
                    visits=0,  # API pública não expõe visitas de terceiros
                    sales_delta=sales_delta,
                )
                db.add(snap)
                synced += 1

            except Exception as e:
                logger.error(f"Erro inesperado ao sincronizar concorrente {comp.mlb_id}: {e}")
                errors += 1

        await db.commit()
        logger.info(f"Sync concorrentes: {synced} ok, {errors} erros")
        return {"success": True, "synced": synced, "errors": errors}


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
