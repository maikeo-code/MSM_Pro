"""
Testes para backend/app/vendas/service_price.py

Cobre:
- calcular_taxa_ml: pura
- calcular_margem: pura
- get_margem: DB real (query simples)
- update_listing_price: DB real
- apply_price_suggestion: validação (new_price >= base)
- simulate_price: DB real com snapshots
- list_repricing_rules: DB real
- create_repricing_rule: DB real
- delete_repricing_rule: DB real
- _rule_to_dict: pura

Cobertura alvo: 10% → ~35%+
"""
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest
import pytest_asyncio

from app.auth.models import MLAccount, User
from app.vendas.models import Listing, ListingSnapshot, RepricingRule


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _uid():
    return uuid.uuid4()


def _make_user(email: str = None) -> User:
    return User(
        id=_uid(),
        email=email or f"u_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="hashed",
        is_active=True,
    )


def _make_ml_account(user_id: uuid.UUID) -> MLAccount:
    return MLAccount(
        id=_uid(),
        user_id=user_id,
        ml_user_id="seller123",
        nickname="test_seller",
        is_active=True,
    )


def _make_listing(
    user_id: uuid.UUID,
    ml_account_id: uuid.UUID,
    mlb_id: str = None,
    price: Decimal = Decimal("200.00"),
    listing_type: str = "classico",
    original_price: Decimal = None,
) -> Listing:
    return Listing(
        id=_uid(),
        user_id=user_id,
        ml_account_id=ml_account_id,
        mlb_id=mlb_id or f"MLB{uuid.uuid4().int % 1_000_000_000:09d}",
        title="Produto Teste",
        listing_type=listing_type,
        price=price,
        original_price=original_price,
        status="active",
    )


def _make_snapshot(
    listing_id: uuid.UUID,
    price: Decimal = Decimal("200.00"),
    visits: int = 20,
    sales_today: int = 3,
    stock: int = 50,
    captured_at: datetime = None,
) -> ListingSnapshot:
    return ListingSnapshot(
        id=_uid(),
        listing_id=listing_id,
        price=price,
        visits=visits,
        sales_today=sales_today,
        questions=0,
        stock=stock,
        captured_at=captured_at or datetime.utcnow(),
    )


def _make_repricing_rule(
    user_id: uuid.UUID,
    listing_id: uuid.UUID,
    rule_type: str = "FIXED_MARKUP",
    value: Decimal = Decimal("1.40"),
    is_active: bool = True,
) -> RepricingRule:
    return RepricingRule(
        id=_uid(),
        user_id=user_id,
        listing_id=listing_id,
        rule_type=rule_type,
        value=value,
        min_price=Decimal("100.00"),
        max_price=Decimal("500.00"),
        is_active=is_active,
    )


# ─── Testes: calcular_taxa_ml ─────────────────────────────────────────────────


class TestCalcularTaxaML:
    def test_classico_11_pct(self):
        """Taxa clássico = 11%."""
        from app.financeiro.service import calcular_taxa_ml
        assert calcular_taxa_ml("classico") == Decimal("0.11")

    def test_premium_16_pct(self):
        """Taxa premium = 16%."""
        from app.financeiro.service import calcular_taxa_ml
        assert calcular_taxa_ml("premium") == Decimal("0.16")

    def test_full_16_pct(self):
        """Taxa full = 16%."""
        from app.financeiro.service import calcular_taxa_ml
        assert calcular_taxa_ml("full") == Decimal("0.16")

    def test_sale_fee_pct_overrides_table(self):
        """sale_fee_pct tem precedência sobre tabela."""
        from app.financeiro.service import calcular_taxa_ml
        custom_fee = Decimal("0.135")
        assert calcular_taxa_ml("classico", sale_fee_pct=custom_fee) == custom_fee

    def test_listing_type_desconhecido_usa_default(self):
        """Tipo desconhecido usa default 16%."""
        from app.financeiro.service import calcular_taxa_ml
        assert calcular_taxa_ml("super_premium_xyz") == Decimal("0.16")

    def test_case_insensitive(self):
        """Comparação é case-insensitive."""
        from app.financeiro.service import calcular_taxa_ml
        assert calcular_taxa_ml("Classico") == Decimal("0.11")
        assert calcular_taxa_ml("PREMIUM") == Decimal("0.16")

    def test_sale_fee_pct_zero_usa_tabela(self):
        """sale_fee_pct=0 não deve sobrescrever tabela (usa fallback)."""
        from app.financeiro.service import calcular_taxa_ml
        # sale_fee_pct = 0 → não sobrescreve (a condição é > 0)
        result = calcular_taxa_ml("classico", sale_fee_pct=Decimal("0"))
        assert result == Decimal("0.11")


