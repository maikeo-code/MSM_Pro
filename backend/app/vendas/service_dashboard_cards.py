import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import MLAccount
from app.mercadolivre.client import MLClient
from app.vendas.models import Order

BRT = timezone(timedelta(hours=-3))


async def get_extra_cards(
    db: AsyncSession, user_id: UUID, ml_account_id: UUID | None = None
) -> dict:
    """Consolida metricas extras por conta ML consultando a API + banco local."""
    query = select(MLAccount).where(
        MLAccount.user_id == user_id, MLAccount.is_active == True
    )
    if ml_account_id:
        query = query.where(MLAccount.id == ml_account_id)

    result = await db.execute(query)
    accounts = list(result.scalars().all())

    if not accounts:
        return _empty_response()

    accounts_data = await asyncio.gather(
        *(_fetch_account_data(db, acc) for acc in accounts)
    )

    totals = _aggregate_totals(accounts_data)

    return {
        "accounts": accounts_data,
        **totals,
    }


async def _fetch_account_data(db: AsyncSession, acc: MLAccount) -> dict:
    """Busca todos os dados de uma conta em paralelo."""
    reputacao = _empty_reputacao()
    perguntas = 0
    mensagens_nao_lidas = 0
    claims = 0
    mediacoes = 0
    saldo_mp = 0.0
    saldo_liberar = 0.0
    full_stock = _empty_full_stock()

    try:
        async with MLClient(access_token=acc.access_token, ml_account_id=acc.id) as client:
            (
                res_rep,
                res_perguntas,
                res_claims,
                res_mediacoes,
                res_mensagens,
                res_saldo,
                res_full,
            ) = await asyncio.gather(
                client.get_seller_reputation(acc.ml_user_id),
                client.get_my_unanswered_questions(),
                client.get_my_open_claims(),
                client.get_my_open_mediations(),
                client.get_unread_messages_count(acc.ml_user_id),
                client.get_mp_balance(acc.ml_user_id),
                client.get_full_inventory_summary(acc.ml_user_id),
                return_exceptions=True,
            )

            if not isinstance(res_rep, Exception) and isinstance(res_rep, dict):
                reputacao = _parse_reputacao(res_rep)

            if not isinstance(res_perguntas, Exception) and isinstance(res_perguntas, dict):
                perguntas = int(res_perguntas.get("total", 0) or 0)

            if not isinstance(res_claims, Exception) and isinstance(res_claims, dict):
                claims = int(res_claims.get("paging", {}).get("total", 0) or 0)

            if not isinstance(res_mediacoes, Exception) and isinstance(res_mediacoes, dict):
                mediacoes = int(res_mediacoes.get("paging", {}).get("total", 0) or 0)

            if not isinstance(res_mensagens, Exception):
                mensagens_nao_lidas = int(res_mensagens or 0)

            if not isinstance(res_saldo, Exception) and isinstance(res_saldo, dict):
                saldo_mp = float(res_saldo.get("total_amount", 0.0) or 0.0)
                saldo_liberar = float(res_saldo.get("unavailable_balance", 0.0) or 0.0)

            if not isinstance(res_full, Exception) and isinstance(res_full, dict):
                full_stock = _parse_full_stock(res_full)
    except Exception:
        pass

    vendas_7d = await _sales_sparkline_7d(db, acc.id)

    return {
        "ml_account_id": str(acc.id),
        "nickname": acc.nickname or "",
        "ml_user_id": acc.ml_user_id,
        "reputacao": reputacao,
        "perguntas": perguntas,
        "mensagens_nao_lidas": mensagens_nao_lidas,
        "claims": claims,
        "mediacoes": mediacoes,
        "saldo_mp": saldo_mp,
        "saldo_liberar": saldo_liberar,
        "full_stock": full_stock,
        "vendas_7d": vendas_7d,
    }


def _parse_reputacao(user_obj: dict) -> dict:
    rep = user_obj.get("seller_reputation") or {}
    metrics = rep.get("metrics") or {}

    def _rate(key: str) -> float:
        node = metrics.get(key) or {}
        if isinstance(node, dict):
            val = node.get("rate", 0)
        else:
            val = node
        try:
            return float(val or 0.0)
        except (TypeError, ValueError):
            return 0.0

    return {
        "level_id": rep.get("level_id") or "unknown",
        "power_seller_status": rep.get("power_seller_status"),
        "claims_rate": _rate("claims"),
        "cancellations_rate": _rate("cancellations"),
        "delayed_handling_time_rate": _rate("delayed_handling_time"),
    }


