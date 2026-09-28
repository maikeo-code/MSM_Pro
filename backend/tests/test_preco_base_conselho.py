"""Preco BASE via PUT /items (Conselho de Precos do JARVIS) -- nao usa promocao.

Travas: o preco vivo tem que ser o esperado (senao alguem mexeu -> 409, sem PUT); promocao ativa
(regular_amount no sale_price) -> 409, sem PUT; depois do PUT relê o preco e diz se confirmou.
"""
import os
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from app.vendas.service_preco_base import Conflito, aplicar_no_ml  # noqa: E402


def _client(leituras, put=None):
    c = AsyncMock()
    c.get_item_sale_price = AsyncMock(side_effect=leituras)
    c.update_item_price = AsyncMock(return_value=put or {"id": "MLB1", "price": 51.18})
    return c


async def test_aplica_e_confirma_na_releitura():
    c = _client([{"amount": 50.77}, {"amount": 51.18}])
    r = await aplicar_no_ml(c, "MLB1", 51.18, esperado=50.77, espera_s=0)
    c.update_item_price.assert_awaited_once_with("MLB1", 51.18)
    assert r["preco_antes"] == 50.77 and r["preco_lido_depois"] == 51.18 and r["confirmado"] is True


async def test_preco_vivo_diferente_do_esperado_nao_aplica():
    c = _client([{"amount": 49.90}])
    with pytest.raises(Conflito, match="49.9"):
        await aplicar_no_ml(c, "MLB1", 51.18, esperado=50.77, espera_s=0)
    c.update_item_price.assert_not_awaited()


async def test_promocao_ativa_nao_aplica():
    c = _client([{"amount": 50.77, "regular_amount": 55.0}])
    with pytest.raises(Conflito, match="promo"):
        await aplicar_no_ml(c, "MLB1", 51.18, esperado=50.77, espera_s=0)
    c.update_item_price.assert_not_awaited()


async def test_leitura_vazia_nao_aplica():
    c = _client([{}])
    with pytest.raises(Conflito):
        await aplicar_no_ml(c, "MLB1", 51.18, esperado=50.77, espera_s=0)
    c.update_item_price.assert_not_awaited()


async def test_releitura_tenta_de_novo_uma_vez():
    c = _client([{"amount": 50.77}, {"amount": 50.77}, {"amount": 51.18}])
    r = await aplicar_no_ml(c, "MLB1", 51.18, esperado=50.77, espera_s=0)
    assert r["confirmado"] is True and r["leituras_depois"] == 2


async def test_nao_confirmado_depois_de_duas_releituras():
    c = _client([{"amount": 50.77}, {"amount": 50.77}, {"amount": 50.77}])
    r = await aplicar_no_ml(c, "MLB1", 51.18, esperado=50.77, espera_s=0)
    assert r["confirmado"] is False and r["preco_lido_depois"] == 50.77


async def test_erro_no_put_sobe():
    from app.mercadolivre.client import MLClientError
    c = _client([{"amount": 50.77}])
    c.update_item_price = AsyncMock(side_effect=MLClientError("boom", 400))
    with pytest.raises(MLClientError):
        await aplicar_no_ml(c, "MLB1", 51.18, esperado=50.77, espera_s=0)


def test_preco_invalido():
    from app.vendas.service_preco_base import validar_preco
    for p in (0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            validar_preco(p)
    assert validar_preco(51.184) == 51.18