# ─── Testes: calcular_margem ─────────────────────────────────────────────────


class TestCalcularMargem:
    def test_margem_classico_sem_frete(self):
        """Margem clássico: preco - custo - 11% taxa."""
        from app.financeiro.service import calcular_margem
        resultado = calcular_margem(
            preco=Decimal("100.00"),
            custo=Decimal("50.00"),
            listing_type="classico",
        )
        # taxa = 11.00, margem = 100 - 50 - 11 = 39
        assert resultado["taxa_ml_valor"] == Decimal("11.00")
        assert resultado["margem_bruta"] == Decimal("39.00")
        assert resultado["margem_pct"] == Decimal("39.00")

    def test_margem_premium_com_frete(self):
        """Margem premium com frete incluído."""
        from app.financeiro.service import calcular_margem
        resultado = calcular_margem(
            preco=Decimal("100.00"),
            custo=Decimal("40.00"),
            listing_type="premium",
            frete=Decimal("10.00"),
        )
        # taxa = 16.00, margem = 100 - 40 - 16 - 10 = 34
        assert resultado["taxa_ml_valor"] == Decimal("16.00")
        assert resultado["margem_bruta"] == Decimal("34.00")

    def test_margem_zero_quando_preco_zero(self):
        """Preço zero: margem_pct = 0 (sem divisão por zero)."""
        from app.financeiro.service import calcular_margem
        resultado = calcular_margem(
            preco=Decimal("0"),
            custo=Decimal("0"),
            listing_type="classico",
        )
        assert resultado["margem_pct"] == Decimal("0.00")

    def test_margem_negativa_possivel(self):
        """Margem pode ser negativa (prejuízo)."""
        from app.financeiro.service import calcular_margem
        resultado = calcular_margem(
            preco=Decimal("50.00"),
            custo=Decimal("60.00"),  # custo maior que preço
            listing_type="classico",
        )
        assert resultado["margem_bruta"] < 0

    def test_margem_com_sale_fee_pct_real(self):
        """Taxa real via API sobrescreve tabela."""
        from app.financeiro.service import calcular_margem
        resultado = calcular_margem(
            preco=Decimal("100.00"),
            custo=Decimal("50.00"),
            listing_type="classico",
            sale_fee_pct=Decimal("0.13"),  # 13% — taxa real diferente dos 11%
        )
        assert resultado["taxa_ml_valor"] == Decimal("13.00")
        assert resultado["margem_bruta"] == Decimal("37.00")

    def test_lucro_alias_de_margem_bruta(self):
        """lucro é alias de margem_bruta."""
        from app.financeiro.service import calcular_margem
        resultado = calcular_margem(
            preco=Decimal("100.00"),
            custo=Decimal("50.00"),
            listing_type="classico",
        )
        assert resultado["lucro"] == resultado["margem_bruta"]

    def test_frete_zero_por_default(self):
        """Frete padrão é 0."""
        from app.financeiro.service import calcular_margem
        resultado = calcular_margem(
            preco=Decimal("100.00"),
            custo=Decimal("50.00"),
            listing_type="classico",
        )
        assert resultado["frete"] == Decimal("0")

    def test_taxa_pct_retornada_corretamente(self):
        """taxa_ml_pct retorna o percentual correto."""
        from app.financeiro.service import calcular_margem
        resultado = calcular_margem(
            preco=Decimal("100.00"),
            custo=Decimal("0"),
            listing_type="premium",
        )
        assert resultado["taxa_ml_pct"] == Decimal("0.16")


# ─── Testes: get_margem (DB real) ─────────────────────────────────────────────


