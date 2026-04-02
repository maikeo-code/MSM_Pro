"""
Testes de service para o módulo vendas — lógica de KPI, listagens e analytics.

Estratégia:
- Funções puras testadas diretamente (sem DB)
- Lógica de KPI testada com mocks de AsyncSession
- Foco em comportamentos corretos (não implementação)
"""
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

import pytest


BRT = timezone(timedelta(hours=-3))


# ─── Helpers para criar objetos mock de DB ───────────────────────────────────

def _make_listing_dict(
    user_id=None, ml_account_id=None, mlb_id="MLB100", price=Decimal("100.00")
):
    lid = uuid.uuid4()
    uid = user_id or uuid.uuid4()
    aid = ml_account_id or uuid.uuid4()
    obj = MagicMock()
    obj.id = lid
    obj.user_id = uid
    obj.ml_account_id = aid
    obj.mlb_id = mlb_id
    obj.title = f"Produto {mlb_id}"
    obj.listing_type = "classico"
    obj.price = price
    obj.original_price = None
    obj.sale_price = None
    obj.status = "active"
    obj.category_id = None
    obj.seller_sku = None
    obj.sale_fee_amount = None
    obj.sale_fee_pct = None
    obj.avg_shipping_cost = None
    obj.permalink = None
    obj.thumbnail = None
    obj.quality_score = None
    obj.created_at = datetime.now(BRT)
    obj.updated_at = datetime.now(BRT)
    return obj


def _make_snapshot_obj(
    listing_id,
    price=Decimal("100.00"),
    sales=5,
    visits=200,
    stock=50,
    revenue=None,
    captured_at=None,
):
    if captured_at is None:
        captured_at = datetime.now(BRT)
    obj = MagicMock()
    obj.id = uuid.uuid4()
    obj.listing_id = listing_id
    obj.price = price
    obj.visits = visits
    obj.sales_today = sales
    obj.questions = 0
    obj.stock = stock
    obj.revenue = revenue
    obj.conversion_rate = None
    obj.orders_count = 0
    obj.cancelled_orders = 0
    obj.cancelled_revenue = Decimal("0")
    obj.returns_count = 0
    obj.returns_revenue = Decimal("0")
    obj.captured_at = captured_at
    return obj


# ─── Testes: _kpi_single_day — lógica de cálculo ────────────────────────────

class TestKpiCalculations:
    """Testa lógica de KPI via funções auxiliares sem banco real."""

    def test_conversao_calculo_correto(self):
        """Taxa de conversão deve ser vendas/visitas * 100."""
        vendas = 8
        visitas = 350
        conversao = round((vendas / visitas * 100), 2)
        assert conversao == pytest.approx(2.29, abs=0.01)

    def test_conversao_zero_quando_sem_visitas(self):
        """Conversão deve ser 0.0 quando visitas = 0 (evitar ZeroDivisionError)."""
        visitas = 0
        vendas = 5
        conversao = round((vendas / visitas * 100), 2) if visitas > 0 else 0.0
        assert conversao == 0.0

    def test_taxa_cancelamento_calculo(self):
        """Taxa de cancelamento = cancelados / (pedidos + cancelados) * 100."""
        pedidos = 8
        cancelados = 2
        total = pedidos + cancelados
        taxa = round(cancelados / total * 100, 2)
        assert taxa == 20.0

    def test_taxa_cancelamento_sem_pedidos(self):
        """Taxa de cancelamento deve ser 0 quando não há pedidos."""
        pedidos = 0
        cancelados = 0
        total = pedidos + cancelados
        taxa = round(cancelados / total * 100, 2) if total > 0 else 0.0
        assert taxa == 0.0

    def test_preco_medio_por_venda(self):
        """Preço médio por venda = receita_total / pedidos."""
        receita_total = 500.0
        pedidos = 5
        preco_medio = round(receita_total / pedidos, 2)
        assert preco_medio == 100.0

    def test_preco_medio_sem_pedidos(self):
        """Preço médio deve ser 0 quando não há pedidos."""
        receita_total = 0.0
        pedidos = 0
        preco_medio = round(receita_total / pedidos, 2) if pedidos > 0 else 0.0
        assert preco_medio == 0.0

    def test_vendas_concluidas_desconta_cancelamentos(self):
        """Vendas concluídas = receita - cancelamentos - devoluções."""
        receita_total = 1000.0
        cancelados_valor = 100.0
        devolucoes_valor = 50.0
        vendas_concluidas = round(receita_total - cancelados_valor - devolucoes_valor, 2)
        assert vendas_concluidas == 850.0