def _empty_reputacao() -> dict:
    return {
        "level_id": "unknown",
        "power_seller_status": None,
        "claims_rate": 0.0,
        "cancellations_rate": 0.0,
        "delayed_handling_time_rate": 0.0,
    }


def _parse_full_stock(data: dict) -> dict:
    """Normaliza resposta do resumo de Full em small_medium/large_xlarge."""
    small_used = 0
    small_total = 0
    large_used = 0
    large_total = 0

    buckets = data.get("buckets") or data.get("size_buckets") or data.get("results") or []
    if isinstance(buckets, list):
        for b in buckets:
            if not isinstance(b, dict):
                continue
            name = (b.get("bucket") or b.get("size") or b.get("name") or "").upper()
            used = int(b.get("used") or b.get("current") or b.get("in_stock") or 0)
            total = int(b.get("total") or b.get("limit") or b.get("capacity") or 0)
            if "SMALL" in name or "MEDIUM" in name:
                small_used += used
                small_total = max(small_total, total)
            elif "LARGE" in name or "EXTRA" in name:
                large_used += used
                large_total = max(large_total, total)

    for key, target in (
        ("SMALL_MEDIUM", "small"),
        ("small_medium", "small"),
        ("LARGE_EXTRA_LARGE", "large"),
        ("large_extra_large", "large"),
    ):
        node = data.get(key)
        if isinstance(node, dict):
            used = int(node.get("used") or node.get("current") or 0)
            total = int(node.get("total") or node.get("limit") or 0)
            if target == "small":
                small_used = max(small_used, used)
                small_total = max(small_total, total)
            else:
                large_used = max(large_used, used)
                large_total = max(large_total, total)

    return {
        "small_medium_used": small_used,
        "small_medium_total": small_total,
        "large_xlarge_used": large_used,
        "large_xlarge_total": large_total,
    }


def _empty_full_stock() -> dict:
    return {
        "small_medium_used": 0,
        "small_medium_total": 0,
        "large_xlarge_used": 0,
        "large_xlarge_total": 0,
    }


async def _sales_sparkline_7d(db: AsyncSession, ml_account_id: UUID) -> list[dict]:
    """Retorna lista de 7 dias com valor de vendas (net_amount) em BRT."""
    today = datetime.now(BRT).date()
    start = today - timedelta(days=6)

    start_dt = datetime.combine(start, datetime.min.time()).replace(tzinfo=BRT)
    end_dt = datetime.combine(today, datetime.max.time()).replace(tzinfo=BRT)

    stmt = (
        select(
            func.date(func.timezone("America/Sao_Paulo", Order.order_date)).label("dia"),
            func.coalesce(func.sum(Order.net_amount), 0).label("valor"),
        )
        .where(
            Order.ml_account_id == ml_account_id,
            Order.order_date >= start_dt,
            Order.order_date <= end_dt,
            Order.payment_status.notin_(["cancelled", "refunded", "rejected"]),
        )
        .group_by("dia")
    )
    rows = (await db.execute(stmt)).all()
    by_day = {r.dia.isoformat() if r.dia else "": float(r.valor or 0) for r in rows}

    result = []
    for i in range(7):
        d = start + timedelta(days=i)
        result.append({"date": d.isoformat(), "valor": by_day.get(d.isoformat(), 0.0)})
    return result


def _aggregate_totals(accounts_data: list[dict]) -> dict:
    """Soma metricas para retrocompatibilidade com shape antigo."""
    reputacao_nivel = "unknown"
    perguntas = 0
    claims = 0
    mediacoes = 0
    mensagens = 0
    saldo_mp = 0.0
    saldo_liberar = 0.0

    for acc in accounts_data:
        rep_level = acc.get("reputacao", {}).get("level_id")
        if rep_level and rep_level != "unknown":
            reputacao_nivel = rep_level
        perguntas += acc.get("perguntas", 0)
        claims += acc.get("claims", 0)
        mediacoes += acc.get("mediacoes", 0)
        mensagens += acc.get("mensagens_nao_lidas", 0)
        saldo_mp += acc.get("saldo_mp", 0.0)
        saldo_liberar += acc.get("saldo_liberar", 0.0)

    return {
        "reputacao": reputacao_nivel,
        "perguntas": perguntas,
        "claims": claims,
        "mediacoes": mediacoes,
        "mensagens_nao_lidas": mensagens,
        "saldo_mp": saldo_mp,
        "saldo_liberar": saldo_liberar,
    }


def _empty_response() -> dict:
    return {
        "accounts": [],
        "reputacao": "unknown",
        "perguntas": 0,
        "claims": 0,
        "mediacoes": 0,
        "mensagens_nao_lidas": 0,
        "saldo_mp": 0.0,
        "saldo_liberar": 0.0,
    }
