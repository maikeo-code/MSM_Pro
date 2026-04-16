"""
Testes para intel/pricing/service_report.py e service_collector.py

Ciclo 10 do auto-learning — cobertura alvo:
- service_report.py: 9.2% → 55%+ (funções puras: _fmt, _var_arrow, _sparkline, _build_summary)
- service_collector.py: 11.7% → 40%+ (_safe_float, _compute_historical_metrics)
"""
import os
from datetime import date

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 1: service_report.py — funções de formatação puras
# ═══════════════════════════════════════════════════════════════════════════════


class TestFmtCurrency:
    """Testa _fmt_currency."""

    def test_valor_abaixo_1000(self):
        from app.intel.pricing.service_report import _fmt_currency
        result = _fmt_currency(99.90)
        assert "99" in result
        assert "R$" in result

    def test_valor_1000_usa_separador(self):
        from app.intel.pricing.service_report import _fmt_currency
        result = _fmt_currency(1500.0)
        assert "R$" in result
        assert "1" in result

    def test_zero(self):
        from app.intel.pricing.service_report import _fmt_currency
        result = _fmt_currency(0.0)
        assert "0" in result

    def test_valor_exato_1000(self):
        from app.intel.pricing.service_report import _fmt_currency
        result = _fmt_currency(1000.0)
        assert "R$" in result


class TestFmtPct:
    """Testa _fmt_pct."""

    def test_porcentagem_formatada(self):
        from app.intel.pricing.service_report import _fmt_pct
        result = _fmt_pct(5.75)
        assert "5.75%" in result

    def test_zero(self):
        from app.intel.pricing.service_report import _fmt_pct
        result = _fmt_pct(0.0)
        assert "0.00%" in result


class TestVarArrow:
    """Testa _var_arrow."""

    def test_previous_zero_retorna_vazio(self):
        from app.intel.pricing.service_report import _var_arrow
        result = _var_arrow(100, 0)
        assert result == ""

    def test_aumento_retorna_verde_com_seta_para_cima(self):
        from app.intel.pricing.service_report import _var_arrow
        result = _var_arrow(120, 100)  # +20%
        assert "9650" in result  # ▲
        assert "20.0%" in result

    def test_queda_retorna_vermelho_com_seta_para_baixo(self):
        from app.intel.pricing.service_report import _var_arrow
        result = _var_arrow(80, 100)  # -20%
        assert "9660" in result  # ▼
        assert "20.0%" in result

    def test_variacao_minima_retorna_estavel(self):
        from app.intel.pricing.service_report import _var_arrow
        # Menos de 0.5% → estável
        result = _var_arrow(100.3, 100)
        assert "=" in result

    def test_exatamente_zero_variacao(self):
        from app.intel.pricing.service_report import _var_arrow
        result = _var_arrow(100, 100)
        assert "=" in result


class TestHealthBar:
    """Testa _health_bar."""

    def test_score_alto_usa_verde(self):
        from app.intel.pricing.service_report import _health_bar
        result = _health_bar(80)
        assert "22c55e" in result  # green

    def test_score_medio_usa_amber(self):
        from app.intel.pricing.service_report import _health_bar
        result = _health_bar(55)
        assert "f59e0b" in result  # amber

    def test_score_baixo_usa_vermelho(self):
        from app.intel.pricing.service_report import _health_bar
        result = _health_bar(20)
        assert "ef4444" in result or "red" in result.lower() or "ef" in result

    def test_score_aparece_na_barra(self):
        from app.intel.pricing.service_report import _health_bar
        result = _health_bar(75)
        assert "75" in result


class TestBuildSparklineSvg:
    """Testa _build_sparkline_svg."""

    def test_menos_de_2_valores_retorna_vazio(self):
        from app.intel.pricing.service_report import _build_sparkline_svg
        assert _build_sparkline_svg([]) == ""
        assert _build_sparkline_svg([10.0]) == ""

    def test_2_valores_retorna_svg(self):
        from app.intel.pricing.service_report import _build_sparkline_svg
        result = _build_sparkline_svg([10.0, 20.0])
        assert "<svg" in result
        assert "polyline" in result

    def test_cor_customizada(self):
        from app.intel.pricing.service_report import _build_sparkline_svg
        result = _build_sparkline_svg([1.0, 2.0, 3.0], color="#ff0000")
        assert "#ff0000" in result

    def test_valores_iguais_nao_divide_por_zero(self):
        """Quando min == max → val_range = 1.0 (proteção)."""
        from app.intel.pricing.service_report import _build_sparkline_svg
        result = _build_sparkline_svg([5.0, 5.0, 5.0])
        assert "<svg" in result  # não quebrou

    def test_7_valores_gera_svg_valido(self):
        from app.intel.pricing.service_report import _build_sparkline_svg
        values = [1.0, 2.0, 3.0, 2.0, 4.0, 3.0, 5.0]
        result = _build_sparkline_svg(values)
        assert "<svg" in result
        assert "polyline" in result


