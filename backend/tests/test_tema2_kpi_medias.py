"""
Tema 2 — KPI por periodo agora retorna medias diarias junto com os totais.

Nota: SQLite (usado nos testes) nao lida bem com cast(timestamp_tz, Date)
igual ao Postgres, entao os testes de integracao que dependem desse cast
ficam como smoke/xfail (ja existem em test_kpi_basic.py). Aqui testamos:

1. Lógica matemática de cálculo de média (puro)
2. Schema KpiPeriodOut aceita os novos campos
3. Funções com inputs vazios retornam as keys corretas
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.vendas.schemas import KpiPeriodOut
from app.vendas.service_kpi import _kpi_date_range, _kpi_single_day


# ─── Schema ─────────────────────────────────────────────────────────────────

def test_schema_kpi_period_aceita_novos_campos():
    """Pydantic schema deve validar os novos campos de media."""
    d = {
        "vendas": 280, "visitas": 2800, "conversao": 10.0,
        "anuncios": 1, "valor_estoque": 0.0, "receita": 0.0,
        "dias_no_periodo": 7, "vendas_media_dia": 40.0,
        "visitas_media_dia": 400.0, "pedidos_media_dia": 10.0,
        "receita_media_dia": 2800.0,
    }
    out = KpiPeriodOut(**d)
    assert out.dias_no_periodo == 7
    assert out.vendas_media_dia == 40.0
    assert out.visitas_media_dia == 400.0
    assert out.pedidos_media_dia == 10.0
    assert out.receita_media_dia == 2800.0


def test_schema_kpi_period_campos_medias_tem_default():
    """Defaults devem permitir retrocompatibilidade."""
    out = KpiPeriodOut(vendas=10, visitas=100)
    assert out.dias_no_periodo == 1
    assert out.vendas_media_dia == 0.0  # default


def test_schema_kpi_period_round_trip():
    """Serializacao pra dict e de volta preserva campos."""
    original = KpiPeriodOut(
        vendas=70, visitas=700,
        dias_no_periodo=7,
        vendas_media_dia=10.0, visitas_media_dia=100.0,
    )
    d = original.model_dump()
    assert d["vendas_media_dia"] == 10.0
    assert d["dias_no_periodo"] == 7
    re = KpiPeriodOut(**d)
    assert re.vendas_media_dia == 10.0


# ─── Logica de media (pura, sem DB) ─────────────────────────────────────────

def _calc_medias(totais: dict, dias: int) -> dict:
    """Replica a logica de calculo de media diaria de service_kpi."""
    if dias < 1:
        dias = 1
    return {
        "dias_no_periodo": dias,
        "vendas_media_dia": round(totais["vendas"] / dias, 2),
        "visitas_media_dia": round(totais["visitas"] / dias, 2),
        "pedidos_media_dia": round(totais["pedidos"] / dias, 2),
        "receita_media_dia": round(totais["receita_total"] / dias, 2),
    }


def test_media_divide_por_7_dias():
    totais = {"vendas": 280, "visitas": 2800, "pedidos": 70, "receita_total": 28000.0}
    m = _calc_medias(totais, 7)
    assert m["dias_no_periodo"] == 7
    assert m["vendas_media_dia"] == 40.0
    assert m["visitas_media_dia"] == 400.0
    assert m["pedidos_media_dia"] == 10.0
    assert m["receita_media_dia"] == 4000.0


def test_media_divide_por_30_dias():
    totais = {"vendas": 900, "visitas": 9000, "pedidos": 300, "receita_total": 90000.0}
    m = _calc_medias(totais, 30)
    assert m["vendas_media_dia"] == 30.0
    assert m["visitas_media_dia"] == 300.0


def test_media_1_dia_igual_total():
    """Para 1 dia, media = total."""
    totais = {"vendas": 25, "visitas": 250, "pedidos": 5, "receita_total": 2500.0}
    m = _calc_medias(totais, 1)
    assert m["vendas_media_dia"] == 25.0
    assert m["visitas_media_dia"] == 250.0


def test_media_arredondamento_decimal():
    """Divisoes nao inteiras arredondam a 2 casas."""
    totais = {"vendas": 100, "visitas": 1000, "pedidos": 33, "receita_total": 1234.5}
    m = _calc_medias(totais, 7)
    assert m["vendas_media_dia"] == 14.29  # 100/7 = 14.285...
    assert m["visitas_media_dia"] == 142.86  # 1000/7 = 142.857...


def test_media_zero_dias_fallback_para_1():
    """Se dias <= 0, tratar como 1 para evitar division by zero."""
    totais = {"vendas": 10, "visitas": 100, "pedidos": 2, "receita_total": 100.0}
    m = _calc_medias(totais, 0)
    assert m["dias_no_periodo"] == 1
    assert m["vendas_media_dia"] == 10.0


def test_media_zero_vendas_retorna_zero():
    """Periodo sem vendas: media = 0."""
    totais = {"vendas": 0, "visitas": 0, "pedidos": 0, "receita_total": 0.0}
    m = _calc_medias(totais, 15)
    assert m["vendas_media_dia"] == 0.0
    assert m["visitas_media_dia"] == 0.0


def test_calculo_dias_no_periodo():
    """Numero de dias inclusive = (to - from) + 1."""
    from_d = date(2026, 4, 4)
    to_d = date(2026, 4, 10)
    dias = (to_d - from_d).days + 1
    assert dias == 7

    # 30 dias
    to_d = date(2026, 5, 3)
    from_d = to_d - timedelta(days=29)
    dias = (to_d - from_d).days + 1
    assert dias == 30


# ─── Smoke tests (SQLite: nao valida valores por causa do cast) ────────────

@pytest.mark.asyncio
async def test_kpi_single_day_sem_listings_retorna_keys(db):
    """Sem listings, a funcao nao deve explodir e deve retornar todas as keys."""
    result = await _kpi_single_day(db, [], date(2026, 4, 10))
    assert "dias_no_periodo" in result
    assert "vendas_media_dia" in result
    assert "visitas_media_dia" in result
    assert "pedidos_media_dia" in result
    assert "receita_media_dia" in result
    assert result["dias_no_periodo"] == 1
    assert result["vendas_media_dia"] == 0.0


@pytest.mark.asyncio
async def test_kpi_date_range_sem_listings_retorna_keys(db):
    """Sem listings, retorna todas as keys incluindo medias."""
    result = await _kpi_date_range(
        db, [], date(2026, 4, 4), date(2026, 4, 10)
    )
    assert "dias_no_periodo" in result
    assert "vendas_media_dia" in result
    assert result["dias_no_periodo"] == 7  # 4 a 10 = 7 dias
    assert result["vendas_media_dia"] == 0.0
    assert result["visitas_media_dia"] == 0.0


@pytest.mark.asyncio
async def test_kpi_date_range_dias_calculados_corretamente(db):
    """Valida dias_no_periodo para diferentes intervalos."""
    # 15 dias
    r = await _kpi_date_range(
        db, [], date(2026, 4, 1), date(2026, 4, 15)
    )
    assert r["dias_no_periodo"] == 15

    # 30 dias
    r = await _kpi_date_range(
        db, [], date(2026, 3, 12), date(2026, 4, 10)
    )
    assert r["dias_no_periodo"] == 30
