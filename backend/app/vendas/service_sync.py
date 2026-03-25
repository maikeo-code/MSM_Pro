"""
Sincronização de anúncios e snapshots com o Mercado Livre.
"""
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from uuid import UUID

# Timezone BRT (UTC-3)
BRT = timezone(timedelta(hours=-3))

from fastapi import HTTPException, status
from sqlalchemy import cast, Date, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.vendas.models import Listing, ListingSnapshot
from app.vendas.service_health import calculate_quality_score_quick


async def sync_listings_from_ml(db: AsyncSession, user_id: UUID) -> dict:
    """
    Busca todos os anúncios ativos das contas ML do usuário e salva no banco.
    Retorna contagem de novos e atualizados.
    """
    from app.auth.models import MLAccount
    from app.mercadolivre.client import MLClient, MLClientError

    # Busca todas as contas ML ativas do usuário
    result = await db.execute(
        select(MLAccount).where(
            MLAccount.user_id == user_id,
            MLAccount.is_active == True,  # noqa: E712
        )
    )
    accounts = result.scalars().all()

    if not accounts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhuma conta ML conectada. Conecte uma conta primeiro.",
        )

    created = 0
    updated = 0
    errors = []

    for account in accounts:
        if not account.access_token:
            continue

        try:
            async with MLClient(account.access_token) as client:
                # Busca IDs dos anúncios ativos
                offset = 0
                all_item_ids = []
                while True:
                    resp = await client.get_user_listings(
                        account.ml_user_id, offset=offset, limit=50
                    )
                    item_ids = resp.get("results", [])
                    all_item_ids.extend(item_ids)
                    if len(item_ids) < 50:
                        break
                    offset += 50

                # Busca detalhes de cada anúncio
                for mlb_id in all_item_ids:
                    try:
                        item = await client.get_item(mlb_id)

                        listing_type_raw = item.get("listing_type_id", "gold_special")
                        shipping = item.get("shipping", {})
                        is_fulfillment = shipping.get("logistic_type") == "fulfillment"
                        if "gold_pro" in listing_type_raw and is_fulfillment:
                            listing_type = "full"
                        elif "gold_pro" in listing_type_raw:
                            listing_type = "premium"
                        else:
                            listing_type = "classico"

                        price = Decimal(str(item.get("price", 0)))
                        stock = item.get("available_quantity", 0)

                        # ── Preço real: usar /items/{id}/sale_price como fonte primária ──
                        # O campo "price" do /items está sendo depreciado pelo ML (março 2026).
                        # O endpoint /sale_price retorna o preço REAL que o comprador vê,
                        # considerando todas as camadas de desconto.
                        original_price = None
                        sale_price_val = None
                        used_sale_price_endpoint = False

                        try:
                            sp_response = await client.get_item_sale_price(mlb_id)
                            if sp_response and sp_response.get("amount") is not None:
                                price = Decimal(str(sp_response["amount"]))
                                reg_amount = sp_response.get("regular_amount")
                                if reg_amount is not None:
                                    original_price = Decimal(str(reg_amount))
                                used_sale_price_endpoint = True
                        except Exception:
                            pass

                        # Fallback: lógica legada usando campos do /items
                        if not used_sale_price_endpoint:
                            original_price_raw = item.get("original_price")
                            original_price = Decimal(str(original_price_raw)) if original_price_raw else None

                            sale_price_data = item.get("sale_price")
                            if sale_price_data and isinstance(sale_price_data, dict):
                                sp_amount = sale_price_data.get("amount")
                                if sp_amount is not None:
                                    sale_price_val = Decimal(str(sp_amount))

                            if sale_price_val is not None and price > sale_price_val:
                                if original_price is None:
                                    original_price = price
                                price = sale_price_val

                            # Último fallback: seller-promotions
                            if original_price is None:
                                try:
                                    promotions = await client.get_item_promotions(mlb_id)
                                    for promo in promotions:
                                        if promo.get("status") == "started" and promo.get("original_price"):
                                            original_price = Decimal(str(promo["original_price"]))
                                            promo_price = promo.get("price")
                                            if promo_price is not None:
                                                price = Decimal(str(promo_price))
                                            break
                                except Exception:
                                    pass

                        # Verifica se listing já existe
                        existing = await db.execute(
                            select(Listing).where(Listing.mlb_id == mlb_id)
                        )
                        listing = existing.scalar_one_or_none()

                        # Extrai category_id e seller_sku
                        category_id = item.get("category_id")
                        seller_sku = item.get("seller_custom_field")
                        if not seller_sku and item.get("attributes"):
                            for attr in item["attributes"]:
                                if attr.get("id") == "SELLER_SKU":
                                    seller_sku = (
                                        attr.get("value_name")
                                        or attr.get("value_id")
                                        or (attr.get("values", [{}])[0].get("name") if attr.get("values") else None)
                                    )
                                    break
                        # Usar secure_thumbnail (HTTPS) quando disponível
                        thumbnail = item.get("secure_thumbnail") or item.get("thumbnail")

                        # Busca taxa real via API listing_prices
                        sale_fee_amount = None
                        sale_fee_pct = None
                        if category_id and listing_type_raw:
                            try:
                                fees_data = await client.get_listing_fees(
                                    price=float(price),
                                    category_id=category_id,
                                    listing_type_id=listing_type_raw,
                                )
                                if fees_data.get("sale_fee_amount"):
                                    sale_fee_amount = Decimal(str(fees_data["sale_fee_amount"]))
                                pct_fee = fees_data.get("percentage_fee")
                                if pct_fee and pct_fee > 0:
                                    sale_fee_pct = Decimal(str(pct_fee / 100))
                            except Exception:
                                pass  # fallback para taxa fixa

                        if listing:
                            listing.title = item.get("title", listing.title)
                            listing.price = price
                            listing.original_price = original_price
                            listing.sale_price = sale_price_val
                            listing.status = item.get("status", "active")
                            listing.thumbnail = thumbnail
                            listing.permalink = item.get("permalink")
                            listing.category_id = category_id
                            listing.seller_sku = seller_sku
                            if sale_fee_amount is not None:
                                listing.sale_fee_amount = sale_fee_amount
                            if sale_fee_pct is not None:
                                listing.sale_fee_pct = sale_fee_pct
                            # Calcula quality_score durante sync
                            listing.quality_score = calculate_quality_score_quick(listing)
                            await db.flush()
                            updated += 1
                        else:
                            listing = Listing(
                                user_id=user_id,
                                ml_account_id=account.id,
                                mlb_id=mlb_id,
                                title=item.get("title", mlb_id),
                                listing_type=listing_type,
                                price=price,
                                original_price=original_price,
                                sale_price=sale_price_val,
                                status=item.get("status", "active"),
                                thumbnail=thumbnail,
                                permalink=item.get("permalink"),
                                category_id=category_id,
                                seller_sku=seller_sku,
                                sale_fee_amount=sale_fee_amount,
                                sale_fee_pct=sale_fee_pct,
                            )
                            # Calcula quality_score para novo listing
                            listing.quality_score = calculate_quality_score_quick(listing)
                            db.add(listing)
                            await db.flush()
                            created += 1

                        # Busca visitas de hoje via time_window (endpoint que funciona por dia)
                        visits_today = 0
                        try:
                            today_str = datetime.now(BRT).date().isoformat()
                            visits_resp = await client._request(
                                "GET",
                                f"/items/{mlb_id}/visits/time_window",
                                params={"last": 1, "unit": "day"},
                            )
                            for day_data in visits_resp.get("results", []):
                                if day_data.get("date", "").startswith(today_str):
                                    visits_today = day_data.get("total", 0)
                                    break
                            # Se não achou hoje especificamente, pega o mais recente
                            if visits_today == 0 and visits_resp.get("results"):
                                visits_today = visits_resp["results"][0].get("total", 0)
                        except Exception:
                            pass

                        # BUG 1 FIX: verificar se já existe snapshot do mesmo dia antes de inserir
                        # Usa .first() em vez de scalar_one_or_none() porque pode haver
                        # múltiplos snapshots do mesmo dia (duplicatas antigas)
                        existing_snap_result = await db.execute(
                            select(ListingSnapshot).where(
                                ListingSnapshot.listing_id == listing.id,
                                cast(ListingSnapshot.captured_at, Date) == datetime.now(BRT).date(),
                            ).order_by(ListingSnapshot.captured_at.desc()).limit(1)
                        )
                        existing_snap = existing_snap_result.scalar_one_or_none()
                        if existing_snap:
                            existing_snap.price = price
                            existing_snap.visits = visits_today
                            existing_snap.stock = stock
                            existing_snap.captured_at = datetime.utcnow()
                            await db.flush()
                        else:
                            snapshot = ListingSnapshot(
                                listing_id=listing.id,
                                price=price,
                                visits=visits_today,
                                sales_today=0,  # será preenchido abaixo via orders
                                questions=0,
                                stock=stock,
                                conversion_rate=None,
                            )
                            db.add(snapshot)

                    except MLClientError as e:
                        errors.append(f"{mlb_id}: {e}")
                        continue

                # Busca vendas de hoje via orders API e atualiza snapshots
                try:
                    today = datetime.now(BRT).date()
                    today_start = f"{today.isoformat()}T00:00:00.000-03:00"

                    orders_resp = await client._request(
                        "GET",
                        "/orders/search",
                        params={
                            "seller": account.ml_user_id,
                            "order.date_created.from": today_start,
                            "sort": "date_desc",
                            "limit": 50,
                        },
                    )

                    # Conta vendas por MLB ID
                    sales_by_mlb: dict[str, int] = {}
                    for order in orders_resp.get("results", []):
                        for oi in order.get("order_items", []):
                            oi_mlb = oi.get("item", {}).get("id", "")
                            qty = oi.get("quantity", 1)
                            sales_by_mlb[oi_mlb] = sales_by_mlb.get(oi_mlb, 0) + qty

                    # Atualiza snapshots com vendas reais
                    for mlb_id_raw, sales_count in sales_by_mlb.items():
                        if sales_count > 0:
                            lst_result = await db.execute(
                                select(Listing).where(Listing.mlb_id == mlb_id_raw)
                            )
                            lst = lst_result.scalar_one_or_none()
                            if lst:
                                snap_result = await db.execute(
                                    select(ListingSnapshot)
                                    .where(ListingSnapshot.listing_id == lst.id)
                                    .order_by(ListingSnapshot.captured_at.desc())
                                    .limit(1)
                                )
                                snap = snap_result.scalar_one_or_none()
                                if snap:
                                    snap.sales_today = sales_count
                                    if snap.visits > 0:
                                        snap.conversion_rate = Decimal(
                                            str(round((sales_count / snap.visits) * 100, 2))
                                        )
                                    await db.flush()
                except Exception:
                    # Não bloquear sync se orders falharem
                    pass

        except MLClientError as e:
            errors.append(f"Conta {account.nickname}: {e}")
            continue

    await db.commit()

    return {
        "created": created,
        "updated": updated,
        "total": created + updated,
        "errors": errors,
        "message": f"Sync concluído: {created} novos, {updated} atualizados.",
    }
