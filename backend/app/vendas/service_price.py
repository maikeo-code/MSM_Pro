"""
Preço, margem e promoções de anúncios.
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.financeiro.service import calcular_margem
from app.produtos.models import Product
from app.vendas.models import Listing, ListingSnapshot
from app.vendas.schemas import MargemResult, SimulatePriceOut, MargemSimulada


async def get_margem(
    db: AsyncSession, mlb_id: str, user_id: UUID, preco: Decimal
) -> MargemResult:
    """Calcula margem para um anúncio com preço informado."""
    from app.vendas.service import get_listing

    listing = await get_listing(db, mlb_id, user_id)

    # Busca custo do produto
    prod_result = await db.execute(
        select(Product).where(Product.id == listing.product_id)
    )
    product = prod_result.scalar_one_or_none()
    custo = product.cost if product else Decimal("0")

    resultado = calcular_margem(
        preco=preco,
        custo=custo,
        listing_type=listing.listing_type,
    )

    return MargemResult(
        preco=preco,
        custo_sku=custo,
        listing_type=listing.listing_type,
        **resultado,
    )


async def update_listing_price(
    db: AsyncSession,
    mlb_id: str,
    user_id: UUID,
    new_price: Decimal,
) -> dict:
    """Altera preço de um anúncio (será integrado com ML API)."""
    from app.vendas.service import get_listing

    listing = await get_listing(db, mlb_id, user_id)

    listing.price = new_price
    await db.flush()
    await db.refresh(listing)

    return {
        "mlb_id": listing.mlb_id,
        "new_price": float(new_price),
        "updated_at": listing.updated_at.isoformat(),
    }


async def apply_price_suggestion(
    db: AsyncSession,
    mlb_id: str,
    user_id: UUID,
    new_price: float,
    justification: str,
) -> dict:
    """
    Aplica sugestão de preço: altera na API do ML e salva log no banco.
    Respeita regra original_price/sale_price:
    - PUT /items/{id} com {"price": new_price} altera o preço base.
    - Se houver promoção ativa (original_price != null), alterar preço pode desativar a promoção.
    - O response da API retorna o item atualizado com price, original_price e sale_price.
    """
    from app.auth.models import MLAccount
    from app.auth.service import refresh_ml_token
    from app.mercadolivre.client import MLClient, MLClientError
    from app.vendas.models import PriceChangeLog
    from app.vendas.service import get_listing

    listing = await get_listing(db, mlb_id, user_id)
    old_price = float(listing.price)

    # Buscar token ML da conta associada ao listing
    acc_result = await db.execute(
        select(MLAccount).where(MLAccount.id == listing.ml_account_id)
    )
    ml_account = acc_result.scalar_one_or_none()
    if not ml_account or not ml_account.access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conta ML não encontrada ou sem token válido",
        )

    # Auto-refresh do token se expirado
    if ml_account.token_expires_at and ml_account.token_expires_at <= datetime.now(timezone.utc):
        try:
            token_data = await refresh_ml_token(ml_account)
            ml_account.access_token = token_data["access_token"]
            ml_account.refresh_token = token_data.get("refresh_token", ml_account.refresh_token)
            ml_account.token_expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=token_data.get("expires_in", 21600)
            )
            await db.flush()
        except Exception as e:
            logger.error("Token refresh failed for account %s: %s", ml_account.id, e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Falha ao renovar token ML. Tente novamente.",
            )

    # Verificar se tem promocao ativa ANTES de alterar preco
    promo_warning = None
    has_active_promotion = False
    try:
        async with MLClient(ml_account.access_token) as promo_client:
            promotions = await promo_client.get_item_promotions(listing.mlb_id)
            active_promos = [
                p
                for p in promotions
                if p.get("status") in ("active", "started")
            ]
            if active_promos:
                has_active_promotion = True
                promo_warning = (
                    f"Atencao: {len(active_promos)} promocao(oes) ativa(s) no anuncio. "
                    "A alteracao de preco pode desativar a promocao."
                )
                logger.info(
                    "Promo check for %s: %d active promotions detected.",
                    mlb_id,
                    len(active_promos),
                )
    except Exception as promo_exc:
        logger.debug(
            "Nao foi possivel verificar promocoes para %s: %s",
            mlb_id,
            promo_exc,
        )

    # Chamar API ML para alterar preço
    ml_api_success = False
    ml_api_response_raw = None
    ml_price_returned = None
    ml_original_price = None
    ml_sale_price = None
    error_msg = None

    try:
        async with MLClient(ml_account.access_token) as client:
            ml_response = await client.update_item_price(listing.mlb_id, new_price)
            ml_api_response_raw = json.dumps(ml_response, default=str)[:5000]
            ml_api_success = True

            # Extrair preços retornados pela API
            ml_price_returned = ml_response.get("price")
            ml_original_price = ml_response.get("original_price")
            # sale_price pode ser objeto ou null
            sp = ml_response.get("sale_price")
            if isinstance(sp, dict):
                ml_sale_price = sp.get("amount")
            elif isinstance(sp, (int, float)):
                ml_sale_price = sp

    except MLClientError as e:
        error_msg = str(e)
        ml_api_response_raw = error_msg[:5000]

    # Atualizar listing local se API respondeu OK
    if ml_api_success:
        listing.price = Decimal(str(new_price))
        if ml_original_price is not None:
            listing.original_price = Decimal(str(ml_original_price))
        else:
            listing.original_price = None
        if ml_sale_price is not None:
            listing.sale_price = Decimal(str(ml_sale_price))
        else:
            listing.sale_price = None

    # Salvar log de ação no PostgreSQL
    log = PriceChangeLog(
        listing_id=listing.id,
        user_id=user_id,
        mlb_id=listing.mlb_id,
        old_price=Decimal(str(old_price)),
        new_price=Decimal(str(new_price)),
        justification=justification,
        source="suggestion_apply",
        ml_api_response=ml_api_response_raw,
        success=ml_api_success,
        error_message=error_msg,
    )
    db.add(log)
    await db.flush()
    await db.refresh(log)

    if not ml_api_success:
        logger.error("ML API rejected price update for %s: %s", mlb_id, error_msg)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="A API do Mercado Livre recusou a alteração de preço. Verifique os dados e tente novamente.",
        )

    return {
        "mlb_id": listing.mlb_id,
        "old_price": old_price,
        "new_price": new_price,
        "justification": justification,
        "ml_api_success": ml_api_success,
        "ml_api_price_returned": ml_price_returned,
        "original_price": ml_original_price,
        "sale_price": ml_sale_price,
        "log_id": str(log.id),
        "applied_at": log.created_at.isoformat(),
        "has_active_promotion": has_active_promotion,
        "promo_warning": promo_warning,
    }


async def simulate_price(
    db: AsyncSession,
    mlb_id: str,
    user_id: UUID,
    target_price: float,
) -> SimulatePriceOut:
    """
    Simula o impacto de alterar o preço de um anúncio.

    1. Busca snapshots dos últimos 90 dias
    2. Calcula elasticidade agrupando por faixa de preço → média vendas/dia por faixa
    3. Interpola vendas estimadas no target_price via regressão linear simples
    4. Retorna receita e margem estimadas vs atuais
    """
    from app.vendas.service import get_listing

    listing = await get_listing(db, mlb_id, user_id)

    # Buscar snapshots dos últimos 90 dias
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    snaps_result = await db.execute(
        select(ListingSnapshot)
        .where(
            ListingSnapshot.listing_id == listing.id,
            ListingSnapshot.captured_at >= cutoff,
        )
        .order_by(ListingSnapshot.captured_at.asc())
    )
    snapshots = snaps_result.scalars().all()

    current_price = float(listing.price)
    MIN_SNAPSHOTS = 7
    is_estimated = len(snapshots) < MIN_SNAPSHOTS

    # Busca custo do SKU
    product = None
    if listing.product_id:
        prod_result = await db.execute(
            select(Product).where(Product.id == listing.product_id)
        )
        product = prod_result.scalar_one_or_none()
    custo = Decimal(str(product.cost)) if product and product.cost else Decimal("0")
    frete = listing.avg_shipping_cost or Decimal("0")
    sale_fee_pct = listing.sale_fee_pct if listing.sale_fee_pct and float(listing.sale_fee_pct) > 0 else None

    def _calcular_margem_simples(preco: float) -> MargemSimulada | None:
        """Retorna margem calculada para um preço, ou None se custo não disponível."""
        resultado = calcular_margem(
            preco=Decimal(str(preco)),
            custo=custo,
            listing_type=listing.listing_type,
            frete=Decimal(str(frete)),
            sale_fee_pct=sale_fee_pct,
        )
        return MargemSimulada(
            taxa_ml_pct=float(resultado["taxa_ml_pct"]),
            taxa_ml_valor=float(resultado["taxa_ml_valor"]),
            frete=float(resultado["frete"]),
            margem_bruta=float(resultado["margem_bruta"]),
            margem_pct=float(resultado["margem_pct"]),
            lucro=float(resultado["lucro"]),
        )

    # Caso sem dados suficientes: retornar com is_estimated=True e sem interpolação
    if is_estimated:
        # Usa vendas médias disponíveis (mesmo que poucas)
        if snapshots:
            avg_sales = sum(s.sales_today or 0 for s in snapshots) / len(snapshots)
        else:
            avg_sales = 0.0

        return SimulatePriceOut(
            target_price=target_price,
            current_price=current_price,
            estimated_sales_per_day=round(avg_sales, 2),
            current_sales_per_day=round(avg_sales, 2),
            estimated_monthly_revenue=round(target_price * avg_sales * 30, 2),
            current_monthly_revenue=round(current_price * avg_sales * 30, 2),
            estimated_margin=_calcular_margem_simples(target_price),
            current_margin=_calcular_margem_simples(current_price),
            recommendation=(
                f"Dados insuficientes para calcular elasticidade com precisão "
                f"({len(snapshots)} snapshots de {MIN_SNAPSHOTS} necessários). "
                "Os valores são estimativas baseadas na média atual."
            ),
            is_estimated=True,
            data_points=len(snapshots),
            message=f"Necessário pelo menos {MIN_SNAPSHOTS} dias de histórico para simulação precisa.",
        )

    # ── Agrupamento por faixa de preço (bandas de 5%) ──────────────────────────
    # Encontrar amplitude de preços
    prices = [float(s.price) for s in snapshots if s.price and float(s.price) > 0]
    if not prices:
        prices = [current_price]

    min_price = min(prices)
    max_price = max(prices)
    price_range = max_price - min_price

    # Se variação de preço muito pequena, usar bandas fixas de R$10
    band_size = max(price_range * 0.05, 10.0)

    # Agrupa snapshots por faixa
    bands: dict[float, list[float]] = {}
    for snap in snapshots:
        p = float(snap.price) if snap.price else current_price
        band_key = round((p // band_size) * band_size, 2)
        if band_key not in bands:
            bands[band_key] = []
        bands[band_key].append(snap.sales_today or 0)

    # Calcula média de vendas por banda
    band_stats: list[tuple[float, float]] = [
        (band_key, sum(sales) / len(sales))
        for band_key, sales in bands.items()
    ]
    band_stats.sort(key=lambda x: x[0])

    # Vendas atuais (média dos últimos 7 dias de snapshot)
    recent = sorted(snapshots, key=lambda s: s.captured_at, reverse=True)[:7]
    current_sales_per_day = sum(s.sales_today or 0 for s in recent) / len(recent) if recent else 0.0

    # ── Interpolação linear para target_price ──────────────────────────────────
    estimated_sales_per_day: float

    if len(band_stats) == 1:
        # Só uma banda: sem variação de preço → assumir vendas iguais
        estimated_sales_per_day = band_stats[0][1]
    else:
        # Interpolar/extrapolar entre bandas mais próximas do target_price
        # Ordenado por preço crescente
        target = target_price

        # Achar as bandas que enquadram o target
        lower = None
        upper = None
        for bp, bsales in band_stats:
            if bp <= target:
                lower = (bp, bsales)
            else:
                upper = (bp, bsales)
                break

        if lower is None:
            # target abaixo de todas as bandas: extrapolar pela inclinação das duas primeiras
            estimated_sales_per_day = band_stats[0][1]
        elif upper is None:
            # target acima de todas as bandas: extrapolar pela inclinação das duas últimas
            estimated_sales_per_day = band_stats[-1][1]
        else:
            # Interpolação linear entre lower e upper
            lp, ls = lower
            up, us = upper
            if up != lp:
                t = (target - lp) / (up - lp)
                estimated_sales_per_day = ls + t * (us - ls)
            else:
                estimated_sales_per_day = ls

    # Garantir que não seja negativo
    estimated_sales_per_day = max(0.0, round(estimated_sales_per_day, 2))
    current_sales_per_day = round(current_sales_per_day, 2)

    estimated_monthly_revenue = round(target_price * estimated_sales_per_day * 30, 2)
    current_monthly_revenue = round(current_price * current_sales_per_day * 30, 2)

    # ── Recomendação textual ───────────────────────────────────────────────────
    sales_diff_pct = (
        round(((estimated_sales_per_day - current_sales_per_day) / current_sales_per_day) * 100, 1)
        if current_sales_per_day > 0
        else 0.0
    )
    rev_diff_pct = (
        round(((estimated_monthly_revenue - current_monthly_revenue) / current_monthly_revenue) * 100, 1)
        if current_monthly_revenue > 0
        else 0.0
    )

    direction = "Reduzir" if target_price < current_price else "Aumentar"
    sales_dir = "aumentar" if sales_diff_pct > 0 else "reduzir"
    rev_dir = "aumentar" if rev_diff_pct > 0 else "reduzir"

    recommendation = (
        f"{direction} preço de R${current_price:.2f} para R${target_price:.2f} "
        f"pode {sales_dir} vendas em {abs(sales_diff_pct):.1f}% "
        f"e {rev_dir} receita mensal em {abs(rev_diff_pct):.1f}%."
    )

    return SimulatePriceOut(
        target_price=target_price,
        current_price=current_price,
        estimated_sales_per_day=estimated_sales_per_day,
        current_sales_per_day=current_sales_per_day,
        estimated_monthly_revenue=estimated_monthly_revenue,
        current_monthly_revenue=current_monthly_revenue,
        estimated_margin=_calcular_margem_simples(target_price),
        current_margin=_calcular_margem_simples(current_price),
        recommendation=recommendation,
        is_estimated=False,
        data_points=len(snapshots),
    )


async def create_or_update_promotion(
    db: AsyncSession,
    mlb_id: str,
    user_id: UUID,
    discount_pct: float,
    start_date,  # datetime
    end_date,    # datetime
    promotion_id: str | None = None,
) -> dict:
    """Cria ou renova promoção (será integrado com ML API)."""
    from app.vendas.service import get_listing

    listing = await get_listing(db, mlb_id, user_id)

    # Calcula preço final
    original_price = float(listing.price)
    final_price = original_price * (1 - discount_pct / 100)

    return {
        "id": promotion_id or "new_promo",
        "type": "desconto_direto",
        "discount_pct": discount_pct,
        "original_price": original_price,
        "final_price": final_price,
        "start_date": start_date.isoformat() if hasattr(start_date, "isoformat") else str(start_date),
        "end_date": end_date.isoformat() if hasattr(end_date, "isoformat") else str(end_date),
        "status": "active" if promotion_id else "pending",
    }


# ─── Repricing Rules CRUD ─────────────────────────────────────────────────────


async def list_repricing_rules(
    db: AsyncSession,
    user_id: UUID,
    listing_id: UUID | None = None,
    active_only: bool = False,
) -> list[dict]:
    """
    Lista regras de reprecificação do usuário.

    Parâmetros:
    - listing_id: filtrar por anúncio específico (opcional)
    - active_only: retornar apenas regras ativas (padrão: False = todas)
    """
    from sqlalchemy.orm import selectinload

    from app.vendas.models import RepricingRule

    conditions = [RepricingRule.user_id == user_id]
    if listing_id is not None:
        conditions.append(RepricingRule.listing_id == listing_id)
    if active_only:
        conditions.append(RepricingRule.is_active == True)  # noqa: E712

    result = await db.execute(
        select(RepricingRule)
        .options(selectinload(RepricingRule.listing))
        .where(*conditions)
        .order_by(RepricingRule.created_at.desc())
    )
    rules = result.scalars().all()

    return [_rule_to_dict(r) for r in rules]


async def create_repricing_rule(
    db: AsyncSession,
    user_id: UUID,
    payload,  # RepricingRuleCreate
) -> dict:
    """
    Cria nova regra de reprecificação para um anúncio.

    Valida:
    - O listing pertence ao usuário
    - Não existe regra do mesmo tipo já ativa para esse listing
    """
    from app.vendas.models import RepricingRule

    # Verificar ownership do listing
    listing_result = await db.execute(
        select(Listing).where(
            Listing.id == payload.listing_id,
            Listing.user_id == user_id,
        )
    )
    listing = listing_result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anúncio não encontrado ou não pertence ao usuário",
        )

    # Checar duplicidade: mesmo tipo ativo para o mesmo listing
    existing_result = await db.execute(
        select(RepricingRule).where(
            RepricingRule.listing_id == payload.listing_id,
            RepricingRule.rule_type == payload.rule_type,
            RepricingRule.is_active == True,  # noqa: E712
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Já existe uma regra ativa do tipo '{payload.rule_type}' para este anúncio. "
                "Desative a regra existente antes de criar uma nova do mesmo tipo."
            ),
        )

    rule = RepricingRule(
        user_id=user_id,
        listing_id=payload.listing_id,
        rule_type=payload.rule_type,
        value=payload.value,
        min_price=payload.min_price,
        max_price=payload.max_price,
        is_active=payload.is_active,
    )
    db.add(rule)
    await db.flush()
    await db.refresh(rule)

    return _rule_to_dict(rule, listing=listing)


async def update_repricing_rule(
    db: AsyncSession,
    user_id: UUID,
    rule_id: UUID,
    payload,  # RepricingRuleUpdate
) -> dict:
    """
    Atualiza regra de reprecificação.

    Usa model_dump(exclude_unset=True) para aplicar apenas os campos
    explicitamente enviados pelo cliente — incluindo None explícito para
    limpar campos opcionais como min_price e max_price.
    Verifica ownership via user_id.
    """
    from app.vendas.models import RepricingRule

    result = await db.execute(
        select(RepricingRule).where(
            RepricingRule.id == rule_id,
            RepricingRule.user_id == user_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Regra de reprecificação não encontrada",
        )

    # exclude_unset=True garante que campos não enviados não sobrescrevem nada.
    # Campos enviados explicitamente como null (ex: min_price=null) são
    # incluídos e aplicados, permitindo limpar valores opcionais.
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(rule, field, value)

    await db.flush()
    await db.refresh(rule)

    return _rule_to_dict(rule)


async def delete_repricing_rule(
    db: AsyncSession,
    user_id: UUID,
    rule_id: UUID,
) -> dict:
    """
    Desativa (soft delete) uma regra de reprecificação.

    Não remove o registro do banco para manter histórico de auditoria.
    Para remoção definitiva, use delete_repricing_rule_hard.
    """
    from app.vendas.models import RepricingRule

    result = await db.execute(
        select(RepricingRule).where(
            RepricingRule.id == rule_id,
            RepricingRule.user_id == user_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Regra de reprecificação não encontrada",
        )

    rule.is_active = False
    await db.flush()

    return {"id": str(rule_id), "is_active": False, "message": "Regra desativada com sucesso"}


def _rule_to_dict(rule, listing=None) -> dict:
    """Serializa RepricingRule para dict compatível com RepricingRuleOut."""
    listing_obj = listing or getattr(rule, "listing", None)
    return {
        "id": rule.id,
        "user_id": rule.user_id,
        "listing_id": rule.listing_id,
        "rule_type": rule.rule_type,
        "value": rule.value,
        "min_price": rule.min_price,
        "max_price": rule.max_price,
        "is_active": rule.is_active,
        "last_applied_at": rule.last_applied_at,
        "last_applied_price": rule.last_applied_price,
        "created_at": rule.created_at,
        "mlb_id": listing_obj.mlb_id if listing_obj else None,
        "listing_title": listing_obj.title if listing_obj else None,
    }