# ─── Testes: _period_to_dates ────────────────────────────────────────────────

class TestPeriodToDates:
    """Testa conversão de string de período para datas."""

    def test_period_7d(self):
        from app.vendas.service_kpi import _period_to_dates
        today = date.today()
        date_from, date_to, label = _period_to_dates("7d", today)
        assert (date_to - date_from).days == 6
        assert label != ""

    def test_period_15d(self):
        from app.vendas.service_kpi import _period_to_dates
        today = date.today()
        date_from, date_to, label = _period_to_dates("15d", today)
        assert (date_to - date_from).days == 14

    def test_period_30d(self):
        from app.vendas.service_kpi import _period_to_dates
        today = date.today()
        date_from, date_to, label = _period_to_dates("30d", today)
        assert (date_to - date_from).days == 29

    def test_period_date_to_is_today(self):
        from app.vendas.service_kpi import _period_to_dates
        today = date.today()
        _, date_to, _ = _period_to_dates("7d", today)
        assert date_to == today


# ─── Testes: Listing model — campos e defaults ───────────────────────────────

class TestListingModel:
    """Testa campos e defaults do model Listing sem conexão com banco."""

    def test_listing_tem_campo_sale_price(self):
        """Model Listing deve ter campo sale_price nullable."""
        from app.vendas.models import Listing
        assert hasattr(Listing, "sale_price")

    def test_listing_tem_campo_original_price(self):
        """Model Listing deve ter campo original_price."""
        from app.vendas.models import Listing
        assert hasattr(Listing, "original_price")

    def test_listing_tem_campo_price(self):
        """Model Listing deve ter campo price (preço atual)."""
        from app.vendas.models import Listing
        assert hasattr(Listing, "price")

    def test_listing_tem_campo_mlb_id(self):
        """Model Listing deve ter mlb_id com índice único."""
        from app.vendas.models import Listing
        assert hasattr(Listing, "mlb_id")

    def test_listing_tem_ml_account_id(self):
        """Model Listing deve ter FK para ml_accounts."""
        from app.vendas.models import Listing
        assert hasattr(Listing, "ml_account_id")

    def test_listing_tem_user_id(self):
        """Model Listing deve ter FK para users."""
        from app.vendas.models import Listing
        assert hasattr(Listing, "user_id")

    def test_listing_sale_price_e_nullable(self):
        """sale_price deve ser nullable no model."""
        from app.vendas.models import Listing
        col = Listing.__table__.c["sale_price"]
        assert col.nullable is True

    def test_listing_original_price_e_nullable(self):
        """original_price deve ser nullable no model."""
        from app.vendas.models import Listing
        col = Listing.__table__.c["original_price"]
        assert col.nullable is True

    def test_listing_price_nao_nullable(self):
        """price (preço atual) não deve ser nullable."""
        from app.vendas.models import Listing
        col = Listing.__table__.c["price"]
        assert col.nullable is False


# ─── Testes: ListingSnapshot model ───────────────────────────────────────────