class TestGetMargem:
    @pytest.mark.asyncio
    async def test_listing_nao_encontrado(self, db):
        """Listing inexistente → 404."""
        from fastapi import HTTPException
        from app.vendas.service_price import get_margem

        user = _make_user()
        db.add(user)
        await db.flush()

        with pytest.raises(HTTPException) as exc:
            await get_margem(db, "MLB999000100", user.id, Decimal("100.00"))

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_margem_sem_produto_usa_custo_zero(self, db):
        """Listing sem produto cadastrado usa custo=0."""
        from app.vendas.service_price import get_margem

        user = _make_user()
        db.add(user)
        await db.flush()

        acc = _make_ml_account(user.id)
        db.add(acc)
        await db.flush()

        listing = _make_listing(user.id, acc.id, mlb_id="MLB000300001", price=Decimal("150.00"))
        db.add(listing)
        await db.flush()

        result = await get_margem(db, "MLB000300001", user.id, Decimal("150.00"))

        assert result.custo_sku == Decimal("0")
        assert result.preco == Decimal("150.00")
        assert result.listing_type == "classico"
        # Com custo=0, margem = preco - taxa_ml
        assert result.margem_bruta == Decimal("150.00") - result.taxa_ml_valor

    @pytest.mark.asyncio
    async def test_margem_retorna_resultado_correto(self, db):
        """Margem calculada corretamente com custo real."""
        from app.produtos.models import Product
        from app.vendas.service_price import get_margem

        user = _make_user()
        db.add(user)
        await db.flush()

        acc = _make_ml_account(user.id)
        db.add(acc)
        await db.flush()

        product = Product(
            id=_uid(),
            user_id=user.id,
            sku="SKU-001",
            name="Produto Teste",
            cost=Decimal("80.00"),
        )
        db.add(product)
        await db.flush()

        listing = _make_listing(
            user.id, acc.id,
            mlb_id="MLB000300002",
            price=Decimal("200.00"),
            listing_type="classico",
        )
        listing.product_id = product.id
        db.add(listing)
        await db.flush()

        result = await get_margem(db, "MLB000300002", user.id, Decimal("200.00"))

        # classico = 11% de 200 = 22
        assert result.taxa_ml_valor == Decimal("22.00")
        # margem = 200 - 80 - 22 = 98
        assert result.margem_bruta == Decimal("98.00")
        assert result.custo_sku == Decimal("80.00")

    @pytest.mark.asyncio
    async def test_margem_premium_taxa_16_pct(self, db):
        """Premium usa 16% de taxa."""
        from app.vendas.service_price import get_margem

        user = _make_user()
        db.add(user)
        await db.flush()

        acc = _make_ml_account(user.id)
        db.add(acc)
        await db.flush()

        listing = _make_listing(
            user.id, acc.id,
            mlb_id="MLB000300003",
            price=Decimal("100.00"),
            listing_type="premium",
        )
        db.add(listing)
        await db.flush()

        result = await get_margem(db, "MLB000300003", user.id, Decimal("100.00"))

        assert result.taxa_ml_valor == Decimal("16.00")


# ─── Testes: update_listing_price ────────────────────────────────────────────


class TestUpdateListingPrice:
    @pytest.mark.asyncio
    async def test_listing_nao_encontrado(self, db):
        """Listing inexistente → 404."""
        from fastapi import HTTPException
        from app.vendas.service_price import update_listing_price

        user = _make_user()
        db.add(user)
        await db.flush()

        with pytest.raises(HTTPException) as exc:
            await update_listing_price(db, "MLB999000200", user.id, Decimal("150.00"))

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_preco_atualizado_corretamente(self, db):
        """Preço deve ser atualizado no banco."""
        from app.vendas.service_price import update_listing_price

        user = _make_user()
        db.add(user)
        await db.flush()

        acc = _make_ml_account(user.id)
        db.add(acc)
        await db.flush()

        listing = _make_listing(user.id, acc.id, mlb_id="MLB000400001", price=Decimal("100.00"))
        db.add(listing)
        await db.flush()

        result = await update_listing_price(db, "MLB000400001", user.id, Decimal("125.00"))

        assert result["mlb_id"] == "MLB000400001"
        assert result["new_price"] == 125.0
        assert "updated_at" in result

    @pytest.mark.asyncio
    async def test_preco_refletido_no_banco(self, db):
        """Após update, listing.price deve refletir novo valor."""
        from sqlalchemy import select
        from app.vendas.service_price import update_listing_price

        user = _make_user()
        db.add(user)
        await db.flush()

        acc = _make_ml_account(user.id)
        db.add(acc)
        await db.flush()

        listing_id = _uid()
        listing = Listing(
            id=listing_id,
            user_id=user.id,
            ml_account_id=acc.id,
            mlb_id="MLB000400002",
            title="T",
            listing_type="classico",
            price=Decimal("100.00"),
            status="active",
        )
        db.add(listing)
        await db.flush()

        await update_listing_price(db, "MLB000400002", user.id, Decimal("180.00"))

        # Verificar no banco
        result = await db.execute(
            select(Listing).where(Listing.mlb_id == "MLB000400002")
        )
        updated = result.scalar_one_or_none()
        assert updated is not None
        assert float(updated.price) == 180.0


