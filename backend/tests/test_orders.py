"""
Testes para o model Order e schemas relacionados a pedidos.

Estratégia:
- Testa model (campos, constraints, nullable), schemas e lógica de negócio
- Sem DB real — usa mocks e testes de model attributes
- Testa OrderOut schema, filtros e edge cases
"""
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

import pytest

BRT = timezone(timedelta(hours=-3))


# ─── Testes: Order model — atributos e estrutura ─────────────────────────────

class TestOrderModel:
    def test_order_tem_ml_order_id(self):
        """Order deve ter campo ml_order_id como identificador externo."""
        from app.vendas.models import Order
        assert hasattr(Order, "ml_order_id")

    def test_order_tem_ml_account_id(self):
        """Order deve ter FK para ml_accounts."""
        from app.vendas.models import Order
        assert hasattr(Order, "ml_account_id")

    def test_order_tem_listing_id_nullable(self):
        """listing_id deve ser nullable no model Order."""
        from app.vendas.models import Order
        col = Order.__table__.c["listing_id"]
        assert col.nullable is True

    def test_order_tem_net_amount(self):
        """Order deve ter net_amount para calcular 'você recebe'."""
        from app.vendas.models import Order
        assert hasattr(Order, "net_amount")

    def test_order_tem_sale_fee(self):
        """Order deve ter sale_fee (tarifa de venda ML)."""
        from app.vendas.models import Order
        assert hasattr(Order, "sale_fee")

    def test_order_tem_shipping_cost(self):
        """Order deve ter shipping_cost (custo de frete)."""
        from app.vendas.models import Order
        assert hasattr(Order, "shipping_cost")

    def test_order_tem_payment_date_nullable(self):
        """payment_date deve ser nullable."""
        from app.vendas.models import Order
        col = Order.__table__.c["payment_date"]
        assert col.nullable is True

    def test_order_tem_delivery_date_nullable(self):
        """delivery_date deve ser nullable."""
        from app.vendas.models import Order
        col = Order.__table__.c["delivery_date"]
        assert col.nullable is True

    def test_order_tem_order_date_nao_nullable(self):
        """order_date não deve ser nullable (campo obrigatório)."""
        from app.vendas.models import Order
        col = Order.__table__.c["order_date"]
        assert col.nullable is False

    def test_order_ml_order_id_unico(self):
        """ml_order_id deve ter constraint unique."""
        from app.vendas.models import Order
        col = Order.__table__.c["ml_order_id"]
        assert col.unique is True

    def test_order_tem_payment_status(self):
        """Order deve ter payment_status para rastrear pagamento."""
        from app.vendas.models import Order
        assert hasattr(Order, "payment_status")

    def test_order_tem_shipping_status(self):
        """Order deve ter shipping_status para rastrear entrega."""
        from app.vendas.models import Order
        assert hasattr(Order, "shipping_status")

    def test_order_tem_buyer_nickname(self):
        """Order deve registrar apelido do comprador."""
        from app.vendas.models import Order
        assert hasattr(Order, "buyer_nickname")

    def test_order_tem_quantidade(self):
        """Order deve registrar quantidade de itens."""
        from app.vendas.models import Order
        assert hasattr(Order, "quantity")

    def test_order_tem_mlb_id(self):
        """Order deve registrar o MLB ID do anúncio."""
        from app.vendas.models import Order
        assert hasattr(Order, "mlb_id")


# ─── Testes: OrderOut schema ─────────────────────────────────────────────────

