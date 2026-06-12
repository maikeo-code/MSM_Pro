"""Serviço da aba Vendas (MT) — replica a cadeia de endpoints do Mercado Turbo.

Mecanismo (provado em mercadoturbo_research/03-MECANISMO-ENDPOINTS.md):
  orders/search  →  tarifa (marketplace_fee)  →  frete (/shipments/{id}/costs senders.cost)
  →  custo (cadastro de Produtos por SKU)  →  imposto (tax-config)  →  fórmula do Turbo.

Fórmula: lucro = pago − frete − tarifa − custo − imposto ; margem% = lucro / pago.

Reutiliza o OAuth do Mercado Livre que o MSM_Pro já gerencia (MLClient + refresh on-401).
NÃO usa a agregação antiga de vendas (a da margem inflada) — esta é a cadeia correta.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import MLAccount
from app.mercadolivre.client import MLClient
from app.produtos.models import Product
from app.vendas_mt.schemas import VendaMTOut

logger = logging.getLogger(__name__)

_STATUS_LABEL = {
    "ready_to_ship": "Aguardando Envio",
    "shipped": "Despachado",
    "delivered": "Entregue",
    "pending": "Pgto. Pendente",
    "handling": "Em Preparação",
    "cancelled": "Cancelado",
    "to_be_agreed": "A combinar",
    "not_specified": "Não especificado",
}


async def _resolver_conta(
    db: AsyncSession, user_id: UUID, ml_account_id: UUID | None
) -> MLAccount | None:
    """Conta ML ativa do usuário (a específica, ou a primeira ativa)."""
    stmt = select(MLAccount).where(
        MLAccount.user_id == user_id,
        MLAccount.is_active == True,  # noqa: E712
    )
    if ml_account_id is not None:
        stmt = stmt.where(MLAccount.id == ml_account_id)
    result = await db.execute(stmt)
    contas = list(result.scalars().all())
    return contas[0] if contas else None


async def _mapa_custos(db: AsyncSession, user_id: UUID) -> dict[str, Decimal]:
    """SKU → custo (cadastro de Produtos do usuário)."""
    result = await db.execute(select(Product).where(Product.user_id == user_id))
    return {p.sku: p.cost for p in result.scalars().all() if p.sku}


async def _aliquota_imposto(db: AsyncSession, user_id: UUID) -> float:
    """Alíquota efetiva de imposto (tax-config). 0 se não configurado."""
    from app.financeiro import service as fin_service

    try:
        cfg = await fin_service.get_tax_config(db, user_id)
        if cfg and cfg.get("aliquota_efetiva") is not None:
            return float(cfg["aliquota_efetiva"])
    except Exception as e:  # pragma: no cover - defensivo
        logger.warning("tax-config indisponível: %s", e)
    return 0.0


async def _frete_real(client: MLClient, shipment_id) -> float:
    """Custo real do frete do vendedor: GET /shipments/{id}/costs → senders[].cost."""
    if not shipment_id:
        return 0.0
    try:
        costs = await client._request("GET", f"/shipments/{shipment_id}/costs")
        senders = costs.get("senders") or []
        return sum(float(s.get("cost") or 0) for s in senders)
    except Exception as e:
        logger.debug("frete indisponível p/ shipment %s: %s", shipment_id, e)
        return 0.0


async def _montar_venda(
    client: MLClient, order: dict, custos: dict[str, Decimal], aliquota: float
) -> VendaMTOut:
    """Monta uma venda com a fórmula EXATA do Mercado Turbo (validada por diff 20/20 pedidos):

    pago        = paid_amount (o que o comprador pagou, já com cupom/frete comprador)
    frete       = custo do vendedor (shipments/costs) + frete pago pelo comprador
    tarifa      = soma dos order_items[].sale_fee
    lucroBruto  = pago - frete - tarifa
    custo       = Product.cost * qtd  (só p/ SKU cadastrado)
    imposto     = total_amount * aliquota  (só p/ SKU cadastrado — como no Turbo)
    lucro       = lucroBruto - custo - imposto
    margem%     = lucro / total_amount * 100
    """
    itens = order.get("order_items") or [{}]
    item0 = itens[0] if itens else {}
    prod = item0.get("item") or {}
    sku = prod.get("seller_sku")
    qtd = item0.get("quantity") or 1

    total = float(order.get("total_amount") or 0)  # valor dos produtos (base imposto/margem)
    pago = float(order.get("paid_amount") or total)  # o que o comprador pagou
    frete_comprador = sum(
        float(p.get("shipping_cost") or 0) for p in (order.get("payments") or [])
    )
    seller_frete = await _frete_real(client, (order.get("shipping") or {}).get("id"))
    frete = seller_frete + frete_comprador  # linha "Frete" do Turbo

    # Tarifa de Venda ML = soma dos sale_fee dos order_items (mesma fonte do sync de Pedidos).
    tarifa = sum(float(oi.get("sale_fee") or 0) for oi in itens)

    configurado = bool(sku and sku in custos)  # SKU tem Custo & Imposto cadastrado
    custo = float(custos[sku]) * qtd if configurado else None
    imposto = total * aliquota if (configurado and aliquota) else None

    lucro_bruto = pago - frete - tarifa
    lucro = lucro_bruto - (custo or 0.0) - (imposto or 0.0)
    margem = (lucro / total * 100) if total else None

    dt = order.get("date_created")
    status = (order.get("shipping") or {}).get("status") or order.get("status")

    return VendaMTOut(
        venda=str(order.get("id")),
        mlb=prod.get("id"),
        sku=sku,
        titulo=prod.get("title") or "(sem título)",
        data=dt,
        status=_STATUS_LABEL.get(status, status),
        total=total,
        pago=pago,
        produtos=total,
        tarifaML=-tarifa if tarifa else None,
        frete=-frete if frete else None,
        lucroBruto=lucro_bruto,
        custoProduto=-custo if custo is not None else None,
        imposto=-imposto if imposto is not None else None,
        receitaLiquida=lucro_bruto,
        lucro=lucro,
        margem=margem,
        temCusto=custo is not None,
    )


async def listar_vendas_mt(
    db: AsyncSession,
    user_id: UUID,
    ml_account_id: UUID | None,
    days: int,
    limit: int,
) -> tuple[MLAccount | None, list[VendaMTOut]]:
    """Lista as vendas via cadeia ML ao vivo (igual ao Turbo)."""
    conta = await _resolver_conta(db, user_id, ml_account_id)
    if conta is None or not conta.access_token:
        return conta, []

    custos = await _mapa_custos(db, user_id)
    aliquota = await _aliquota_imposto(db, user_id)
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%S.000-00:00"
    )

    vendas: list[VendaMTOut] = []
    async with MLClient(conta.access_token, ml_account_id=str(conta.id)) as client:
        data = await client.get_orders(conta.ml_user_id, date_from, limit=limit)
        orders = data.get("results", []) if isinstance(data, dict) else []
        for order in orders:
            try:
                vendas.append(await _montar_venda(client, order, custos, aliquota))
            except Exception as e:  # pragma: no cover - resiliência por venda
                logger.warning("falha ao montar venda %s: %s", order.get("id"), e)
    return conta, vendas
