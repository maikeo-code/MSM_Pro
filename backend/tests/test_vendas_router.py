"""
Testes de rotas e schemas para o módulo vendas.

Estratégia:
- Testa schemas de input/output diretamente (sem HTTP)
- Testa validações de query parameters
- Testa KpiPeriodOut, HeatmapOut, FunnelOut
- Sem importar app.main (evita inicialização de engines e celery)
"""
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

import pytest

BRT = timezone(timedelta(hours=-3))


# ─── Testes: KpiPeriodOut ────────────────────────────────────────────────────

class TestKpiPeriodOut:
    def test_kpi_period_out_instancia_com_defaults(self):
        """KpiPeriodOut deve poder ser instanciado com todos os defaults."""
        from app.vendas.schemas import KpiPeriodOut
        kpi = KpiPeriodOut()
        assert kpi.vendas == 0
        assert kpi.visitas == 0
        assert kpi.conversao == 0.0
        assert kpi.anuncios == 0
        assert kpi.valor_estoque == 0.0
        assert kpi.receita == 0.0

    def test_kpi_period_out_com_dados_reais(self):
        """KpiPeriodOut deve aceitar dados válidos."""
        from app.vendas.schemas import KpiPeriodOut
        kpi = KpiPeriodOut(
            vendas=15,
            visitas=500,
            conversao=3.0,
            anuncios=5,
            valor_estoque=5000.0,
            receita=1500.0,
            pedidos=12,
            receita_total=1400.0,
            preco_medio=116.67,
            taxa_cancelamento=5.0,
        )
        assert kpi.vendas == 15
        assert kpi.visitas == 500
        assert kpi.anuncios == 5

    def test_kpi_period_out_variacoes_none_por_padrao(self):
        """Variações devem ser None quando não há período anterior."""
        from app.vendas.schemas import KpiPeriodOut
        kpi = KpiPeriodOut()
        assert kpi.vendas_variacao is None
        assert kpi.receita_variacao is None
        assert kpi.visitas_variacao is None
        assert kpi.conversao_variacao is None

    def test_kpi_period_out_variacoes_positivas(self):
        """Variações positivas devem ser aceitas."""
        from app.vendas.schemas import KpiPeriodOut
        kpi = KpiPeriodOut(
            vendas_variacao=25.5,
            receita_variacao=10.2,
        )
        assert kpi.vendas_variacao == 25.5
        assert kpi.receita_variacao == 10.2

    def test_kpi_period_out_variacoes_negativas(self):
        """Variações negativas (queda) devem ser aceitas."""
        from app.vendas.schemas import KpiPeriodOut
        kpi = KpiPeriodOut(
            vendas_variacao=-15.0,
            receita_variacao=-8.3,
        )
        assert kpi.vendas_variacao == -15.0

    def test_kpi_tem_campos_novos(self):
        """KpiPeriodOut deve ter campos de cancelamentos e devoluções."""
        from app.vendas.schemas import KpiPeriodOut
        fields = set(KpiPeriodOut.model_fields.keys())
        novos_campos = {"cancelamentos_valor", "devolucoes_valor", "devolucoes_qtd", "vendas_concluidas"}
        assert novos_campos.issubset(fields)


# ─── Testes: HeatmapOut ──────────────────────────────────────────────────────

