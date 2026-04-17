"""Testes do plugin ekas_efficiency."""
import os
import sqlite3
import pytest

from plugins.ekas_efficiency import (
    init_schema,
    compute_cost,
    check_budget,
    log_usage,
    get_today_usage,
    build_cache_control_messages,
    BudgetExceeded,
    PRICING,
    CACHED_INPUT_DISCOUNT,
    BATCH_DISCOUNT,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    init_schema(c)
    c.commit()
    yield c
    c.close()


def test_init_schema_cria_tabela(conn):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ekas_usage_log'"
    ).fetchone()
    assert row is not None


def test_init_schema_idempotente(conn):
    init_schema(conn)
    init_schema(conn)  # não explode


def test_compute_cost_haiku_input_e_output():
    cost = compute_cost("haiku-4-5", 1000, 500)
    expected = 1000 * PRICING["haiku"]["input"] + 500 * PRICING["haiku"]["output"]
    assert cost == pytest.approx(expected, rel=1e-6)


def test_compute_cost_cached_reduz_90pct():
    # 1000 input todos cacheados = 10% do custo normal
    full = compute_cost("sonnet-4-6", 1000, 0, cached_tokens=0)
    cached = compute_cost("sonnet-4-6", 1000, 0, cached_tokens=1000)
    assert cached == pytest.approx(full * CACHED_INPUT_DISCOUNT, rel=1e-6)


def test_compute_cost_batch_desconta_50pct():
    normal = compute_cost("sonnet-4-6", 1000, 1000, batch=False)
    batch = compute_cost("sonnet-4-6", 1000, 1000, batch=True)
    assert batch == pytest.approx(normal * BATCH_DISCOUNT, rel=1e-6)


def test_compute_cost_modelo_desconhecido_cai_em_haiku():
    cost = compute_cost("modelo-louco", 1000, 0)
    assert cost > 0


def test_log_usage_persiste_e_calcula(conn):
    cost = log_usage(conn, "test", "sonnet", 1000, 500)
    assert cost > 0
    row = conn.execute("SELECT * FROM ekas_usage_log").fetchone()
    assert row is not None


def test_get_today_usage_agrega(conn):
    log_usage(conn, "a", "haiku", 100, 50)
    log_usage(conn, "b", "haiku", 200, 80)
    u = get_today_usage(conn)
    assert u["tokens_in"] == 300
    assert u["tokens_out"] == 130
    assert u["cost_usd"] > 0


def test_check_budget_ok_quando_vazio(conn):
    check_budget(conn, planned_cost_usd=0.01)  # não deve levantar


def test_check_budget_estoura_em_usd(conn, monkeypatch):
    monkeypatch.setenv("MAX_EKAS_USD_DIA", "0.001")
    log_usage(conn, "x", "opus", 1000, 1000)  # caro
    with pytest.raises(BudgetExceeded):
        check_budget(conn)


def test_check_budget_estoura_em_tokens(conn, monkeypatch):
    monkeypatch.setenv("MAX_EKAS_TOKENS_DIA", "100")
    log_usage(conn, "x", "haiku", 200, 0)
    with pytest.raises(BudgetExceeded):
        check_budget(conn)


def test_check_budget_planned_cost_soma(conn, monkeypatch):
    monkeypatch.setenv("MAX_EKAS_USD_DIA", "0.05")
    log_usage(conn, "x", "haiku", 10, 5)  # custo quase zero
    # planned cost muito alto: deve estourar
    with pytest.raises(BudgetExceeded):
        check_budget(conn, planned_cost_usd=1.00)


def test_build_cache_control_messages_estrutura():
    params = build_cache_control_messages("SYS", "CTX", "pergunta")
    assert "system" in params
    assert "messages" in params
    assert len(params["system"]) == 2
    for block in params["system"]:
        assert block["cache_control"] == {"type": "ephemeral"}
    assert params["messages"][0]["role"] == "user"
    assert params["messages"][0]["content"] == "pergunta"


def test_build_cache_control_mantem_textos():
    params = build_cache_control_messages("S1", "C1", "U1")
    assert params["system"][0]["text"] == "S1"
    assert params["system"][1]["text"] == "C1"
