"""
Preço, margem e promoções de anúncios.
"""
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.financeiro.service import calcular_margem
from app.produtos.models import Product
from app.vendas.models import Listing
from app.vendas.schemas import MargemResult


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
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Falha ao renovar token ML: {e}",
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
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"API ML rejeitou alteração: {error_msg}",
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
    }


async def create_or_update_promotion(
    db: AsyncSession,
    mlb_id: str,
    user_id: UUID,
    discount_pct: float,
    start_date: str,
    end_date: str,
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
        "start_date": start_date,
        "end_date": end_date,
        "status": "active" if promotion_id else "pending",
    }