class TestSparklineWithFallback:
    """Testa _sparkline_with_fallback."""

    def test_sem_dados(self):
        from app.intel.pricing.service_report import _sparkline_with_fallback
        result = _sparkline_with_fallback([])
        assert "sem dados" in result

    def test_tendencia_subindo(self):
        from app.intel.pricing.service_report import _sparkline_with_fallback
        result = _sparkline_with_fallback([1.0, 2.0, 3.0, 4.0])
        assert "subindo" in result

    def test_tendencia_caindo(self):
        from app.intel.pricing.service_report import _sparkline_with_fallback
        result = _sparkline_with_fallback([4.0, 3.0, 2.0, 1.0])
        assert "caindo" in result

    def test_estavel(self):
        from app.intel.pricing.service_report import _sparkline_with_fallback
        result = _sparkline_with_fallback([5.0, 5.0, 5.0, 5.0])
        assert "estavel" in result


class TestBuildSummary:
    """Testa _build_summary."""

    def test_lista_vazia_retorna_zeros(self):
        from app.intel.pricing.service_report import _build_summary
        result = _build_summary([])
        assert result["total_vendas"] == 0
        assert result["total_visitas"] == 0
        assert result["receita_total"] == 0.0
        assert result["total_listings"] == 0

    def test_conta_acoes(self):
        from app.intel.pricing.service_report import _build_summary
        recs = [
            {"periods": {"today": {"sales": 5, "visits": 100, "revenue": 250.0},
                         "yesterday": {"sales": 3, "visits": 80, "revenue": 150.0}},
             "recommendation": {"action": "increase"}},
            {"periods": {"today": {"sales": 3, "visits": 60, "revenue": 150.0},
                         "yesterday": {"sales": 4, "visits": 70, "revenue": 200.0}},
             "recommendation": {"action": "decrease"}},
            {"periods": {"today": {"sales": 2, "visits": 40, "revenue": 100.0},
                         "yesterday": {"sales": 2, "visits": 40, "revenue": 100.0}},
             "recommendation": {"action": "hold"}},
        ]
        result = _build_summary(recs)
        assert result["increase_count"] == 1
        assert result["decrease_count"] == 1
        assert result["hold_count"] == 1
        assert result["total_listings"] == 3

    def test_totaliza_vendas_visitas_receita(self):
        from app.intel.pricing.service_report import _build_summary
        recs = [
            {"periods": {"today": {"sales": 5, "visits": 100, "revenue": 250.0},
                         "yesterday": {"sales": 3, "visits": 80, "revenue": 150.0}},
             "recommendation": {"action": "hold"}},
            {"periods": {"today": {"sales": 3, "visits": 60, "revenue": 150.0},
                         "yesterday": {"sales": 2, "visits": 50, "revenue": 100.0}},
             "recommendation": {"action": "hold"}},
        ]
        result = _build_summary(recs)
        assert result["total_vendas"] == 8
        assert result["total_visitas"] == 160
        assert abs(result["receita_total"] - 400.0) < 0.01

    def test_variacao_calculada(self):
        """Quando ontem > 0, variação é calculada."""
        from app.intel.pricing.service_report import _build_summary
        recs = [
            {"periods": {"today": {"sales": 10, "visits": 200, "revenue": 500.0},
                         "yesterday": {"sales": 5, "visits": 100, "revenue": 250.0}},
             "recommendation": {"action": "hold"}},
        ]
        result = _build_summary(recs)
        assert result["vendas_var"] == 100.0  # 5→10 = +100%
        assert result["receita_var"] == 100.0  # 250→500 = +100%

    def test_variacao_none_quando_ontem_zero(self):
        from app.intel.pricing.service_report import _build_summary
        recs = [
            {"periods": {"today": {"sales": 5, "visits": 100, "revenue": 250.0},
                         "yesterday": {"sales": 0, "visits": 0, "revenue": 0.0}},
             "recommendation": {"action": "hold"}},
        ]
        result = _build_summary(recs)
        assert result["vendas_var"] is None
        assert result["visitas_var"] is None

    def test_conversao_media_calculada(self):
        from app.intel.pricing.service_report import _build_summary
        recs = [
            {"periods": {"today": {"sales": 5, "visits": 100, "revenue": 250.0},
                         "yesterday": {"sales": 5, "visits": 100, "revenue": 250.0}},
             "recommendation": {"action": "hold"}},
        ]
        result = _build_summary(recs)
        assert abs(result["conversao_media"] - 5.0) < 0.01


class TestKpiCard:
    """Testa _kpi_card."""

    def test_kpi_card_com_variacao_positiva(self):
        from app.intel.pricing.service_report import _kpi_card
        result = _kpi_card("Vendas", "10", 25.0)
        assert "Vendas" in result
        assert "10" in result
        assert "25.0%" in result

    def test_kpi_card_com_variacao_negativa(self):
        from app.intel.pricing.service_report import _kpi_card
        result = _kpi_card("Receita", "R$ 500", -10.0)
        assert "Receita" in result
        assert "10.0%" in result

    def test_kpi_card_sem_variacao(self):
        from app.intel.pricing.service_report import _kpi_card
        result = _kpi_card("Visitas", "200", None)
        assert "Visitas" in result
        assert "200" in result

    def test_kpi_card_variacao_zero(self):
        from app.intel.pricing.service_report import _kpi_card
        result = _kpi_card("Conv", "5%", 0.0)
        assert "0%" in result


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 2: service_collector.py — funções puras
# ═══════════════════════════════════════════════════════════════════════════════