class TestHeatmapOut:
    def _make_heatmap_cell(self, day=0, hour=10, count=5):
        from app.vendas.schemas import HeatmapCell
        return HeatmapCell(
            day_of_week=day,
            hour=hour,
            day_name="Segunda-feira",
            count=count,
            avg_per_week=2.5,
        )

    def test_heatmap_cell_valida(self):
        """HeatmapCell deve aceitar dados válidos."""
        from app.vendas.schemas import HeatmapCell
        cell = HeatmapCell(
            day_of_week=0,
            hour=14,
            day_name="Segunda-feira",
            count=10,
            avg_per_week=3.5,
        )
        assert cell.day_of_week == 0
        assert cell.hour == 14
        assert cell.count == 10

    def test_heatmap_out_completo(self):
        """HeatmapOut deve aceitar estrutura completa."""
        from app.vendas.schemas import HeatmapOut, HeatmapCell
        cells = [
            HeatmapCell(day_of_week=i, hour=10, day_name="Dia", count=i, avg_per_week=1.0)
            for i in range(7)
        ]
        heatmap = HeatmapOut(
            period_days=30,
            total_sales=150,
            avg_daily=5.0,
            peak_day="Quarta-feira",
            peak_day_index=2,
            peak_hour="14:00-15:00",
            has_hourly_data=True,
            data=cells,
        )
        assert heatmap.period_days == 30
        assert heatmap.total_sales == 150
        assert len(heatmap.data) == 7

    def test_heatmap_out_sem_dados_hourly(self):
        """HeatmapOut deve aceitar has_hourly_data=False (fallback)."""
        from app.vendas.schemas import HeatmapOut
        heatmap = HeatmapOut(
            period_days=7,
            total_sales=0,
            avg_daily=0.0,
            peak_day="",
            peak_day_index=0,
            peak_hour="",
            has_hourly_data=False,
            data=[],
        )
        assert heatmap.has_hourly_data is False
        assert heatmap.data == []

    def test_heatmap_cell_day_of_week_range(self):
        """day_of_week deve representar 0=segunda até 6=domingo."""
        from app.vendas.schemas import HeatmapCell
        days = ["Segunda-feira", "Terca-feira", "Quarta-feira",
                "Quinta-feira", "Sexta-feira", "Sabado", "Domingo"]
        for i, day_name in enumerate(days):
            cell = HeatmapCell(
                day_of_week=i,
                hour=0,
                day_name=day_name,
                count=0,
                avg_per_week=0.0,
            )
            assert cell.day_of_week == i


# ─── Testes: FunnelOut ───────────────────────────────────────────────────────

class TestFunnelOut:
    def test_funnel_out_defaults_zero(self):
        """FunnelOut deve ter defaults zero."""
        from app.vendas.schemas import FunnelOut
        funnel = FunnelOut()
        assert funnel.visitas == 0
        assert funnel.vendas == 0
        assert funnel.conversao == 0.0
        assert funnel.receita == 0.0

    def test_funnel_out_com_dados(self):
        """FunnelOut deve aceitar dados válidos."""
        from app.vendas.schemas import FunnelOut
        funnel = FunnelOut(
            visitas=1000,
            vendas=25,
            conversao=2.5,
            receita=2500.0,
        )
        assert funnel.visitas == 1000
        assert funnel.conversao == 2.5

    def test_funnel_conversao_zero_sem_visitas(self):
        """Conversão deve ser 0 quando não há visitas."""
        from app.vendas.schemas import FunnelOut
        funnel = FunnelOut(visitas=0, vendas=0, conversao=0.0, receita=0.0)
        assert funnel.conversao == 0.0


# ─── Testes: KpiCompareOut ───────────────────────────────────────────────────

class TestKpiCompareOut:
    def test_kpi_compare_out_estrutura(self):
        """KpiCompareOut deve ter period_a, period_b, variacao."""
        from app.vendas.schemas import KpiCompareOut

        compare = KpiCompareOut(
            period_a={"vendas": 100, "receita": 5000.0},
            period_b={"vendas": 80, "receita": 4000.0},
            period_a_label="Últimos 7 dias",
            period_b_label="7 dias anteriores",
            variacao={"vendas": 25.0, "receita": 25.0},
        )
        assert compare.period_a["vendas"] == 100
        assert compare.period_b["vendas"] == 80
        assert compare.variacao["vendas"] == 25.0

    def test_kpi_compare_variacao_negativa(self):
        """Variação negativa (queda) deve ser representada."""
        from app.vendas.schemas import KpiCompareOut
        compare = KpiCompareOut(
            period_a={"vendas": 60},
            period_b={"vendas": 100},
            period_a_label="Atual",
            period_b_label="Anterior",
            variacao={"vendas": -40.0},
        )
        assert compare.variacao["vendas"] == -40.0


