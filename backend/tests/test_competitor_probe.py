"""Sondagem (so leitura) dos endpoints oficiais de preco de concorrente -- pesquisa no MCP do ML em 29/09/2026:
/items/{id}/sale_price aceita token de outro vendedor (so esconde metadata); catalogo por /products/{id};
MLBU (User Product) por /user-products/{id}. A sondagem diz o que cada um respondeu, sem gravar nada."""
import os

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-for-unit-tests!!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from app.mercadolivre.client import MLClientError  # noqa: E402


class _Fake:
    def __init__(self, respostas):
        self.respostas, self.chamadas = respostas, []

    async def _request(self, method, url, **kw):
        self.chamadas.append((method, url, kw.get("params")))
        r = self.respostas.get(url)
        if isinstance(r, Exception):
            raise r
        if r is None:
            raise MLClientError("HTTP 404: not found", status_code=404)
        return r


@pytest.mark.asyncio
async def test_item_de_terceiro_pelo_sale_price():
    from app.concorrencia.probe import sondar
    fake = _Fake({"/items/MLB4185585590/sale_price": {"amount": 49.9, "regular_amount": None},
                  "/items/MLB4185585590/prices": MLClientError("HTTP 403: forbidden", status_code=403)})
    r = (await sondar(fake, ["MLB4185585590"]))[0]
    assert r["id_ml"] == "MLB4185585590" and r["preco"] == 49.9 and r["fonte"] == "sale_price"
    assert r["tentativas"]["sale_price"] == {"ok": True, "status": 200, "preco": 49.9}
    assert r["tentativas"]["prices"]["status"] == 403
    assert all(m == "GET" for m, _, _ in fake.chamadas)                      # so leitura
    assert ("GET", "/items/MLB4185585590/sale_price", {"context": "channel_marketplace"}) in fake.chamadas


@pytest.mark.asyncio
async def test_catalogo_pelo_vencedor_da_buy_box():
    from app.concorrencia.probe import sondar
    fake = _Fake({"/products/MLB66736353": {"buy_box_winner": {"item_id": "MLB111", "price": 30.5}}})
    r = (await sondar(fake, ["MLB66736353"]))[0]
    assert r["preco"] == 30.5 and r["fonte"] == "products.buy_box_winner" and r["vencedor"] == "MLB111"


@pytest.mark.asyncio
async def test_mlbu_tenta_user_products_e_nao_inventa_preco():
    from app.concorrencia.probe import sondar
    fake = _Fake({"/user-products/MLBU3453370601": {"id": "MLBU3453370601", "family_id": 9, "user_id": 5}})
    r = (await sondar(fake, ["MLBU3453370601"]))[0]
    assert r["tentativas"]["user_products"]["ok"] is True and r["preco"] is None
    assert r["tentativas"]["products"]["status"] == 404


def test_rota_de_sondagem_existe_e_e_get():
    from app.concorrencia.router import router
    rotas = {(r.path, tuple(sorted(r.methods))) for r in router.routes}
    assert ("/competitors/prices/probe", ("GET",)) in rotas