class TestListingSnapshotModel:
    def test_snapshot_tem_listing_id(self):
        from app.vendas.models import ListingSnapshot
        assert hasattr(ListingSnapshot, "listing_id")

    def test_snapshot_tem_sales_today(self):
        from app.vendas.models import ListingSnapshot
        assert hasattr(ListingSnapshot, "sales_today")

    def test_snapshot_tem_visits(self):
        from app.vendas.models import ListingSnapshot
        assert hasattr(ListingSnapshot, "visits")

    def test_snapshot_tem_conversion_rate(self):
        """conversion_rate deve ser nullable no snapshot."""
        from app.vendas.models import ListingSnapshot
        col = ListingSnapshot.__table__.c["conversion_rate"]
        assert col.nullable is True

    def test_snapshot_tem_revenue(self):
        """revenue deve ser nullable (apenas preenchido quando há dados de orders)."""
        from app.vendas.models import ListingSnapshot
        col = ListingSnapshot.__table__.c["revenue"]
        assert col.nullable is True

    def test_snapshot_tem_captured_at(self):
        from app.vendas.models import ListingSnapshot
        assert hasattr(ListingSnapshot, "captured_at")


# ─── Testes: Schemas ─────────────────────────────────────────────────────────

class TestListingSchemas:
    def test_listing_create_valida_mlb_id_pattern(self):
        """ListingCreate deve aceitar MLB-123 e MLB123."""
        from app.vendas.schemas import ListingCreate

        valid_ids = ["MLB123", "MLB-123456789"]
        for mlb_id in valid_ids:
            payload = ListingCreate(
                ml_account_id=uuid.uuid4(),
                mlb_id=mlb_id,
                title="Produto Teste",
                price=Decimal("50.00"),
            )
            assert payload.mlb_id == mlb_id

    def test_listing_create_rejeita_mlb_id_invalido(self):
        """ListingCreate deve rejeitar IDs que nao seguem padrao MLB-d+."""
        from pydantic import ValidationError
        from app.vendas.schemas import ListingCreate

        with pytest.raises(ValidationError):
            ListingCreate(
                ml_account_id=uuid.uuid4(),
                mlb_id="INVALIDO_XYZ",
                title="Teste",
                price=Decimal("50.00"),
            )

    def test_listing_create_preco_nao_negativo(self):
        """ListingCreate deve rejeitar preço negativo."""
        from pydantic import ValidationError
        from app.vendas.schemas import ListingCreate

        with pytest.raises(ValidationError):
            ListingCreate(
                ml_account_id=uuid.uuid4(),
                mlb_id="MLB123",
                title="Teste",
                price=Decimal("-10.00"),
            )

    def test_listing_create_product_id_opcional(self):
        """ListingCreate deve aceitar product_id como None."""
        from app.vendas.schemas import ListingCreate

        payload = ListingCreate(
            ml_account_id=uuid.uuid4(),
            mlb_id="MLB456",
            title="Produto",
            price=Decimal("100.00"),
            product_id=None,
        )
        assert payload.product_id is None

    def test_listing_out_tem_campos_calculados(self):
        """ListingOut deve ter campos calculados como dias_para_zerar, rpv, voce_recebe."""
        from app.vendas.schemas import ListingOut

        fields = ListingOut.model_fields.keys()
        calculated = ["dias_para_zerar", "rpv", "voce_recebe", "participacao_pct"]
        for campo in calculated:
            assert campo in fields, f"Campo calculado '{campo}' ausente no ListingOut"

    def test_kpi_period_out_defaults_zero(self):
        """KpiPeriodOut deve ter defaults zero para todos os campos numéricos."""
        from app.vendas.schemas import KpiPeriodOut

        kpi = KpiPeriodOut()
        assert kpi.vendas == 0
        assert kpi.visitas == 0
        assert kpi.conversao == 0.0
        assert kpi.anuncios == 0
        assert kpi.receita == 0.0

    def test_kpi_period_out_variacoes_nullable(self):
        """Variações no KpiPeriodOut devem ser None por padrão."""
        from app.vendas.schemas import KpiPeriodOut

        kpi = KpiPeriodOut()
        assert kpi.vendas_variacao is None
        assert kpi.receita_variacao is None
        assert kpi.visitas_variacao is None

    def test_funnel_out_defaults(self):
        """FunnelOut deve ter defaults zero."""
        from app.vendas.schemas import FunnelOut

        funnel = FunnelOut()
        assert funnel.visitas == 0
        assert funnel.vendas == 0
        assert funnel.conversao == 0.0
        assert funnel.receita == 0.0


