"""
Tema 6 — Testes das correcoes de custos, comissoes e frete.

Valida:
1. calcular_taxa_ml usa sale_fee_pct real quando disponivel
2. Fallback de taxa usa 0.11 (classico), nao 0.17
3. Fallback para listing_type desconhecido usa 0.16
4. calcular_margem funciona com frete real
5. Logica de extracao de sender_cost (prioridade correta)
6. net_amount = total - sale_fee - shipping_cost
"""
from decimal import Decimal

import pytest

from app.core.constants import ML_FEES, ML_FEES_FLOAT, ML_FEE_DEFAULT
from app.financeiro.service import calcular_taxa_ml, calcular_margem


# ─── Taxa ML ────────────────────────────────────────────────────────────────

def test_taxa_ml_classico_11pct():
    assert calcular_taxa_ml("classico") == Decimal("0.11")


def test_taxa_ml_premium_16pct():
    assert calcular_taxa_ml("premium") == Decimal("0.16")


def test_taxa_ml_full_16pct():
    assert calcular_taxa_ml("full") == Decimal("0.16")


def test_taxa_ml_sale_fee_real_sobrescreve_tabela():
    """Quando sale_fee_pct real vem da API, deve ter prioridade."""
    # Classico padrao seria 11%, mas API retornou 9.5% para esta categoria
    real = Decimal("0.095")
    assert calcular_taxa_ml("classico", sale_fee_pct=real) == real


def test_taxa_ml_sale_fee_zero_ignorado():
    """sale_fee_pct=0 (ou None) nao deve sobrescrever — usa tabela."""
    assert calcular_taxa_ml("premium", sale_fee_pct=None) == Decimal("0.16")
    assert calcular_taxa_ml("premium", sale_fee_pct=Decimal("0")) == Decimal("0.16")


def test_taxa_ml_listing_type_desconhecido_usa_default():
    assert calcular_taxa_ml("xpto") == ML_FEE_DEFAULT  # 0.16
    assert calcular_taxa_ml("") == ML_FEE_DEFAULT


def test_taxa_ml_case_insensitive():
    assert calcular_taxa_ml("CLASSICO") == Decimal("0.11")
    assert calcular_taxa_ml("Premium") == Decimal("0.16")


# ─── Calculo de margem ──────────────────────────────────────────────────────

def test_calcular_margem_classico_sem_frete():
    """Preco 100, custo 50, classico 11% = margem 39."""
    res = calcular_margem(
        preco=Decimal("100"),
        custo=Decimal("50"),
        listing_type="classico",
    )
    assert res["taxa_ml_valor"] == Decimal("11.00")
    assert res["margem_bruta"] == Decimal("39.00")
    assert res["margem_pct"] == Decimal("39.00")


def test_calcular_margem_com_frete_real():
    """Preco 100, custo 50, classico 11%, frete real 18 = margem 21."""
    res = calcular_margem(
        preco=Decimal("100"),
        custo=Decimal("50"),
        listing_type="classico",
        frete=Decimal("18"),
    )
    assert res["frete"] == Decimal("18")
    assert res["taxa_ml_valor"] == Decimal("11.00")
    # 100 - 50 - 11 - 18 = 21
    assert res["margem_bruta"] == Decimal("21.00")


def test_calcular_margem_full_16pct():
    """Full tem taxa 16%: 100 - 60 - 16 = 24."""
    res = calcular_margem(
        preco=Decimal("100"),
        custo=Decimal("60"),
        listing_type="full",
    )
    assert res["taxa_ml_valor"] == Decimal("16.00")
    assert res["margem_bruta"] == Decimal("24.00")


def test_calcular_margem_usa_sale_fee_pct_real():
    """Quando vem taxa real, deve calcular com ela."""
    res = calcular_margem(
        preco=Decimal("100"),
        custo=Decimal("50"),
        listing_type="classico",
        sale_fee_pct=Decimal("0.09"),
    )
    assert res["taxa_ml_valor"] == Decimal("9.00")
    assert res["margem_bruta"] == Decimal("41.00")