# ─── Testes: apply_price_suggestion (validação) ──────────────────────────────


class TestApplyPriceSuggestionValidation:
    @pytest.mark.asyncio
    async def test_listing_nao_encontrado(self, db):
        """Listing inexistente → 404."""
        from fastapi import HTTPException
        from app.vendas.service_price import apply_price_suggestion

        user = _make_user()
        db.add(user)
        await db.flush()

        with pytest.raises(HTTPException) as exc:
            await apply_price_suggestion(db, "MLB999000300", user.id, 90.0, "test")

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_sem_ml_account_token_raises_400(self, db):
        """Sem token ML → 400 Bad Request."""
        from fastapi import HTTPException
        from app.vendas.service_price import apply_price_suggestion

        user = _make_user()
        db.add(user)
        await db.flush()

        # Conta sem token
        acc = MLAccount(
            id=_uid(),
            user_id=user.id,
            ml_user_id="999",
            nickname="no_token",
            is_active=True,
            access_token=None,
        )
        db.add(acc)
        await db.flush()

        listing = _make_listing(
            user.id, acc.id,
            mlb_id="MLB000500001",
            price=Decimal("200.00"),
        )
        db.add(listing)
        await db.flush()

        with pytest.raises(HTTPException) as exc:
            await apply_price_suggestion(db, "MLB000500001", user.id, 150.0, "test")

        assert exc.value.status_code == 400
        assert "token" in exc.value.detail.lower() or "conta" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_preco_maior_que_base_raises_400(self, db):
        """new_price >= base_price → 400 (promoção precisa ser desconto)."""
        from fastapi import HTTPException
        from app.vendas.service_price import apply_price_suggestion

        user = _make_user()
        db.add(user)
        await db.flush()

        acc = MLAccount(
            id=_uid(),
            user_id=user.id,
            ml_user_id="seller456",
            nickname="seller",
            is_active=True,
            access_token="valid_token_abc",
        )
        db.add(acc)
        await db.flush()

        listing = _make_listing(
            user.id, acc.id,
            mlb_id="MLB000500002",
            price=Decimal("200.00"),
            original_price=None,
        )
        db.add(listing)
        await db.flush()

        # new_price = 200 (igual ao base_price) → deve rejeitar
        with pytest.raises(HTTPException) as exc:
            await apply_price_suggestion(db, "MLB000500002", user.id, 200.0, "test")

        assert exc.value.status_code == 400
        assert "preço" in exc.value.detail.lower() or "preco" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_preco_acima_base_raises_400(self, db):
        """new_price > base_price → 400."""
        from fastapi import HTTPException
        from app.vendas.service_price import apply_price_suggestion

        user = _make_user()
        db.add(user)
        await db.flush()

        acc = MLAccount(
            id=_uid(),
            user_id=user.id,
            ml_user_id="seller789",
            nickname="seller",
            is_active=True,
            access_token="valid_token_xyz",
        )
        db.add(acc)
        await db.flush()

        listing = _make_listing(
            user.id, acc.id,
            mlb_id="MLB000500003",
            price=Decimal("200.00"),
        )
        db.add(listing)
        await db.flush()

        # new_price = 250 > base_price 200 → deve rejeitar
        with pytest.raises(HTTPException) as exc:
            await apply_price_suggestion(db, "MLB000500003", user.id, 250.0, "test")

        assert exc.value.status_code == 400


# ─── Testes: simulate_price ───────────────────────────────────────────────────


