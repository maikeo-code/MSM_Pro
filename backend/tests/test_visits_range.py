"""Visitas por dia num periodo (read-only) -- usado pelo Conselho de Precos (JARVIS).

time_window: results[].total = total DAQUELE dia; ending e exclusivo.
Erro do ML tem que subir (nao virar 0), senao "sem dado" parece "zero visitas".
"""
import os
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


def _client():
    from app.mercadolivre.client import MLClient
    with patch("app.mercadolivre.client._distributed_rate_limit", new_callable=AsyncMock):
        return MLClient(access_token="fake-token")


async def test_uma_chamada_com_last_n_e_ending_exclusivo():
    c = _client()
    c._request = AsyncMock(return_value={"results": [
        {"date": "2026-09-14T00:00:00Z", "total": 80},
        {"date": "2026-09-15T00:00:00Z", "total": 0},
        {"date": "2026-09-16T00:00:00Z", "total": 95}]})
    r = await c.get_item_visits_range("mlb-123", date(2026, 9, 14), date(2026, 9, 16))
    assert r == {"2026-09-14": 80, "2026-09-15": 0, "2026-09-16": 95}
    args, kw = c._request.call_args
    assert args[1] == "/items/MLB123/visits/time_window"
    assert kw["params"] == {"last": 3, "unit": "day", "ending": "2026-09-17"}


async def test_erro_do_ml_sobe_em_vez_de_virar_zero():
    from app.mercadolivre.client import MLClientError
    c = _client()
    c._request = AsyncMock(side_effect=MLClientError("boom", 500))
    with pytest.raises(MLClientError):
        await c.get_item_visits_range("MLB1", date(2026, 9, 14), date(2026, 9, 15))


async def test_dia_fora_do_periodo_e_ignorado_e_dia_ausente_nao_vira_zero():
    c = _client()
    c._request = AsyncMock(return_value={"results": [
        {"date": "2026-09-13T00:00:00Z", "total": 7},
        {"date": "2026-09-14T00:00:00Z", "total": 80}]})
    r = await c.get_item_visits_range("MLB1", date(2026, 9, 14), date(2026, 9, 15))
    assert r == {"2026-09-14": 80}


def test_periodo_invalido():
    from app.vendas.service_visits_range import validar_periodo
    with pytest.raises(ValueError):
        validar_periodo(date(2026, 9, 20), date(2026, 9, 14), hoje=date(2026, 9, 28))
    with pytest.raises(ValueError):
        validar_periodo(date(2026, 6, 1), date(2026, 9, 14), hoje=date(2026, 9, 28))   # > 60 dias
    with pytest.raises(ValueError):
        validar_periodo(date(2026, 9, 14), date(2026, 9, 28), hoje=date(2026, 9, 28))  # hoje ainda nao fechou
    assert validar_periodo(date(2026, 9, 14), date(2026, 9, 23), hoje=date(2026, 9, 28)) == 10