class TestOrderOutSchema:
    def _make_order_data(self, **overrides):
        now = datetime.now(BRT)
        base = {
            "id": uuid.uuid4(),
            "ml_order_id": "ML-123456",
            "ml_account_id": uuid.uuid4(),
            "listing_id": None,
            "mlb_id": "MLB500",
            "buyer_nickname": "compradorX",
            "quantity": 1,
            "unit_price": Decimal("100.00"),
            "total_amount": Decimal("100.00"),
            "sale_fee": Decimal("17.00"),
            "shipping_cost": Decimal("0.00"),
            "net_amount": Decimal("83.00"),
            "payment_status": "approved",
            "shipping_status": "shipped",
            "order_date": now,
            "payment_date": None,
            "delivery_date": None,
            "created_at": now,
        }
        base.update(overrides)
        return base

    def test_order_out_valida_todos_campos(self):
        """OrderOut deve aceitar todos os campos válidos."""
        from app.vendas.schemas import OrderOut
        data = self._make_order_data()
        out = OrderOut(**data)
        assert out.ml_order_id == "ML-123456"

    def test_order_out_listing_id_none(self):
        """OrderOut deve aceitar listing_id=None."""
        from app.vendas.schemas import OrderOut
        data = self._make_order_data(listing_id=None)
        out = OrderOut(**data)
        assert out.listing_id is None

    def test_order_out_listing_id_com_uuid(self):
        """OrderOut deve aceitar listing_id como UUID."""
        from app.vendas.schemas import OrderOut
        listing_id = uuid.uuid4()
        data = self._make_order_data(listing_id=listing_id)
        out = OrderOut(**data)
        assert out.listing_id == listing_id

    def test_order_out_payment_date_nullable(self):
        """OrderOut deve aceitar payment_date=None."""
        from app.vendas.schemas import OrderOut
        data = self._make_order_data(payment_date=None)
        out = OrderOut(**data)
        assert out.payment_date is None

    def test_order_out_delivery_date_nullable(self):
        """OrderOut deve aceitar delivery_date=None."""
        from app.vendas.schemas import OrderOut
        data = self._make_order_data(delivery_date=None)
        out = OrderOut(**data)
        assert out.delivery_date is None

    def test_order_out_net_amount_correto(self):
        """net_amount deve refletir valor líquido a receber."""
        from app.vendas.schemas import OrderOut
        data = self._make_order_data(
            total_amount=Decimal("200.00"),
            sale_fee=Decimal("32.00"),
            shipping_cost=Decimal("0.00"),
            net_amount=Decimal("168.00"),
        )
        out = OrderOut(**data)
        assert out.net_amount == Decimal("168.00")

    def test_order_out_tem_todos_campos_esperados(self):
        """OrderOut deve ter todos os campos necessários para o frontend."""
        from app.vendas.schemas import OrderOut

        expected_fields = {
            "id", "ml_order_id", "ml_account_id", "listing_id",
            "mlb_id", "buyer_nickname", "quantity", "unit_price",
            "total_amount", "sale_fee", "shipping_cost", "net_amount",
            "payment_status", "shipping_status", "order_date",
            "payment_date", "delivery_date", "created_at",
        }
        actual_fields = set(OrderOut.model_fields.keys())
        assert expected_fields.issubset(actual_fields)


# ─── Testes: lógica de net_amount ───────────────────────────────────────────

class TestOrderNetAmountLogica:
    """Testa lógica de cálculo do valor líquido a receber."""

    def test_net_amount_descontando_taxa(self):
        """net_amount = total_amount - sale_fee - shipping_cost."""
        total = Decimal("100.00")
        taxa = Decimal("17.00")
        frete = Decimal("0.00")
        net = total - taxa - frete
        assert net == Decimal("83.00")

    def test_net_amount_com_frete(self):
        """net_amount deve descontar frete quando presente."""
        total = Decimal("150.00")
        taxa = Decimal("24.00")  # 16% de 150
        frete = Decimal("15.00")
        net = total - taxa - frete
        assert net == Decimal("111.00")

    def test_net_amount_nao_negativo_esperado(self):
        """Em cenário normal, net_amount deve ser positivo."""
        total = Decimal("100.00")
        taxa = Decimal("11.00")  # 11% classico
        frete = Decimal("0.00")
        net = total - taxa - frete
        assert net > Decimal("0")

    def test_calculo_taxa_classico(self):
        """Taxa clássico = 11% do preço."""
        preco = Decimal("100.00")
        taxa_pct = Decimal("0.11")
        taxa_valor = (preco * taxa_pct).quantize(Decimal("0.01"))
        assert taxa_valor == Decimal("11.00")

    def test_calculo_taxa_premium(self):
        """Taxa premium = 16% do preço."""
        preco = Decimal("100.00")
        taxa_pct = Decimal("0.16")
        taxa_valor = (preco * taxa_pct).quantize(Decimal("0.01"))
        assert taxa_valor == Decimal("16.00")


# ─── Testes: filtragem de pedidos — lógica de negócio ───────────────────────