class TestSimulatePrice:
    @pytest.mark.asyncio
    async def test_listing_nao_encontrado(self, db):
        """Listing inexistente → 404."""
        from fastapi import HTTPException
        from app.vendas.service_price import simulate_price

        user = _make_user()
        db.add(user)
        await db.flush()

        with pytest.raises(HTTPException) as exc:
            await simulate_price(db, "MLB999000400", user.id, 150.0)

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_sem_snapshots_is_estimated_true(self, db):
        """Sem snapshots, simulação é estimada."""
        from app.vendas.service_price import simulate_price

        user = _make_user()
        db.add(user)
        await db.flush()

        acc = _make_ml_account(user.id)
        db.add(acc)
        await db.flush()

        listing = _make_listing(user.id, acc.id, mlb_id="MLB000600001")
        db.add(listing)
        await db.flush()

        result = await simulate_price(db, "MLB000600001", user.id, 180.0)

        assert result.is_estimated is True

    @pytest.mark.asyncio
    async def test_com_poucos_snapshots_is_estimated(self, db):
        """Com menos de 7 snapshots, simulação é estimada."""
        from app.vendas.service_price import simulate_price

        user = _make_user()
        db.add(user)
        await db.flush()

        acc = _make_ml_account(user.id)
        db.add(acc)
        await db.flush()

        listing = _make_listing(user.id, acc.id, mlb_id="MLB000600002")
        db.add(listing)
        await db.flush()

        now = datetime.utcnow()
        for i in range(3):  # apenas 3, abaixo do mínimo de 7
            db.add(_make_snapshot(listing.id, captured_at=now - timedelta(days=i)))
        await db.flush()

        result = await simulate_price(db, "MLB000600002", user.id, 180.0)

        assert result.is_estimated is True

    @pytest.mark.asyncio
    async def test_retorna_current_price(self, db):
        """current_price deve corresponder ao listing.price."""
        from app.vendas.service_price import simulate_price

        user = _make_user()
        db.add(user)
        await db.flush()

        acc = _make_ml_account(user.id)
        db.add(acc)
        await db.flush()

        listing = _make_listing(user.id, acc.id, mlb_id="MLB000600003", price=Decimal("250.00"))
        db.add(listing)
        await db.flush()

        result = await simulate_price(db, "MLB000600003", user.id, 200.0)

        assert result.current_price == 250.0

    @pytest.mark.asyncio
    async def test_retorna_target_price(self, db):
        """target_price deve ser o preço solicitado."""
        from app.vendas.service_price import simulate_price

        user = _make_user()
        db.add(user)
        await db.flush()

        acc = _make_ml_account(user.id)
        db.add(acc)
        await db.flush()

        listing = _make_listing(user.id, acc.id, mlb_id="MLB000600004", price=Decimal("200.00"))
        db.add(listing)
        await db.flush()

        result = await simulate_price(db, "MLB000600004", user.id, 170.0)

        assert result.target_price == 170.0

    @pytest.mark.asyncio
    async def test_com_7_plus_snapshots_nao_estimado(self, db):
        """Com 7+ snapshots, is_estimated pode ser False."""
        from app.vendas.service_price import simulate_price

        user = _make_user()
        db.add(user)
        await db.flush()

        acc = _make_ml_account(user.id)
        db.add(acc)
        await db.flush()

        listing = _make_listing(user.id, acc.id, mlb_id="MLB000600005", price=Decimal("200.00"))
        db.add(listing)
        await db.flush()

        now = datetime.utcnow()
        for i in range(10):  # 10 snapshots = acima do mínimo de 7
            db.add(_make_snapshot(
                listing.id,
                price=Decimal("200.00"),
                visits=50,
                sales_today=5,
                captured_at=now - timedelta(days=i),
            ))
        await db.flush()

        result = await simulate_price(db, "MLB000600005", user.id, 180.0)

        assert result.is_estimated is False


# ─── Testes: list_repricing_rules ─────────────────────────────────────────────


