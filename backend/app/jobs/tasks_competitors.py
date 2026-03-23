"""
Lógica assíncrona para sincronização de concorrentes monitorados.

Funções exportadas:
  - _sync_competitor_snapshots_async: sincroniza preços e visitas de todos os concorrentes ativos
  - _check_competitor_stockout: detecta possíveis stock-outs de concorrentes
"""
import logging
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.auth.models import MLAccount
from app.core.database import AsyncSessionLocal
from app.mercadolivre.client import MLClient, MLClientError
from app.vendas.models import Listing

from .tasks_helpers import _create_sync_log, _finish_sync_log

logger = logging.getLogger(__name__)


async def _sync_competitor_snapshots_async():
    """
    Busca todos os Competitor ativos, chama a API ML para cada um e salva
    CompetitorSnapshot com preço atual, visitas e sales_delta.

    Visitas: endpoint GET /items/{id}/visits/time_window?last=1&unit=day é público
    — não precisa de token do dono. Busca em batch via get_items_visits_bulk()
    antes do loop principal para evitar N chamadas individuais.
    """
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
                # Passa ml_account_id ao cliente para suportar refresh automático
                bulk_client = MLClient(first_account.access_token, ml_account_id=str(first_account.id))
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
                logger.warning(
                    "Nenhuma conta ML ativa encontrada — visitas de concorrentes serão 0"
                )

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

                    # Passa ml_account_id ao cliente para suportar refresh automático
                    client = MLClient(account.access_token, ml_account_id=str(account.id))
                    try:
                        item_data = await client.get_item(comp.mlb_id)
                    except MLClientError as e:
                        logger.warning(
                            f"Erro ML ao buscar concorrente {comp.mlb_id}: {e}"
                        )
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
                    logger.error(
                        f"Erro inesperado ao sincronizar concorrente {comp.mlb_id}: {e}"
                    )
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
                sold_quantities = [
                    s.sold_quantity for s in snaps if s.sold_quantity is not None
                ]
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
                logger.error(
                    f"Erro ao verificar stock-out do concorrente {comp.mlb_id}: {e}"
                )

    except Exception as e:
        logger.error(f"Erro geral em _check_competitor_stockout: {e}")

    return triggered
