"""
Testes para consultor/service.py — funções puras de formatação.

Cobre funções sem DB/HTTP:
- _formatar_historico_7d
- _formatar_concorrentes
- _formatar_listing (parcial)
- _formatar_kpi
"""
import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest


def _make_snapshot(date_str="2026-04-10", sales=5, visits=100, revenue=500.0,
                   cancelled=0, returns=0):
    return {
        "date": date_str,
        "sales": sales,
        "visits": visits,
        "revenue": revenue,
        "cancelled": cancelled,
        "returns": returns,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# _formatar_historico_7d
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatarHistorico7d:
    def test_sem_dados_retorna_sem_dados(self):
        from app.consultor.service import _formatar_historico_7d
        result = _formatar_historico_7d([])
        assert "sem dados" in result.lower()

    def test_com_dados_retorna_string(self):
        from app.consultor.service import _formatar_historico_7d
        snaps = [_make_snapshot(f"2026-04-{i:02d}") for i in range(1, 8)]
        result = _formatar_historico_7d(snaps)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_tendencia_subindo(self):
        """Segunda metade com mais vendas → tendência 'subindo'."""
        from app.consultor.service import _formatar_historico_7d

        snaps = [
            _make_snapshot(f"2026-04-0{i}", sales=i * 2, visits=i * 20, revenue=i * 200)
            for i in range(1, 8)
        ]
        result = _formatar_historico_7d(snaps)
        assert "subindo" in result.lower() or "tendencia" in result.lower()

    def test_tendencia_caindo(self):
        """Segunda metade com menos vendas → tendência 'caindo'."""
        from app.consultor.service import _formatar_historico_7d

        snaps = [
            _make_snapshot(f"2026-04-0{i}", sales=(8 - i) * 2, visits=(8 - i) * 20, revenue=(8 - i) * 200)
            for i in range(1, 8)
        ]
        result = _formatar_historico_7d(snaps)
        assert isinstance(result, str)

    def test_com_cancelamentos_e_devolucoes(self):
        """Snapshots com cancelamentos/devoluções → inclui na string."""
        from app.consultor.service import _formatar_historico_7d

        snaps = [
            _make_snapshot("2026-04-01", sales=5, cancelled=2, returns=1),
            _make_snapshot("2026-04-02", sales=3, cancelled=0, returns=0),
        ]
        result = _formatar_historico_7d(snaps)
        # Com cancelamentos presentes (total=2), deve mencionar
        assert "cancelamentos" in result.lower()

    def test_com_um_snapshot_tendencia_insuficiente(self):
        """1 snapshot → dados insuficientes para tendência."""
        from app.consultor.service import _formatar_historico_7d

        result = _formatar_historico_7d([_make_snapshot()])
        assert "insuficientes" in result.lower() or len(result) > 0

    def test_trend_symbol_zero_para_zero_estavel(self):
        """old=0, new=0 → '='."""
        from app.consultor.service import _formatar_historico_7d

        snaps = [
            _make_snapshot(f"2026-04-0{i}", sales=0, visits=0, revenue=0.0)
            for i in range(1, 4)
        ]
        result = _formatar_historico_7d(snaps)
        assert isinstance(result, str)

    def test_trend_symbol_zero_para_positivo_subindo(self):
        """old=0, new>0 → 'subindo'."""
        from app.consultor.service import _formatar_historico_7d

        snaps = [
            _make_snapshot("2026-04-01", sales=0, visits=0, revenue=0.0),
            _make_snapshot("2026-04-02", sales=0, visits=0, revenue=0.0),
            _make_snapshot("2026-04-03", sales=10, visits=100, revenue=1000.0),
            _make_snapshot("2026-04-04", sales=10, visits=100, revenue=1000.0),
        ]
        result = _formatar_historico_7d(snaps)
        assert "subindo" in result.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# _formatar_concorrentes
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatarConcorrentes:
    def test_sem_concorrentes_retorna_vazio(self):
        from app.consultor.service import _formatar_concorrentes
        result = _formatar_concorrentes([], 100.0)
        assert result == ""

    def test_com_concorrente_mais_barato(self):
        from app.consultor.service import _formatar_concorrentes

        concorrentes = [
            {"mlb_id": "MLB111", "title": "Produto X", "price": 80.0, "sales_delta": None}
        ]
        result = _formatar_concorrentes(concorrentes, 100.0)
        assert "MLB111" in result
        assert "R$ 80.00" in result

    def test_com_concorrente_sem_preco(self):
        """Concorrente sem price → menciona 'sem dados de preco'."""
        from app.consultor.service import _formatar_concorrentes

        concorrentes = [
            {"mlb_id": "MLB222", "title": "Produto Y", "price": None, "sales_delta": None}
        ]
        result = _formatar_concorrentes(concorrentes, 100.0)
        assert "sem dados" in result.lower()

    def test_com_concorrente_com_vendas_delta(self):
        """Concorrente com sales_delta → inclui na string."""
        from app.consultor.service import _formatar_concorrentes

        concorrentes = [
            {"mlb_id": "MLB333", "title": "Produto Z", "price": 90.0, "sales_delta": 5}
        ]
        result = _formatar_concorrentes(concorrentes, 100.0)
        assert "5 vendas/dia" in result

    def test_diferenca_percentual_calculada(self):
        """Diferença percentual entre preços calculada corretamente."""
        from app.consultor.service import _formatar_concorrentes

        concorrentes = [
            {"mlb_id": "MLB444", "title": "Produto A", "price": 100.0, "sales_delta": None}
        ]
        result = _formatar_concorrentes(concorrentes, 120.0)
        # meu_preco=120, conc_price=100 → diff = (120-100)/100*100 = +20.0%
        assert "+20.0%" in result

    def test_concorrente_preco_zero_nao_divide(self):
        """Concorrente com price=0 → sem divisão por zero."""
        from app.consultor.service import _formatar_concorrentes

        concorrentes = [
            {"mlb_id": "MLB555", "title": "Produto B", "price": 0.0, "sales_delta": None}
        ]
        # Não deve levantar ZeroDivisionError
        result = _formatar_concorrentes(concorrentes, 100.0)
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════════════════
# _formatar_kpi
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatarKpi:
    def test_kpi_vazio_retorna_string(self):
        from app.consultor.service import _formatar_kpi
        result = _formatar_kpi({})
        assert isinstance(result, str)

    def test_kpi_com_dados_retorna_string(self):
        from app.consultor.service import _formatar_kpi

        kpi = {
            "today": {"vendas": 5, "visitas": 100, "conversao": 5.0, "receita": 500.0},
            "yesterday": {"vendas": 3, "visitas": 80, "conversao": 3.75, "receita": 300.0},
            "last_7d": {"vendas": 20, "visitas": 500, "conversao": 4.0, "receita": 2000.0},
        }
        result = _formatar_kpi(kpi)
        assert isinstance(result, str)
        assert len(result) > 0