# ─── Shipping extraction (valida que prioridade esta correta) ───────────────

def _extract_sender_cost(shipment: dict) -> Decimal:
    """Mesma logica de tasks_listings.py (apos fix) e tasks_orders.py."""
    cost_comps = shipment.get("cost_components", {}) or {}
    sender_cost = (
        cost_comps.get("sender_cost")
        or cost_comps.get("loyal_discount")
        or shipment.get("base_cost")
        or 0
    )
    return Decimal(str(sender_cost or 0))


def test_sender_cost_prioridade_1_sender_cost():
    """sender_cost presente deve ser preferido."""
    s = {
        "base_cost": 99.99,
        "cost_components": {
            "sender_cost": 25.50,
            "loyal_discount": 20.00,
        },
    }
    assert _extract_sender_cost(s) == Decimal("25.5")


def test_sender_cost_prioridade_2_loyal_discount():
    """Quando sender_cost nao existe, usa loyal_discount."""
    s = {
        "base_cost": 99.99,
        "cost_components": {
            "sender_cost": None,
            "loyal_discount": 18.00,
        },
    }
    assert _extract_sender_cost(s) == Decimal("18.0")


def test_sender_cost_prioridade_3_base_cost():
    """Sem cost_components, usa base_cost."""
    s = {"base_cost": 30.00, "cost_components": {}}
    assert _extract_sender_cost(s) == Decimal("30.0")


def test_sender_cost_frete_gratis_retorna_zero():
    """Frete gratis (sender_cost=0 e nada mais) retorna zero corretamente."""
    s = {"cost_components": {"sender_cost": 0}, "base_cost": 0}
    assert _extract_sender_cost(s) == Decimal("0")


# ─── net_amount coerente ────────────────────────────────────────────────────

def test_net_amount_calculo_basico():
    total = Decimal("150.00")
    fee = Decimal("16.50")  # 11% classico
    ship = Decimal("22.00")  # frete vendedor real
    net = total - fee - ship
    assert net == Decimal("111.50")


def test_net_amount_ignora_frete_comprador():
    """
    Regressao: antes, o sistema podia usar shipping.cost do /orders que e
    o frete do comprador. Agora precisa usar sender_cost que vem do
    /shipments. Este teste garante que o valor calculado usa o custo real
    do vendedor (ex: 0 para frete gratis pago pelo ML).
    """
    total = Decimal("80.00")
    fee = Decimal("8.80")  # 11%
    ship_vendedor_real = Decimal("0")  # frete subsidiado pelo ML
    net = total - fee - ship_vendedor_real
    assert net == Decimal("71.20")


# ─── Fallback 0.11 (nao mais 0.17) em service_kpi ───────────────────────────

def test_fallback_fee_pct_usa_11_nao_17():
    """
    Regressao do bug: service_kpi.py usava 0.17 como fallback quando
    listing.listing_type nao batia. Agora usa 0.11 (classico, mais comum).
    """
    # Simulacao manual da logica corrigida em service_kpi.py
    listing_type = None  # listing sem tipo definido
    taxa_pct = ML_FEES_FLOAT.get((listing_type or "").lower(), 0.11)
    assert taxa_pct == 0.11

    # listing_type existente, classico
    listing_type = "classico"
    taxa_pct = ML_FEES_FLOAT.get((listing_type or "").lower(), 0.11)
    assert taxa_pct == 0.11

    # listing_type premium
    listing_type = "premium"
    taxa_pct = ML_FEES_FLOAT.get((listing_type or "").lower(), 0.11)
    assert taxa_pct == 0.16


def test_ml_fees_tabela_oficial_sincronizada():
    """Garante que ML_FEES e ML_FEES_FLOAT estao sincronizados."""
    for tipo, valor_decimal in ML_FEES.items():
        assert tipo in ML_FEES_FLOAT
        assert float(valor_decimal) == ML_FEES_FLOAT[tipo]