class TestListRepricingRules:
    @pytest.mark.asyncio
    async def test_usuario_sem_regras_retorna_lista_vazia(self, db):
        """Usuário sem regras retorna lista vazia."""
        from app.vendas.service_price import list_repricing_rules

        user = _make_user()
        db.add(user)
        await db.flush()

        result = await list_repricing_rules(db, user.id)

        assert result == []

    @pytest.mark.asyncio
    async def test_retorna_regras_do_usuario(self, db):
        """Regras do usuário são retornadas."""
        from app.vendas.service_price import list_repricing_rules

        user = _make_user()
        db.add(user)
        await db.flush()

        acc = _make_ml_account(user.id)
        db.add(acc)
        await db.flush()

        listing = _make_listing(user.id, acc.id)
        db.add(listing)
        await db.flush()

        rule = _make_repricing_rule(user.id, listing.id)
        db.add(rule)
        await db.flush()

        result = await list_repricing_rules(db, user.id)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_nao_retorna_regras_de_outro_usuario(self, db):
        """Regras de outro usuário não são retornadas."""
        from app.vendas.service_price import list_repricing_rules

        user1 = _make_user()
        user2 = _make_user()
        db.add_all([user1, user2])
        await db.flush()

        acc = _make_ml_account(user1.id)
        db.add(acc)
        await db.flush()

        listing = _make_listing(user1.id, acc.id)
        db.add(listing)
        await db.flush()

        rule = _make_repricing_rule(user1.id, listing.id)
        db.add(rule)
        await db.flush()

        result = await list_repricing_rules(db, user2.id)

        assert result == []

    @pytest.mark.asyncio
    async def test_filtra_por_listing_id(self, db):
        """Filtragem por listing_id funciona corretamente."""
        from app.vendas.service_price import list_repricing_rules

        user = _make_user()
        db.add(user)
        await db.flush()

        acc = _make_ml_account(user.id)
        db.add(acc)
        await db.flush()

        listing1 = _make_listing(user.id, acc.id, mlb_id="MLB000700001")
        listing2 = _make_listing(user.id, acc.id, mlb_id="MLB000700002")
        db.add_all([listing1, listing2])
        await db.flush()

        rule1 = _make_repricing_rule(user.id, listing1.id)
        rule2 = _make_repricing_rule(user.id, listing2.id)
        db.add_all([rule1, rule2])
        await db.flush()

        result = await list_repricing_rules(db, user.id, listing_id=listing1.id)

        assert len(result) == 1


# ─── Testes: create_repricing_rule ───────────────────────────────────────────


class TestCreateRepricingRule:
    @pytest.mark.asyncio
    async def test_listing_nao_encontrado_raises_404(self, db):
        """Listing ID inexistente → 404."""
        from fastapi import HTTPException
        from app.vendas.service_price import create_repricing_rule
        from app.vendas.schemas import RepricingRuleCreate

        user = _make_user()
        db.add(user)
        await db.flush()

        rule_data = RepricingRuleCreate(
            listing_id=_uid(),  # listing_id inexistente
            rule_type="FIXED_MARKUP",
            value=Decimal("1.40"),
            min_price=Decimal("100.00"),
            max_price=Decimal("500.00"),
        )

        with pytest.raises(HTTPException) as exc:
            await create_repricing_rule(db, user.id, rule_data)

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_cria_regra_corretamente(self, db):
        """Regra criada com dados corretos."""
        from app.vendas.service_price import create_repricing_rule
        from app.vendas.schemas import RepricingRuleCreate

        user = _make_user()
        db.add(user)
        await db.flush()

        acc = _make_ml_account(user.id)
        db.add(acc)
        await db.flush()

        listing = _make_listing(user.id, acc.id, mlb_id="MLB000800001")
        db.add(listing)
        await db.flush()

        rule_data = RepricingRuleCreate(
            listing_id=listing.id,
            rule_type="FIXED_MARKUP",
            value=Decimal("1.50"),
            min_price=Decimal("100.00"),
            max_price=Decimal("600.00"),
        )

        result = await create_repricing_rule(db, user.id, rule_data)

        assert result["rule_type"] == "FIXED_MARKUP"
        assert result["mlb_id"] == "MLB000800001"
        assert result["is_active"] is True

    @pytest.mark.asyncio
    async def test_floor_ceiling_sem_value(self, db):
        """FLOOR_CEILING não requer value — apenas min/max."""
        from app.vendas.service_price import create_repricing_rule
        from app.vendas.schemas import RepricingRuleCreate

        user = _make_user()
        db.add(user)
        await db.flush()

        acc = _make_ml_account(user.id)
        db.add(acc)
        await db.flush()

        listing = _make_listing(user.id, acc.id, mlb_id="MLB000800002")
        db.add(listing)
        await db.flush()

        rule_data = RepricingRuleCreate(
            listing_id=listing.id,
            rule_type="FLOOR_CEILING",
            value=None,
            min_price=Decimal("150.00"),
            max_price=Decimal("300.00"),
        )

        result = await create_repricing_rule(db, user.id, rule_data)

        assert result["rule_type"] == "FLOOR_CEILING"


