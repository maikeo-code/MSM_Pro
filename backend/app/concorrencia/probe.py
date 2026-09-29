"""Sondagem (somente leitura) dos endpoints oficiais de preço de concorrente.

Pesquisa na documentação do ML (MCP, 29/09/2026):
  - item MLB de qualquer vendedor → GET /items/{id}/sale_price?context=channel_marketplace (doc "Preços de
    produtos": com token que não é do vendedor, só o `metadata` vem oculto) e GET /items/{id}/prices
  - catálogo (MLB 8 díg) → GET /products/{id} (buy_box_winner) e /products/{id}/items
  - MLBU (User Product) → GET /user-products/{id}; a doc não garante leitura de UP de terceiro

Nada é gravado: devolve, por id, o que cada endpoint respondeu e o primeiro preço encontrado.
"""
from app.concorrencia.competitor_targets import is_catalog_id
from app.mercadolivre.client import MLClientError


def _norm(id_ml: str) -> str:
    return id_ml.upper().replace("-", "").strip()


async def _tentar(client, url: str, params: dict | None = None) -> tuple[dict, dict | list | None]:
    try:
        body = await client._request("GET", url, params=params) if params else await client._request("GET", url)
        return {"ok": True, "status": 200}, body
    except MLClientError as exc:
        return {"ok": False, "status": exc.status_code, "erro": str(exc)[:160]}, None
    except Exception as exc:  # rede etc. — a sondagem nunca derruba o resto
        return {"ok": False, "status": None, "erro": f"{type(exc).__name__}: {str(exc)[:160]}"}, None


def _preco(valor) -> float | None:
    try:
        return float(valor) if valor is not None else None
    except (TypeError, ValueError):
        return None


async def sondar(client, ids: list[str]) -> list[dict]:
    saida = []
    for bruto in ids:
        id_ml = _norm(bruto)
        r = {"id_ml": id_ml, "preco": None, "fonte": None, "vencedor": None, "tentativas": {}}

        def achou(nome: str, preco, vencedor=None):
            r["tentativas"][nome]["preco"] = preco
            if preco is not None and r["preco"] is None:
                r["preco"], r["fonte"], r["vencedor"] = preco, nome if nome != "products" else "products.buy_box_winner", vencedor

        if not is_catalog_id(id_ml):
            st, body = await _tentar(client, f"/items/{id_ml}/sale_price", {"context": "channel_marketplace"})
            r["tentativas"]["sale_price"] = st
            if body:
                achou("sale_price", _preco(body.get("amount")))
            st, body = await _tentar(client, f"/items/{id_ml}/prices")
            r["tentativas"]["prices"] = st
            if body:
                std = [p for p in body.get("prices") or [] if p.get("type") == "standard"]
                achou("prices", _preco(std[0].get("amount")) if std else None)
        else:
            st, body = await _tentar(client, f"/products/{id_ml}")
            r["tentativas"]["products"] = st
            if body:
                bbw = body.get("buy_box_winner") or {}
                achou("products", _preco(bbw.get("price")), bbw.get("item_id"))
            if id_ml.startswith("MLBU"):
                st, body = await _tentar(client, f"/user-products/{id_ml}")
                r["tentativas"]["user_products"] = st
                if body:
                    r["tentativas"]["user_products"]["campos"] = sorted(body)[:20]
                    r["tentativas"]["user_products"]["preco"] = None
            else:
                st, body = await _tentar(client, f"/products/{id_ml}/items", {"limit": 5})
                r["tentativas"]["products_items"] = st
                if body:
                    res = body.get("results") or []
                    achou("products_items", _preco(res[0].get("price")) if res else None,
                          res[0].get("item_id") if res else None)
        saida.append(r)
    return saida
