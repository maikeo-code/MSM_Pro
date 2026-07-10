"""Testes de stock_from_item (E9) — estoque como o painel do ML exibe.

Item com variações: soma variations[].available_quantity (o topo subconta).
Item sem variações: usa available_quantity do topo (inclui FULL simples).
"""
from app.jobs.tasks_listings import stock_from_item


def test_item_com_variacoes_soma():
    """3 variações 20+30+19 = 69 (bug real: painel ML=69, app lia topo=19)."""
    item = {
        "available_quantity": 19,  # topo subconta — NAO deve ser usado
        "variations": [
            {"id": 1, "available_quantity": 20},
            {"id": 2, "available_quantity": 30},
            {"id": 3, "available_quantity": 19},
        ],
    }
    assert stock_from_item(item) == 69


def test_item_sem_variacoes_usa_topo():
    item = {"available_quantity": 33, "variations": []}
    assert stock_from_item(item) == 33


def test_item_sem_campo_variations_usa_topo():
    item = {"available_quantity": 7}
    assert stock_from_item(item) == 7


def test_variacao_com_quantidade_none_conta_zero():
    item = {
        "available_quantity": 0,
        "variations": [
            {"id": 1, "available_quantity": 10},
            {"id": 2, "available_quantity": None},
            {"id": 3},
        ],
    }
    assert stock_from_item(item) == 10


def test_sem_estoque_retorna_zero():
    assert stock_from_item({}) == 0