# ─── Testes: delete_repricing_rule ───────────────────────────────────────────


class TestDeleteRepricingRule:
    @pytest.mark.asyncio
    async def test_regra_inexistente_raises_404(self, db):
        """Regra que não existe → 404."""
        from fastapi import HTTPException
        from app.vendas.service_price import delete_repricing_rule

        user = _make_user()
        db.add(user)
        await db.flush()

        with pytest.raises(HTTPException) as exc:
            await delete_repricing_rule(db, user.id, _uid())

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_deleta_regra_corretamente(self, db):
        """Regra deletada com sucesso."""
        from sqlalchemy import select
        from app.vendas.service_price import delete_repricing_rule

        user = _make_user()
        db.add(user)
        await db.flush()

        acc = _make_ml_account(user.id)
        db.add(acc)
        await db.flush()

        listing = _make_listing(user.id, acc.id)
        db.add(listing)
        await db.flush()

        rule = _make_repricing_rule(user.id, listing.id)
        db.add(rule)
        await db.flush()
        rule_id = rule.id

        result_delete = await delete_repricing_rule(db, user.id, rule_id)

        # delete_repricing_rule é soft-delete: marca is_active=False
        assert result_delete["is_active"] is False

        # Verificar que está marcada como inativa no banco
        result = await db.execute(
            select(RepricingRule).where(RepricingRule.id == rule_id)
        )
        soft_deleted = result.scalar_one_or_none()
        assert soft_deleted is not None
        assert soft_deleted.is_active is False

    @pytest.mark.asyncio
    async def test_nao_pode_deletar_regra_de_outro_usuario(self, db):
        """Usuário não pode deletar regra de outro."""
        from fastapi import HTTPException
        from app.vendas.service_price import delete_repricing_rule

        user1 = _make_user()
        user2 = _make_user()
        db.add_all([user1, user2])
        await db.flush()

        acc = _make_ml_account(user1.id)
        db.add(acc)
        await db.flush()

        listing = _make_listing(user1.id, acc.id)
        db.add(listing)
        await db.flush()

        rule = _make_repricing_rule(user1.id, listing.id)
        db.add(rule)
        await db.flush()

        with pytest.raises(HTTPException) as exc:
            await delete_repricing_rule(db, user2.id, rule.id)

        assert exc.value.status_code == 404


# ─── Testes: _rule_to_dict (pura) ────────────────────────────────────────────


class TestRuleToDict:
    def test_serializa_campos_basicos(self):
        """_rule_to_dict serializa campos básicos corretamente."""
        from app.vendas.service_price import _rule_to_dict

        rule = MagicMock()
        rule.id = _uid()
        rule.user_id = _uid()
        rule.listing_id = _uid()
        rule.rule_type = "FIXED_MARKUP"
        rule.value = Decimal("1.40")
        rule.min_price = Decimal("100.00")
        rule.max_price = Decimal("500.00")
        rule.is_active = True
        rule.last_applied_at = None
        rule.last_applied_price = None
        rule.created_at = datetime.utcnow()

        listing = MagicMock()
        listing.mlb_id = "MLB123456789"
        listing.title = "Produto X"

        result = _rule_to_dict(rule, listing=listing)

        assert result["rule_type"] == "FIXED_MARKUP"
        assert result["mlb_id"] == "MLB123456789"
        assert result["listing_title"] == "Produto X"
        assert result["is_active"] is True

    def test_sem_listing_mlb_id_none(self):
        """Sem listing, mlb_id e listing_title são None."""
        from app.vendas.service_price import _rule_to_dict

        rule = MagicMock()
        rule.id = _uid()
        rule.user_id = _uid()
        rule.listing_id = _uid()
        rule.rule_type = "FLOOR_CEILING"
        rule.value = None
        rule.min_price = Decimal("100.00")
        rule.max_price = Decimal("300.00")
        rule.is_active = True
        rule.last_applied_at = None
        rule.last_applied_price = None
        rule.created_at = datetime.utcnow()
        # Simula que rule.listing retorna None
        type(rule).listing = property(lambda self: None)

        result = _rule_to_dict(rule, listing=None)

        assert result["mlb_id"] is None
        assert result["listing_title"] is None