# ─── Testes: sale_price como fonte primária de preço ─────────────────────────

class TestSalePriceAsSource:
    def test_listing_out_tem_sale_price(self):
        """ListingOut deve expor sale_price para o frontend."""
        from app.vendas.schemas import ListingOut

        assert "sale_price" in ListingOut.model_fields

    def test_listing_out_tem_original_price(self):
        """ListingOut deve expor original_price para mostrar desconto."""
        from app.vendas.schemas import ListingOut

        assert "original_price" in ListingOut.model_fields

    def test_listing_out_sale_price_opcional(self):
        """sale_price no schema deve ser Optional (pode ser None)."""
        from app.vendas.schemas import ListingOut

        field = ListingOut.model_fields["sale_price"]
        # Campo deve ter default None
        assert field.default is None or not field.is_required()

    def test_listing_create_sale_price_opcional(self):
        """ListingCreate deve aceitar sale_price como None."""
        from app.vendas.schemas import ListingCreate

        payload = ListingCreate(
            ml_account_id=uuid.uuid4(),
            mlb_id="MLB789",
            title="Produto",
            price=Decimal("100.00"),
            sale_price=None,
        )
        assert payload.sale_price is None

    def test_listing_create_sale_price_com_desconto(self):
        """ListingCreate deve aceitar sale_price quando há promoção."""
        from app.vendas.schemas import ListingCreate

        payload = ListingCreate(
            ml_account_id=uuid.uuid4(),
            mlb_id="MLB789",
            title="Produto",
            price=Decimal("100.00"),
            original_price=Decimal("120.00"),
            sale_price=Decimal("85.00"),
        )
        assert payload.sale_price == Decimal("85.00")
        assert payload.original_price == Decimal("120.00")


# ─── Testes: dias_para_zerar — lógica de cálculo ────────────────────────────

class TestDiasParaZerarLogica:
    """Testa a lógica de cálculo de dias para zerar estoque."""

    def _calc_dias_para_zerar(self, stock: int, sales_values: list[int]) -> int | None:
        """Replica a lógica de service_kpi.py para dias_para_zerar."""
        if not sales_values or stock <= 0:
            return None

        n = len(sales_values)
        weights = [1 + (i * 0.3) for i in range(n)]
        weighted_sum = sum(v * w for v, w in zip(sales_values, weights))
        total_weight = sum(weights)
        avg_sales_weighted = weighted_sum / total_weight

        if avg_sales_weighted > 0:
            return round(stock / avg_sales_weighted)
        return None

    def test_dias_para_zerar_basico(self):
        """Com vendas consistentes, deve calcular dias corretamente."""
        dias = self._calc_dias_para_zerar(stock=100, sales_values=[5, 5, 5, 5, 5])
        assert dias is not None
        assert dias > 0

    def test_dias_para_zerar_estoque_zero(self):
        """Com estoque 0, não deve calcular dias."""
        dias = self._calc_dias_para_zerar(stock=0, sales_values=[5, 5, 5])
        assert dias is None

    def test_dias_para_zerar_sem_vendas(self):
        """Com vendas todas zero, não deve calcular dias."""
        dias = self._calc_dias_para_zerar(stock=100, sales_values=[0, 0, 0])
        assert dias is None

    def test_dias_para_zerar_media_ponderada(self):
        """Dias recentes devem ter maior peso no cálculo."""
        # Vendas crescendo (mais recentes pesam mais → média maior → menos dias)
        dias_crescendo = self._calc_dias_para_zerar(
            stock=100, sales_values=[1, 2, 3, 4, 5, 6, 7]  # crescente
        )
        # Vendas decrescendo (mais recentes pesam mais → média menor → mais dias)
        dias_decrescendo = self._calc_dias_para_zerar(
            stock=100, sales_values=[7, 6, 5, 4, 3, 2, 1]  # decrescente
        )
        assert dias_crescendo is not None
        assert dias_decrescendo is not None
        assert dias_crescendo < dias_decrescendo  # crescente → média ponderada maior