# ─── Testes: ListingOut campos calculados ────────────────────────────────────

class TestListingOutSchema:
    def _make_listing_out_data(self, **overrides):
        now = datetime.now(BRT)
        base = {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "product_id": None,
            "ml_account_id": uuid.uuid4(),
            "mlb_id": "MLB100",
            "title": "Produto Teste",
            "listing_type": "classico",
            "price": Decimal("100.00"),
            "status": "active",
            "permalink": None,
            "thumbnail": None,
            "created_at": now,
            "updated_at": now,
        }
        base.update(overrides)
        return base

    def test_listing_out_sem_snapshot(self):
        """ListingOut deve aceitar last_snapshot=None."""
        from app.vendas.schemas import ListingOut
        data = self._make_listing_out_data(last_snapshot=None)
        out = ListingOut(**data)
        assert out.last_snapshot is None

    def test_listing_out_campos_calculados_nullable(self):
        """Campos calculados devem ser None quando não calculados."""
        from app.vendas.schemas import ListingOut
        data = self._make_listing_out_data()
        out = ListingOut(**data)
        assert out.dias_para_zerar is None
        assert out.rpv is None
        assert out.voce_recebe is None
        assert out.participacao_pct is None

    def test_listing_out_com_voce_recebe(self):
        """ListingOut deve aceitar voce_recebe calculado."""
        from app.vendas.schemas import ListingOut
        data = self._make_listing_out_data(voce_recebe=83.0)
        out = ListingOut(**data)
        assert out.voce_recebe == 83.0

    def test_listing_out_com_sale_price(self):
        """ListingOut deve expor sale_price quando há promoção."""
        from app.vendas.schemas import ListingOut
        data = self._make_listing_out_data(
            price=Decimal("100.00"),
            original_price=Decimal("120.00"),
            sale_price=Decimal("85.00"),
        )
        out = ListingOut(**data)
        assert out.sale_price == Decimal("85.00")
        assert out.original_price == Decimal("120.00")

    def test_listing_out_variacao_fields(self):
        """ListingOut deve ter campos de variação de vendas e receita."""
        from app.vendas.schemas import ListingOut
        data = self._make_listing_out_data(
            vendas_variacao=15.5,
            receita_variacao=-5.0,
        )
        out = ListingOut(**data)
        assert out.vendas_variacao == 15.5
        assert out.receita_variacao == -5.0

    def test_listing_out_avg_visits_per_day(self):
        """ListingOut deve ter avg_visits_per_day para períodos multi-dia."""
        from app.vendas.schemas import ListingOut
        data = self._make_listing_out_data(avg_visits_per_day=142.5)
        out = ListingOut(**data)
        assert out.avg_visits_per_day == 142.5


# ─── Testes: validações de query parameters (simuladas) ─────────────────────

