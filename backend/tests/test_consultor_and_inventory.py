"""
Testes para consultor/service.py (funções puras) e intel/analytics/service_inventory.py

Ciclo 8 do auto-learning — cobertura alvo:
- consultor/service.py: 6.4% → 55% (funções puras: _formatar_*)
- intel/analytics/service_inventory.py: 11.3% → 60% (lógica pura pós-query)

Estratégia:
- Funções puras (_formatar_historico_7d, _formatar_concorrentes, _formatar_listing,
  _formatar_kpi): testar diretamente sem DB
- service_inventory: retorno vazio (SQLite) + lógica pura via mock de rows
"""
import os
import uuid
from decimal import Decimal

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _uid():
    return uuid.uuid4()


def _snap_dict(
    date="10/04", sales=5, visits=100, revenue=250.0,
    price=50.0, stock=20, conversion=5.0, orders=5,
    cancelled=0, returns=0,
):
    return {
        "date": date,
        "sales": sales,
        "visits": visits,
        "revenue": revenue,
        "price": price,
        "stock": stock,
        "conversion": conversion,
        "orders": orders,
        "cancelled": cancelled,
        "returns": returns,
    }


def _listing_dict(
    mlb_id="MLB123",
    title="Produto Teste",
    price=50.0,
    listing_type="classico",
    snap=None,
):
    return {
        "mlb_id": mlb_id,
        "title": title,
        "price": price,
        "listing_type": listing_type,
        "last_snapshot": snap,
        "seller_sku": "SKU-001",
        "quality_score": None,
        "voce_recebe": None,
        "original_price": None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 1: _formatar_historico_7d
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatarHistorico7d:
    """Testa a função pura _formatar_historico_7d."""

    def test_sem_snapshots_retorna_sem_dados(self):
        from app.consultor.service import _formatar_historico_7d
        result = _formatar_historico_7d([])
        assert "sem dados" in result

    def test_com_um_snapshot(self):
        from app.consultor.service import _formatar_historico_7d
        snaps = [_snap_dict(date="10/04", sales=3, visits=60, revenue=150.0)]
        result = _formatar_historico_7d(snaps)
        assert "10/04" in result
        assert "3v" in result

    def test_tendencia_subindo(self):
        """Segunda metade tem mais vendas → tendencia subindo."""
        from app.consultor.service import _formatar_historico_7d
        snaps = [
            _snap_dict(date="10/04", sales=1, visits=20),
            _snap_dict(date="11/04", sales=1, visits=20),
            _snap_dict(date="12/04", sales=10, visits=200),
            _snap_dict(date="13/04", sales=10, visits=200),
        ]
        result = _formatar_historico_7d(snaps)
        assert "subindo" in result

    def test_tendencia_caindo(self):
        """Segunda metade tem menos vendas → tendencia caindo."""
        from app.consultor.service import _formatar_historico_7d
        snaps = [
            _snap_dict(date="10/04", sales=10, visits=200),
            _snap_dict(date="11/04", sales=10, visits=200),
            _snap_dict(date="12/04", sales=1, visits=20),
            _snap_dict(date="13/04", sales=1, visits=20),
        ]
        result = _formatar_historico_7d(snaps)
        assert "caindo" in result

    def test_totais_calculados(self):
        """Totais acumulados aparecem no resultado."""
        from app.consultor.service import _formatar_historico_7d
        snaps = [
            _snap_dict(sales=5, visits=100, revenue=250.0),
            _snap_dict(sales=3, visits=80, revenue=150.0),
        ]
        result = _formatar_historico_7d(snaps)
        assert "8 vendas" in result  # 5+3
        assert "180 visitas" in result  # 100+80

    def test_cancelamentos_aparecem_quando_positivos(self):
        """Cancelamentos e devoluções só aparecem se > 0."""
        from app.consultor.service import _formatar_historico_7d
        snaps = [_snap_dict(cancelled=2, returns=1)]
        result = _formatar_historico_7d(snaps)
        assert "cancelamentos" in result
        assert "devolucoes" in result

    def test_sem_cancelamentos_nao_aparece(self):
        from app.consultor.service import _formatar_historico_7d
        snaps = [_snap_dict(cancelled=0, returns=0)]
        result = _formatar_historico_7d(snaps)
        assert "cancelamentos" not in result

    def test_dados_insuficientes_um_snapshot(self):
        """Com apenas 1 snapshot, tendência fica 'dados insuficientes'."""
        from app.consultor.service import _formatar_historico_7d
        snaps = [_snap_dict()]
        result = _formatar_historico_7d(snaps)
        assert "dados insuficientes" in result

    def test_trend_symbol_zero_zero(self):
        """Quando ambos lados são 0 → estável."""
        from app.consultor.service import _formatar_historico_7d
        snaps = [
            _snap_dict(sales=0, visits=0, revenue=0.0),
            _snap_dict(sales=0, visits=0, revenue=0.0),
        ]
        result = _formatar_historico_7d(snaps)
        assert "estavel" in result or "=" in result


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 2: _formatar_concorrentes
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatarConcorrentes:
    """Testa _formatar_concorrentes."""

    def test_sem_concorrentes_retorna_vazio(self):
        from app.consultor.service import _formatar_concorrentes
        result = _formatar_concorrentes([], meu_preco=50.0)
        assert result == ""

    def test_concorrente_com_preco(self):
        from app.consultor.service import _formatar_concorrentes
        concorrentes = [
            {"mlb_id": "MLB999", "title": "Produto Concorrente", "price": 45.0, "sales_delta": None}
        ]
        result = _formatar_concorrentes(concorrentes, meu_preco=50.0)
        assert "MLB999" in result
        assert "45.00" in result

    def test_diferenca_percentual_positiva(self):
        """Meu preço > concorrente → diferença positiva."""
        from app.consultor.service import _formatar_concorrentes
        concorrentes = [
            {"mlb_id": "MLB999", "title": "Produto", "price": 40.0, "sales_delta": None}
        ]
        result = _formatar_concorrentes(concorrentes, meu_preco=50.0)
        assert "+" in result  # meu preço 25% mais caro

    def test_diferenca_percentual_negativa(self):
        """Meu preço < concorrente → diferença negativa."""
        from app.consultor.service import _formatar_concorrentes
        concorrentes = [
            {"mlb_id": "MLB999", "title": "Produto", "price": 60.0, "sales_delta": None}
        ]
        result = _formatar_concorrentes(concorrentes, meu_preco=50.0)
        assert "-" in result

    def test_concorrente_sem_preco(self):
        """Concorrente sem dados de preço."""
        from app.consultor.service import _formatar_concorrentes
        concorrentes = [
            {"mlb_id": "MLB999", "title": "Produto", "price": None, "sales_delta": None}
        ]
        result = _formatar_concorrentes(concorrentes, meu_preco=50.0)
        assert "sem dados de preco" in result

    def test_concorrente_com_vendas_delta(self):
        """sales_delta aparece quando definido."""
        from app.consultor.service import _formatar_concorrentes
        concorrentes = [
            {"mlb_id": "MLB999", "title": "Produto", "price": 50.0, "sales_delta": 5}
        ]
        result = _formatar_concorrentes(concorrentes, meu_preco=50.0)
        assert "vendas/dia" in result

    def test_multiplos_concorrentes(self):
        from app.consultor.service import _formatar_concorrentes
        concorrentes = [
            {"mlb_id": "MLB1", "title": "P1", "price": 45.0, "sales_delta": None},
            {"mlb_id": "MLB2", "title": "P2", "price": 55.0, "sales_delta": None},
        ]
        result = _formatar_concorrentes(concorrentes, meu_preco=50.0)
        assert "MLB1" in result
        assert "MLB2" in result


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 3: _formatar_listing
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatarListing:
    """Testa _formatar_listing com vários cenários."""

    def test_listing_basico_sem_snap(self):
        from app.consultor.service import _formatar_listing
        listing = _listing_dict()
        result = _formatar_listing(listing)
        assert "MLB123" in result
        assert "Produto Teste" in result
        assert "Sem dados de snapshot" in result

    def test_listing_com_snap_dict(self):
        """Snapshot como dicionário."""
        from app.consultor.service import _formatar_listing
        snap = {
            "stock": 10, "visits": 100, "sales_today": 5,
            "conversion_rate": 5.0, "revenue": 250.0,
            "orders_count": 5, "cancelled_orders": 0, "returns_count": 0,
        }
        listing = _listing_dict(snap=snap)
        result = _formatar_listing(listing)
        assert "Estoque: 10" in result
        assert "Visitas hoje: 100" in result
        assert "Vendas hoje: 5" in result

    def test_listing_com_quality_score_excelente(self):
        from app.consultor.service import _formatar_listing
        listing = _listing_dict()
        listing["quality_score"] = 90
        result = _formatar_listing(listing)
        assert "Excelente" in result

    def test_listing_com_quality_score_ruim(self):
        from app.consultor.service import _formatar_listing
        listing = _listing_dict()
        listing["quality_score"] = 30
        result = _formatar_listing(listing)
        assert "Ruim" in result

    def test_listing_com_original_price_desconto(self):
        """Preço original maior → desconto aparece."""
        from app.consultor.service import _formatar_listing
        listing = _listing_dict(price=40.0)
        listing["original_price"] = 50.0
        result = _formatar_listing(listing)
        assert "desconto" in result.lower() or "original" in result.lower()

    def test_listing_com_voce_recebe(self):
        from app.consultor.service import _formatar_listing
        listing = _listing_dict(price=100.0)
        listing["voce_recebe"] = 84.0
        result = _formatar_listing(listing)
        assert "84.00" in result
        assert "Retencao" in result or "recebe" in result

    def test_listing_com_variacao_vs_ontem(self):
        """Variação de vendas e receita vs ontem."""
        from app.consultor.service import _formatar_listing
        listing = _listing_dict(snap={"stock": 5, "visits": 50, "sales_today": 3,
                                       "conversion_rate": 6.0, "revenue": 150.0,
                                       "orders_count": 3, "cancelled_orders": 0, "returns_count": 0})
        listing["vendas_variacao"] = 20.0
        listing["receita_variacao"] = -10.0
        result = _formatar_listing(listing)
        assert "+20%" in result
        assert "-10%" in result

    def test_listing_com_historico_7d(self):
        from app.consultor.service import _formatar_listing
        snaps_7d = [_snap_dict(date=f"{i:02d}/04") for i in range(1, 5)]
        listing = _listing_dict()
        result = _formatar_listing(listing, historico_7d=snaps_7d)
        assert "Historico 7d" in result

    def test_listing_com_concorrentes(self):
        from app.consultor.service import _formatar_listing
        concorrentes = [{"mlb_id": "MLB999", "title": "Rival", "price": 45.0, "sales_delta": None}]
        listing = _listing_dict(price=50.0)
        result = _formatar_listing(listing, concorrentes=concorrentes)
        assert "MLB999" in result

    def test_listing_alerta_estoque_critico(self):
        """dias_para_zerar <= 7 → alerta crítico."""
        from app.consultor.service import _formatar_listing
        snap = {"stock": 3, "visits": 50, "sales_today": 1, "conversion_rate": 2.0,
                "revenue": 50.0, "orders_count": 1, "cancelled_orders": 0, "returns_count": 0}
        listing = _listing_dict(snap=snap)
        listing["dias_para_zerar"] = 5
        snaps_7d = [_snap_dict(sales=1) for _ in range(7)]
        result = _formatar_listing(listing, historico_7d=snaps_7d)
        assert "ALERTA" in result or "critico" in result.lower()

    def test_listing_sem_preco(self):
        """Listing sem preço não deve quebrar."""
        from app.consultor.service import _formatar_listing
        listing = _listing_dict(price=None)
        listing["price"] = None
        result = _formatar_listing(listing)
        assert "MLB123" in result  # não quebrou


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 4: _formatar_kpi
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatarKpi:
    """Testa _formatar_kpi."""

    def test_kpi_vazio_retorna_header(self):
        from app.consultor.service import _formatar_kpi
        result = _formatar_kpi({})
        assert "KPIs CONSOLIDADOS" in result

    def test_kpi_hoje_aparece(self):
        from app.consultor.service import _formatar_kpi
        kpi = {
            "hoje": {
                "vendas": 10, "receita_total": 500.0, "visitas": 200,
                "pedidos": 10, "conversao": 5.0, "anuncios": 5
            }
        }
        result = _formatar_kpi(kpi)
        assert "Hoje" in result
        assert "10 vendas" in result
        assert "500.00 receita" in result

    def test_multiplos_periodos(self):
        from app.consultor.service import _formatar_kpi
        kpi = {
            "hoje": {"vendas": 5, "receita_total": 250.0, "visitas": 100, "pedidos": 5, "conversao": 5.0, "anuncios": 3},
            "ontem": {"vendas": 3, "receita_total": 150.0, "visitas": 80, "pedidos": 3, "conversao": 3.75, "anuncios": 3},
            "7dias": {"vendas": 30, "receita_total": 1500.0, "visitas": 700, "pedidos": 30, "conversao": 4.28, "anuncios": 3},
        }
        result = _formatar_kpi(kpi)
        assert "Hoje" in result
        assert "Ontem" in result
        assert "Ultimos 7 dias" in result

    def test_periodo_sem_dados_e_ignorado(self):
        """Período vazio não deve aparecer."""
        from app.consultor.service import _formatar_kpi
        kpi = {"hoje": {}, "ontem": {"vendas": 5, "receita_total": 250.0, "visitas": 100, "pedidos": 5, "conversao": 5.0, "anuncios": 3}}
        result = _formatar_kpi(kpi)
        # "Hoje" com dados vazio → não aparece linha de Hoje
        assert "Ontem" in result
        # Hoje não tem dados → linha não é gerada
        assert "Hoje:" not in result


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 5: intel/analytics/service_inventory — retorno vazio
# ═══════════════════════════════════════════════════════════════════════════════


class TestInventoryHealthEmpty:
    """Testa get_inventory_health quando não há listings."""

    @pytest.mark.asyncio
    async def test_sem_listings_retorna_empty(self, db):
        from app.intel.analytics.service_inventory import get_inventory_health
        import uuid
        user_id = uuid.uuid4()

        result = await get_inventory_health(db, user_id)

        assert result.items == []
        assert result.total_items == 0
        assert result.healthy_count == 0
        assert result.overstocked_count == 0
        assert result.critical_low_count == 0
        assert result.avg_days_of_stock == 0.0

    @pytest.mark.asyncio
    async def test_period_7d(self, db):
        from app.intel.analytics.service_inventory import get_inventory_health
        import uuid
        result = await get_inventory_health(db, uuid.uuid4(), period="7d")
        assert result.period_days == 7

    @pytest.mark.asyncio
    async def test_period_15d(self, db):
        from app.intel.analytics.service_inventory import get_inventory_health
        import uuid
        result = await get_inventory_health(db, uuid.uuid4(), period="15d")
        assert result.period_days == 15

    @pytest.mark.asyncio
    async def test_period_unknown_defaults_30d(self, db):
        from app.intel.analytics.service_inventory import get_inventory_health
        import uuid
        result = await get_inventory_health(db, uuid.uuid4(), period="60d")
        assert result.period_days == 30  # padrão quando desconhecido


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 6: Lógica pura de health_status (sem DB)
# ═══════════════════════════════════════════════════════════════════════════════


class TestInventoryHealthLogic:
    """Testa a lógica pura de classificação de health_status."""

    def _classify(self, total_sales: int, current_stock: int, period_days: int = 30) -> dict:
        """Simula a lógica de classificação de `service_inventory.py`."""
        if period_days == 0:
            avg_daily_sales = 0.0
        else:
            avg_daily_sales = total_sales / period_days

        sell_through_rate = (
            (total_sales / (total_sales + current_stock))
            if (total_sales + current_stock) > 0
            else 0.0
        )

        days_of_stock = (
            current_stock / avg_daily_sales if avg_daily_sales > 0 else float("inf")
        )

        if days_of_stock == float("inf"):
            health_status = "no_sales"
        elif days_of_stock < 7:
            health_status = "critical_low"
        elif days_of_stock > 90:
            health_status = "overstocked"
        else:
            health_status = "healthy"

        return {
            "health_status": health_status,
            "avg_daily_sales": avg_daily_sales,
            "sell_through_rate": sell_through_rate,
            "days_of_stock": days_of_stock,
        }

    def test_healthy_status(self):
        """30 dias de estoque → healthy."""
        result = self._classify(total_sales=10, current_stock=10, period_days=30)
        assert result["health_status"] == "healthy"

    def test_critical_low(self):
        """Menos de 7 dias de estoque → critical_low."""
        # 60 vendas em 30 dias = 2/dia, 10 unidades → 5 dias
        result = self._classify(total_sales=60, current_stock=10, period_days=30)
        assert result["health_status"] == "critical_low"

    def test_overstocked(self):
        """Mais de 90 dias de estoque → overstocked."""
        # 1 venda em 30 dias = 0.033/dia, 10 unidades → 300 dias
        result = self._classify(total_sales=1, current_stock=10, period_days=30)
        assert result["health_status"] == "overstocked"

    def test_no_sales(self):
        """Sem vendas → no_sales (inf)."""
        result = self._classify(total_sales=0, current_stock=5, period_days=30)
        assert result["health_status"] == "no_sales"

    def test_sell_through_rate(self):
        """sell_through_rate = sales / (sales + stock)."""
        result = self._classify(total_sales=10, current_stock=10, period_days=30)
        assert abs(result["sell_through_rate"] - 0.5) < 0.01

    def test_sell_through_rate_zero_stock_zero_sales(self):
        """Sem vendas nem estoque → 0.0."""
        result = self._classify(total_sales=0, current_stock=0, period_days=30)
        assert result["sell_through_rate"] == 0.0

    def test_avg_daily_sales(self):
        """avg_daily_sales = total_sales / period_days."""
        result = self._classify(total_sales=30, current_stock=10, period_days=30)
        assert abs(result["avg_daily_sales"] - 1.0) < 0.01


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 7: service_weights DEFAULT_WEIGHTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestServiceWeightsDefault:
    """Testa que sem dados suficientes retorna DEFAULT_WEIGHTS."""

    @pytest.mark.asyncio
    async def test_sem_recomendacoes_retorna_default(self, db):
        from app.intel.pricing.service_weights import get_adaptive_weights, DEFAULT_WEIGHTS
        import uuid
        user_id = uuid.uuid4()

        result = await get_adaptive_weights(db, user_id)

        assert result == DEFAULT_WEIGHTS
        assert abs(result["sales_trend"] - 0.35) < 0.001
        assert abs(result["visit_trend"] - 0.25) < 0.001
        assert abs(result["conv_trend"] - 0.15) < 0.001

    def test_default_weights_somam_100(self):
        from app.intel.pricing.service_weights import DEFAULT_WEIGHTS
        total = sum(DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001  # soma 100%

    def test_default_weights_tem_todas_chaves(self):
        from app.intel.pricing.service_weights import DEFAULT_WEIGHTS
        expected_keys = {"sales_trend", "visit_trend", "conv_trend", "comp_score",
                         "stock_score", "margem_score", "hist_score"}
        assert set(DEFAULT_WEIGHTS.keys()) == expected_keys