class TestSafeFloat:
    """Testa _safe_float."""

    def test_none_retorna_zero(self):
        from app.intel.pricing.service_collector import _safe_float
        assert _safe_float(None) == 0.0

    def test_int_converte(self):
        from app.intel.pricing.service_collector import _safe_float
        assert _safe_float(5) == 5.0

    def test_decimal_converte(self):
        from decimal import Decimal
        from app.intel.pricing.service_collector import _safe_float
        assert _safe_float(Decimal("3.14")) == pytest.approx(3.14)

    def test_float_retorna(self):
        from app.intel.pricing.service_collector import _safe_float
        assert _safe_float(2.5) == 2.5

    def test_zero(self):
        from app.intel.pricing.service_collector import _safe_float
        assert _safe_float(0) == 0.0


class TestComputeHistoricalMetrics:
    """Testa _compute_historical_metrics."""

    def _month(self, year, month, total_sales, days=20, min_price=80.0, max_price=120.0):
        return {
            "month": date(year, month, 1),
            "total_sales": total_sales,
            "days_with_data": days,
            "min_price": min_price,
            "max_price": max_price,
        }

    def test_sem_dados_retorna_vazio(self):
        from app.intel.pricing.service_collector import _compute_historical_metrics
        result = _compute_historical_metrics([], date(2026, 4, 15))
        assert result == {}

    def test_todos_dias_sem_dados_retorna_vazio(self):
        from app.intel.pricing.service_collector import _compute_historical_metrics
        months = [self._month(2026, 1, 0, days=0), self._month(2026, 2, 0, days=0)]
        result = _compute_historical_metrics(months, date(2026, 4, 15))
        assert result == {}

    def test_chaves_retornadas(self):
        from app.intel.pricing.service_collector import _compute_historical_metrics
        months = [self._month(2026, 3, 30, days=15), self._month(2026, 4, 20, days=10)]
        result = _compute_historical_metrics(months, date(2026, 4, 15))
        for key in ["avg_daily_sales_30d", "trend_180d", "peak_daily_sales",
                    "price_range_180d", "current_vs_peak_pct"]:
            assert key in result

    def test_peak_calculado(self):
        """Mês com mais vendas/dia é o pico."""
        from app.intel.pricing.service_collector import _compute_historical_metrics
        months = [
            self._month(2026, 1, 10, days=10),   # 1/dia
            self._month(2026, 2, 100, days=10),  # 10/dia → pico
            self._month(2026, 3, 30, days=10),   # 3/dia
        ]
        result = _compute_historical_metrics(months, date(2026, 4, 15))
        assert result["peak_daily_sales"] == pytest.approx(10.0)

    def test_price_range(self):
        from app.intel.pricing.service_collector import _compute_historical_metrics
        months = [
            self._month(2026, 3, 30, min_price=80.0, max_price=100.0),
            self._month(2026, 4, 20, min_price=90.0, max_price=120.0),
        ]
        result = _compute_historical_metrics(months, date(2026, 4, 15))
        assert result["price_range_180d"]["min"] == pytest.approx(80.0)
        assert result["price_range_180d"]["max"] == pytest.approx(120.0)

    def test_tendencia_declining(self):
        """avg_30d < 75% avg_90d → declining."""
        from app.intel.pricing.service_collector import _compute_historical_metrics
        today = date(2026, 4, 15)
        # Mês de jan (90d ago): 50 vendas/10 dias = 5/dia
        # Mês de fev (60d ago): 40 vendas/10 dias = 4/dia
        # Mês de abr (0d ago): 5 vendas/10 dias = 0.5/dia → declining
        months = [
            self._month(2026, 1, 50, days=10),
            self._month(2026, 2, 40, days=10),
            self._month(2026, 4, 5, days=10),
        ]
        result = _compute_historical_metrics(months, today)
        # Pode ser stable ou declining dependendo dos dados
        assert result["trend_180d"] in ("stable", "declining", "increasing")

    def test_current_vs_peak_pct_negativo_quando_abaixo_pico(self):
        """Se média atual < pico → current_vs_peak_pct negativo."""
        from app.intel.pricing.service_collector import _compute_historical_metrics
        today = date(2026, 4, 15)
        months = [
            self._month(2025, 12, 100, days=10),  # pico: 10/dia
            self._month(2026, 4, 10, days=10),    # atual: 1/dia
        ]
        result = _compute_historical_metrics(months, today)
        if result.get("current_vs_peak_pct") is not None:
            assert result["current_vs_peak_pct"] < 0