class TestQueryParameterValidation:
    """Testa lógica de validação de parâmetros das rotas."""

    VALID_PERIODS = ["today", "yesterday", "before_yesterday", "7d", "15d", "30d", "60d"]
    INVALID_PERIODS = ["1d", "100d", "week", "month", "", "null"]

    def test_periodos_validos_aceitos(self):
        """Lista de períodos válidos definidos no router."""
        import re
        pattern = r"^(today|yesterday|before_yesterday|7d|15d|30d|60d)$"
        for period in self.VALID_PERIODS:
            assert re.match(pattern, period) is not None, f"{period} deveria ser válido"

    def test_periodos_invalidos_rejeitados(self):
        """Períodos inválidos devem falhar na validação."""
        import re
        pattern = r"^(today|yesterday|before_yesterday|7d|15d|30d|60d)$"
        for period in self.INVALID_PERIODS:
            assert re.match(pattern, period) is None, f"{period} deveria ser inválido"

    def test_periodos_validos_funnel(self):
        """Períodos válidos para funil: 7d, 15d, 30d, 60d."""
        import re
        pattern = r"^(7d|15d|30d|60d)$"
        valid = ["7d", "15d", "30d", "60d"]
        invalid = ["today", "yesterday", "1d", "90d"]
        for p in valid:
            assert re.match(pattern, p) is not None
        for p in invalid:
            assert re.match(pattern, p) is None

    def test_periodos_validos_heatmap(self):
        """Períodos válidos para heatmap: 7d, 15d, 30d, 60d, 90d."""
        import re
        pattern = r"^(7d|15d|30d|60d|90d)$"
        valid = ["7d", "15d", "30d", "60d", "90d"]
        for p in valid:
            assert re.match(pattern, p) is not None

    def test_periodos_validos_kpi_compare(self):
        """Períodos válidos para compare: 7d, 15d, 30d."""
        import re
        pattern_a = r"^(7d|15d|30d)$"
        valid = ["7d", "15d", "30d"]
        for p in valid:
            assert re.match(pattern_a, p) is not None

    def test_mlb_id_pattern_valido(self):
        """MLB IDs validos devem seguir padrao MLB-?[0-9]+."""
        import re
        pattern = r"^MLB-?\d+$"
        valid = ["MLB123", "MLB-123456789", "MLB1"]
        invalid = ["INVALIDO", "ml123", "MLB", "MLB-", "123"]
        for mid in valid:
            assert re.match(pattern, mid) is not None, f"{mid} deveria ser válido"
        for mid in invalid:
            assert re.match(pattern, mid) is None, f"{mid} deveria ser inválido"


# ─── Testes: SnapshotOut schema ──────────────────────────────────────────────

class TestSnapshotOut:
    def _make_snapshot_data(self, **overrides):
        now = datetime.now(BRT)
        base = {
            "id": uuid.uuid4(),
            "listing_id": uuid.uuid4(),
            "price": Decimal("100.00"),
            "visits": 200,
            "sales_today": 5,
            "questions": 2,
            "stock": 50,
            "conversion_rate": None,
            "captured_at": now,
        }
        base.update(overrides)
        return base

    def test_snapshot_out_valido(self):
        """SnapshotOut deve aceitar dados válidos."""
        from app.vendas.schemas import SnapshotOut
        data = self._make_snapshot_data()
        out = SnapshotOut(**data)
        assert out.visits == 200
        assert out.sales_today == 5

    def test_snapshot_out_conversion_rate_nullable(self):
        """conversion_rate deve ser aceita como None."""
        from app.vendas.schemas import SnapshotOut
        data = self._make_snapshot_data(conversion_rate=None)
        out = SnapshotOut(**data)
        assert out.conversion_rate is None

    def test_snapshot_out_revenue_nullable(self):
        """revenue deve ser aceita como None."""
        from app.vendas.schemas import SnapshotOut
        data = self._make_snapshot_data(revenue=None)
        out = SnapshotOut(**data)
        assert out.revenue is None

    def test_snapshot_out_com_todos_campos(self):
        """SnapshotOut deve aceitar todos os campos opcionais preenchidos."""
        from app.vendas.schemas import SnapshotOut
        data = self._make_snapshot_data(
            conversion_rate=Decimal("2.50"),
            orders_count=5,
            revenue=500.0,
            avg_selling_price=100.0,
            cancelled_orders=1,
            cancelled_revenue=100.0,
            returns_count=0,
            returns_revenue=0.0,
        )
        out = SnapshotOut(**data)
        assert out.orders_count == 5
        assert float(out.conversion_rate) == pytest.approx(2.5)
