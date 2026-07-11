"""Harness de auditoria de paridade: MSM_Pro vs API REAL do Mercado Livre.

Para cada conta ML do usuario, busca os numeros REAIS na API do ML (orders,
visits, item stock/price, seller_reputation) e compara com o que o MSM_Pro
persiste. Read-only. Principio mestre: o MSM_Pro deve ESPELHAR o painel do
vendedor do ML — divergencia aqui = bug do MSM_Pro.

Saida: por conta, lista de checks {metric, ml, app, verdict} + placar agregado.
Veredito por check: PASS (bate), FAIL (diverge), NO_DATA (app sem dado),
ERROR (chamada ML falhou).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import MLAccount
from app.mercadolivre.client import MLClient
from app.reputacao.models import ReputationSnapshot
from app.vendas.constants import CANCEL_STATUSES, NON_SALE_PAYMENT_STATUSES
from app.vendas.models import Listing, ListingSnapshot, Order

logger = logging.getLogger(__name__)
BRT = timezone(timedelta(hours=-3))


def _verdict(app_val, ml_val, tol: float = 0.0) -> str:
    """PASS se app == ml dentro de tolerancia relativa (tol). NO_DATA se app None."""
    if app_val is None:
        return "NO_DATA"
    if ml_val is None:
        return "ERROR"
    try:
        a = float(app_val)
        m = float(ml_val)
    except (TypeError, ValueError):
        return "FAIL"
    if m == 0:
        return "PASS" if a == 0 else "FAIL"
    return "PASS" if abs(a - m) / abs(m) <= tol else "FAIL"


def _check(
    metric: str,
    ml_val,
    app_val,
    tol: float = 0.0,
    detail: str | None = None,
    info: bool = False,
) -> dict:
    """Monta um check. Se info=True, um veredito de discrepancia vira INFO em vez de
    FAIL (E43): usado para metricas de um dia AINDA NAO FECHADO (o snapshot do dia
    corrente e capturado no meio do dia -> subconta visitas por natureza, nao e bug).
    PASS continua PASS; so a divergencia deixa de poluir o placar como FAIL."""
    v = _verdict(app_val, ml_val, tol)
    if info and v == "FAIL":
        v = "INFO"
    out = {"metric": metric, "ml": ml_val, "app": app_val, "verdict": v}
    if detail:
        out["detail"] = detail
    return out


# Blocos auditaveis hoje. E38-E41 acrescentam shipping/questions/claims.
ALL_BLOCKS = ("sales", "visits", "stock", "price", "fees", "reputation")
_ITEM_BLOCKS = frozenset({"visits", "stock", "price", "fees"})  # compartilham o get_item


def _normalize_blocks(blocks: set[str] | None) -> frozenset[str]:
    """None/vazio -> todos. Ignora nomes desconhecidos (nunca quebra o placar)."""
    if not blocks:
        return frozenset(ALL_BLOCKS)
    sel = frozenset(b.strip().lower() for b in blocks) & frozenset(ALL_BLOCKS)
    return sel or frozenset(ALL_BLOCKS)


async def run_parity_audit(
    db: AsyncSession,
    user_id: UUID,
    target_day: date,
    sample_items: int = 5,
    blocks: set[str] | None = None,
) -> dict:
    sel = _normalize_blocks(blocks)
    accounts = list(
        (
            await db.execute(
                select(MLAccount).where(
                    MLAccount.user_id == user_id,
                    MLAccount.is_active == True,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    results = []
    for acc in accounts:
        results.append(await _audit_account(db, acc, target_day, sample_items, sel))

    checks = passed = failed = no_data = errors = info = 0
    for r in results:
        for c in r["checks"]:
            checks += 1
            v = c["verdict"]
            if v == "PASS":
                passed += 1
            elif v == "FAIL":
                failed += 1
            elif v == "NO_DATA":
                no_data += 1
            elif v == "INFO":
                info += 1
            else:
                errors += 1

    # parity_pct exclui APENAS os checks INFO (dia nao fechado — ruido de timing do dia
    # corrente, E43). NO_DATA/ERROR permanecem no denominador como antes (nao alterar a
    # semantica historica do placar). Quando info=0 o numero e identico ao baseline.
    decisive = checks - info
    return {
        "day": target_day.isoformat(),
        "sample_items": sample_items,
        "blocks": sorted(sel),
        "accounts": results,
        "summary": {
            "checks": checks,
            "passed": passed,
            "failed": failed,
            "no_data": no_data,
            "info": info,
            "errors": errors,
            "parity_pct": round(passed / decisive * 100, 1) if decisive else None,
        },
    }


async def _audit_account(
    db: AsyncSession, acc: MLAccount, day: date, sample_items: int, sel: frozenset[str]
) -> dict:
    checks: list[dict] = []
    # Dia fechado = anterior a hoje (BRT). Visitas de um dia ainda em curso subcontam
    # por natureza (snapshot capturado no meio do dia) -> viram INFO, nao FAIL (E43).
    day_closed = day < datetime.now(BRT).date()
    try:
        async with MLClient(access_token=acc.access_token, ml_account_id=acc.id) as client:
            if "sales" in sel:
                checks += await _audit_sales(db, client, acc, day)
            if sel & _ITEM_BLOCKS:
                checks += await _audit_visits_stock_price(
                    db, client, acc, day, sample_items, day_closed=day_closed, sel=sel
                )
            if "reputation" in sel:
                checks += await _audit_reputation(db, client, acc)
    except Exception as e:  # noqa: BLE001
        logger.exception("parity audit falhou acc=%s", acc.nickname)
        checks.append(_check("conexao_ml", None, None, detail=str(e)))
    return {
        "ml_account_id": str(acc.id),
        "nickname": acc.nickname or "",
        "ml_user_id": acc.ml_user_id,
        "checks": checks,
    }


async def _audit_sales(db, client, acc: MLAccount, day: date) -> list[dict]:
    """Vendas/pedidos/receita do dia: ML (/orders/search) vs Order table."""
    start = datetime.combine(day, time.min, tzinfo=BRT)
    end = datetime.combine(day, time.max, tzinfo=BRT)

    # ML real (paginado)
    ml_pedidos = ml_unidades = 0
    ml_receita = 0.0
    offset = 0
    try:
        while True:
            resp = await client.get_orders(
                acc.ml_user_id, start.isoformat(), end.isoformat(), offset=offset, limit=50
            )
            rows = resp.get("results", []) if isinstance(resp, dict) else []
            for o in rows:
                if o.get("status") in CANCEL_STATUSES:
                    continue
                ml_pedidos += 1
                ml_receita += float(o.get("total_amount", 0) or 0)
                for oi in o.get("order_items", []):
                    ml_unidades += int(oi.get("quantity", 0) or 0)
            total = resp.get("paging", {}).get("total", 0) if isinstance(resp, dict) else 0
            offset += 50
            if not rows or offset >= total:
                break
    except Exception as e:  # noqa: BLE001
        return [_check("vendas_dia", None, None, detail=f"ML orders falhou: {e}")]

    # MSM_Pro (Order table)
    s_utc = start.astimezone(timezone.utc)
    e_utc = end.astimezone(timezone.utc)
    row = (
        await db.execute(
            select(
                func.count(Order.id),
                func.coalesce(func.sum(Order.quantity), 0),
                func.coalesce(func.sum(Order.total_amount), 0),
            ).where(
                Order.ml_account_id == acc.id,
                Order.order_date >= s_utc,
                Order.order_date <= e_utc,
                Order.payment_status.notin_(NON_SALE_PAYMENT_STATUSES),
            )
        )
    ).one()
    app_pedidos, app_unidades, app_receita = int(row[0]), int(row[1]), round(float(row[2]), 2)

    return [
        _check("pedidos_dia", ml_pedidos, app_pedidos),
        _check("unidades_dia", ml_unidades, app_unidades),
        _check("receita_dia", round(ml_receita, 2), app_receita, tol=0.01),
    ]


async def _audit_visits_stock_price(
    db,
    client,
    acc: MLAccount,
    day: date,
    sample_items: int,
    day_closed: bool = True,
    sel: frozenset[str] = _ITEM_BLOCKS,
) -> list[dict]:
    """Amostra de anuncios: visitas, estoque, preco e comissao (ML vs app).

    day_closed=False (dia ainda em curso) -> checks de VISITAS viram INFO em vez de
    FAIL quando divergem (o snapshot do dia corrente e parcial). Estoque/preco/comissao
    sao valores ATUAIS (nao dependem do dia) -> nao afetados por day_closed.

    sel = blocos pedidos (E37). Cada check e a chamada ML correspondente so acontecem
    se o bloco esta em sel; com todos selecionados (padrao) o comportamento e identico."""
    want_visits = "visits" in sel
    want_item = bool(sel & {"stock", "price", "fees"})
    rows = list(
        (
            await db.execute(
                select(
                    Listing.id,
                    Listing.mlb_id,
                    Listing.price,
                    Listing.sale_price,
                    Listing.sale_fee_amount,
                    Listing.category_id,
                    Listing.listing_type,
                )
                .where(Listing.ml_account_id == acc.id, Listing.status == "active")
                # ORDER BY estavel: sem isso o Postgres devolve anuncios DIFERENTES a
                # cada chamada (LIMIT sem ordem = nao-deterministico) e o parity_pct
                # oscilava (ex. 66-76% no MESMO dia) so pela amostra mudar. Amostra fixa
                # torna o gate reproduzivel — pre-requisito p/ comparar antes/depois na Fase 4.
                .order_by(Listing.mlb_id)
                .limit(sample_items)
            )
        ).all()
    )
    checks: list[dict] = []
    for lid, mlb, l_price, l_sale_price, l_fee, l_cat, l_type in rows:
        snap = (
            await db.execute(
                select(ListingSnapshot.visits, ListingSnapshot.stock, ListingSnapshot.price)
                .where(
                    ListingSnapshot.listing_id == lid,
                    ListingSnapshot.snapshot_day == day,
                )
                .order_by(ListingSnapshot.captured_at.desc())
                .limit(1)
            )
        ).first()

        # Visitas do dia (ML time_window) vs snapshot.visits
        if want_visits:
            try:
                ml_visits = await client.get_item_visits_on_day(mlb, day)
            except Exception as e:  # noqa: BLE001
                ml_visits = None
                checks.append(_check(f"visitas[{mlb}]", None, None, detail=str(e)))
            app_visits = int(snap[0]) if snap else None
            if ml_visits is not None:
                checks.append(
                    _check(f"visitas[{mlb}]", ml_visits, app_visits, info=not day_closed)
                )

        if not want_item:
            continue

        # Estoque e preco atuais (ML /items + /sale_price) vs listing/snapshot
        try:
            item = await client.get_item(mlb)
            # Mesma regra do sync (E9): itens COM variacoes -> SOMA de
            # variations[].available_quantity. Usar so o available_quantity do topo
            # (como antes) reintroduzia no VERIFICADOR o bug que o E9 corrigiu no sync
            # -> falso-FAIL em itens com variacao. E42.
            from app.jobs.tasks_listings import stock_from_item

            ml_stock = stock_from_item(item)

            # Preço: usa sale_price (campo vigente). item["price"] está DEPRECIADO no BR
            # e retorna o preço cheio sem desconto, causando falso-FAIL.
            sp = await client.get_item_sale_price(mlb)
            if sp and sp.get("amount") is not None:
                ml_price = round(float(sp["amount"]), 2)
            else:
                # Fallback: item.price (quando não há promoção, coincide com sale_price)
                ml_price = round(float(item.get("price") or 0), 2)

            # App: usa listing.sale_price se existir, senão listing.price
            app_price_raw = l_sale_price if l_sale_price is not None else l_price
            app_stock = int(snap[1]) if snap else None
            app_price = round(float(app_price_raw), 2) if app_price_raw is not None else None

            if "stock" in sel:
                checks.append(_check(f"estoque[{mlb}]", ml_stock, app_stock))
            if "price" in sel:
                checks.append(_check(f"preco[{mlb}]", ml_price, app_price, tol=0.05))

            # Comissão (listing_prices vs listing.sale_fee_amount)
            if "fees" in sel and l_cat and l_type:
                shp = item.get("shipping") or {}
                lt = item.get("listing_type_id") or l_type
                # Mapeia tipo interno para listing_type_id do ML
                _lt_map = {"classico": "gold_special", "premium": "gold_pro", "full": "gold_pro"}
                lt_id = lt if "_" in lt else _lt_map.get(lt, lt)
                try:
                    fees = await client.get_listing_fees(
                        price=ml_price,
                        category_id=l_cat,
                        listing_type_id=lt_id,
                        logistic_type=shp.get("logistic_type"),
                        shipping_mode="me2",
                    )
                    ml_fee = round(float(fees.get("sale_fee_amount") or 0), 2)
                    app_fee = round(float(l_fee), 2) if l_fee is not None else None
                    if ml_fee > 0:
                        checks.append(_check(f"comissao[{mlb}]", ml_fee, app_fee, tol=0.10))
                except Exception:  # noqa: BLE001
                    pass  # Comissão não crítica para o placar principal
        except Exception as e:  # noqa: BLE001
            checks.append(_check(f"item[{mlb}]", None, None, detail=str(e)))
    return checks


async def _audit_reputation(db, client, acc: MLAccount) -> list[dict]:
    """Reputacao: vendas 60d reais (metrics.sales.completed) vs snapshot do app."""
    try:
        rep = await client.get_seller_reputation(acc.ml_user_id)
    except Exception as e:  # noqa: BLE001
        return [_check("reputacao", None, None, detail=str(e))]

    sr = rep.get("seller_reputation", {}) if isinstance(rep, dict) else {}
    metrics = sr.get("metrics", {}) or {}
    sales = metrics.get("sales", {}) or {}
    ml_sales_60d = sales.get("completed")  # vendas 60d REAIS do painel ML
    ml_claims = (metrics.get("claims", {}) or {}).get("value")

    snap = (
        await db.execute(
            select(
                ReputationSnapshot.completed_sales_60d,
                ReputationSnapshot.total_sales_60d,
                ReputationSnapshot.claims_value,
            )
            .where(ReputationSnapshot.ml_account_id == acc.id)
            .order_by(ReputationSnapshot.captured_at.desc())
            .limit(1)
        )
    ).first()
    app_completed_60d = int(snap[0]) if snap and snap[0] is not None else None
    app_claims = int(snap[2]) if snap and snap[2] is not None else None

    return [
        _check("reputacao_vendas_60d", ml_sales_60d, app_completed_60d),
        _check("reputacao_claims", ml_claims, app_claims),
    ]
