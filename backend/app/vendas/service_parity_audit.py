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


def _check(metric: str, ml_val, app_val, tol: float = 0.0, detail: str | None = None) -> dict:
    v = _verdict(app_val, ml_val, tol)
    out = {"metric": metric, "ml": ml_val, "app": app_val, "verdict": v}
    if detail:
        out["detail"] = detail
    return out


async def run_parity_audit(
    db: AsyncSession,
    user_id: UUID,
    target_day: date,
    sample_items: int = 5,
) -> dict:
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
        results.append(await _audit_account(db, acc, target_day, sample_items))

    checks = passed = failed = no_data = errors = 0
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
            else:
                errors += 1

    return {
        "day": target_day.isoformat(),
        "sample_items": sample_items,
        "accounts": results,
        "summary": {
            "checks": checks,
            "passed": passed,
            "failed": failed,
            "no_data": no_data,
            "errors": errors,
            "parity_pct": round(passed / checks * 100, 1) if checks else None,
        },
    }


async def _audit_account(
    db: AsyncSession, acc: MLAccount, day: date, sample_items: int
) -> dict:
    checks: list[dict] = []
    try:
        async with MLClient(access_token=acc.access_token, ml_account_id=acc.id) as client:
            checks += await _audit_sales(db, client, acc, day)
            checks += await _audit_visits_stock_price(db, client, acc, day, sample_items)
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
    db, client, acc: MLAccount, day: date, sample_items: int
) -> list[dict]:
    """Amostra de anuncios: visitas do dia, estoque e preco (ML /items vs snapshot)."""
    listings = list(
        (
            await db.execute(
                select(Listing.id, Listing.mlb_id)
                .where(Listing.ml_account_id == acc.id, Listing.status == "active")
                .limit(sample_items)
            )
        ).all()
    )
    checks: list[dict] = []
    for lid, mlb in listings:
        # Visitas do dia (ML time_window) vs snapshot.visits
        try:
            ml_visits = await client.get_item_visits_on_day(mlb, day)
        except Exception as e:  # noqa: BLE001
            ml_visits = None
            checks.append(_check(f"visitas[{mlb}]", None, None, detail=str(e)))
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
        app_visits = int(snap[0]) if snap else None
        if ml_visits is not None:
            checks.append(_check(f"visitas[{mlb}]", ml_visits, app_visits))

        # Estoque e preco atuais (ML /items) vs ultimo snapshot
        try:
            item = await client.get_item(mlb)
            ml_stock = int(item.get("available_quantity", 0) or 0)
            ml_price = round(float(item.get("price", 0) or 0), 2)
            app_stock = int(snap[1]) if snap else None
            app_price = round(float(snap[2]), 2) if snap else None
            checks.append(_check(f"estoque[{mlb}]", ml_stock, app_stock))
            checks.append(_check(f"preco[{mlb}]", ml_price, app_price, tol=0.01))
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