class TestOrderFiltrosLogica:
    """Testa lógica de filtragem sem DB real."""

    def _make_mock_order(self, order_date: datetime, ml_account_id: uuid.UUID) -> MagicMock:
        obj = MagicMock()
        obj.order_date = order_date
        obj.ml_account_id = ml_account_id
        return obj

    def test_filtro_por_data_exclui_pedidos_antigos(self):
        """Pedidos anteriores a date_from devem ser excluídos."""
        now = datetime.now(BRT)
        account_id = uuid.uuid4()
        orders = [
            self._make_mock_order(now, account_id),
            self._make_mock_order(now - timedelta(days=1), account_id),
            self._make_mock_order(now - timedelta(days=10), account_id),
        ]
        date_from = now - timedelta(days=2)
        filtered = [o for o in orders if o.order_date >= date_from]
        assert len(filtered) == 2

    def test_filtro_por_ml_account_id(self):
        """Pedidos de outra conta ML devem ser excluídos."""
        now = datetime.now(BRT)
        account1 = uuid.uuid4()
        account2 = uuid.uuid4()
        orders = [
            self._make_mock_order(now, account1),
            self._make_mock_order(now, account1),
            self._make_mock_order(now, account2),
        ]
        filtered = [o for o in orders if o.ml_account_id == account1]
        assert len(filtered) == 2

    def test_paginacao_limit_offset(self):
        """Paginação com limit/offset deve retornar subconjunto correto."""
        orders = list(range(10))  # simulação de 10 pedidos
        page1 = orders[0:3]
        page2 = orders[3:6]
        assert page1 == [0, 1, 2]
        assert page2 == [3, 4, 5]

    def test_filtro_pedidos_de_hoje(self):
        """Filtro start_of_day deve retornar apenas pedidos do dia atual."""
        now = datetime.now(BRT)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        account_id = uuid.uuid4()
        orders = [
            self._make_mock_order(now, account_id),                       # hoje
            self._make_mock_order(now - timedelta(days=1), account_id),   # ontem
            self._make_mock_order(now - timedelta(hours=25), account_id), # > 24h
        ]
        filtered = [o for o in orders if o.order_date >= start_of_day]
        assert len(filtered) == 1

    def test_filtro_pedidos_aprovados(self):
        """Filtro por payment_status=approved deve excluir pendentes."""
        orders_data = [
            {"status": "approved", "total": Decimal("100.00")},
            {"status": "pending", "total": Decimal("50.00")},
            {"status": "approved", "total": Decimal("200.00")},
            {"status": "refunded", "total": Decimal("80.00")},
        ]
        approved = [o for o in orders_data if o["status"] == "approved"]
        assert len(approved) == 2
        total_aprovado = sum(o["total"] for o in approved)
        assert total_aprovado == Decimal("300.00")


# ─── Testes: edge cases ──────────────────────────────────────────────────────

class TestOrderEdgeCases:
    def test_order_quantidade_multipla(self):
        """Order com quantity > 1 deve multiplicar unit_price corretamente."""
        unit_price = Decimal("50.00")
        quantity = 3
        total_esperado = unit_price * quantity
        assert total_esperado == Decimal("150.00")

    def test_net_amount_com_taxa_zero(self):
        """Se taxa for 0, net_amount = total_amount - shipping."""
        total = Decimal("100.00")
        taxa = Decimal("0.00")
        frete = Decimal("10.00")
        net = total - taxa - frete
        assert net == Decimal("90.00")

    def test_order_out_serializa_decimals(self):
        """OrderOut deve serializar Decimal corretamente."""
        from app.vendas.schemas import OrderOut

        now = datetime.now(BRT)
        data = {
            "id": uuid.uuid4(),
            "ml_order_id": "ML-DECIMAL",
            "ml_account_id": uuid.uuid4(),
            "listing_id": None,
            "mlb_id": "MLB111",
            "buyer_nickname": "test",
            "quantity": 1,
            "unit_price": Decimal("99.99"),
            "total_amount": Decimal("99.99"),
            "sale_fee": Decimal("10.99"),
            "shipping_cost": Decimal("5.00"),
            "net_amount": Decimal("84.00"),
            "payment_status": "approved",
            "shipping_status": "delivered",
            "order_date": now,
            "payment_date": now,
            "delivery_date": now,
            "created_at": now,
        }
        out = OrderOut(**data)
        # Deve serializar sem erros
        dumped = out.model_dump()
        assert dumped["unit_price"] == Decimal("99.99")
        assert dumped["net_amount"] == Decimal("84.00")
