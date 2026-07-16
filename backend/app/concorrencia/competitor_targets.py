"""IDs de concorrentes monitorados (conta SC) — coleta diária de preço.

Mapa estático dos 11 concorrentes vinculados a 3 anúncios nossos. A tabela
`competitor_prices` é FLAT por `id_ml`; este módulo é a fonte da LISTA + a
rastreabilidade (qual concorrente é de qual anúncio nosso) e o classificador
item vs catálogo.

Classificação (regra do ML):
  - item     → MLB + ~10 dígitos → GET /items/{id}
  - catálogo → MLBU… ou MLB + ~8 dígitos → GET /products/{id} (buy_box_winner)
"""

# (nosso_mlb, nosso_sku, [concorrentes id_ml])
COMPETITOR_GROUPS: list[tuple[str, str, list[str]]] = [
    (
        "MLB3967373421",  # Cesto
        "76692009",
        [
            "MLB4185585590",
            "MLB4664920981",
            "MLB5496628754",
            "MLB6429093518",
            "MLB6460154858",
        ],
    ),
    (
        "MLB4642444149",  # Kit 5
        "50115746",
        [
            "MLB66736353",   # 8 díg → catálogo
            "MLB66987007",   # 8 díg → catálogo
            "MLB68602042",   # 8 díg → catálogo
            "MLBU3453370601",  # MLBU → catálogo
        ],
    ),
    (
        "MLB6686654478",  # Kit 6
        "50412847",
        [
            "MLB3377496529",
            "MLB4130481127",
        ],
    ),
]

# Lista achatada de todos os id_ml a coletar (sem duplicatas, ordem preservada).
COMPETITOR_TARGETS: list[str] = []
for _our_mlb, _our_sku, _competitors in COMPETITOR_GROUPS:
    for _cid in _competitors:
        if _cid not in COMPETITOR_TARGETS:
            COMPETITOR_TARGETS.append(_cid)


def is_catalog_id(id_ml: str) -> bool:
    """True se o ID é de CATÁLOGO (usar /products/{id}), False se item (/items/{id}).

    Catálogo = prefixo MLBU… OU MLB seguido de menos de 10 dígitos (tipicamente 8).
    Item = MLB + 10 dígitos.
    """
    s = (id_ml or "").upper().strip()
    if s.startswith("MLBU"):
        return True
    digits = s[3:] if s.startswith("MLB") else s
    return digits.isdigit() and len(digits) < 10
