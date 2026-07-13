"""Testes do veredito INFO no harness de paridade (E43).

Visitas de um dia NAO FECHADO subcontam por natureza (snapshot parcial). Em vez de
poluir o placar com FAIL, essas divergencias viram INFO e saem do denominador do
parity_pct. Dia fechado continua PASS/FAIL normal. PASS nunca vira INFO.
"""
from app.vendas.service_parity_audit import (
    ALL_BLOCKS,
    DEFAULT_BLOCKS,
    KNOWN_BLOCKS,
    _check,
    _normalize_blocks,
    _verdict,
)


def test_check_info_converte_fail_em_info():
    # Divergencia (9 vs 7) com info=True -> INFO, nao FAIL.
    c = _check("visitas[MLB1]", 9, 7, info=True)
    assert c["verdict"] == "INFO"


def test_check_info_nao_afeta_pass():
    # Quando bate, info=True nao muda nada: continua PASS.
    c = _check("visitas[MLB1]", 7, 7, info=True)
    assert c["verdict"] == "PASS"


def test_check_sem_info_mantem_fail():
    # Dia fechado (info=False, padrao): divergencia continua FAIL.
    c = _check("visitas[MLB1]", 9, 7)
    assert c["verdict"] == "FAIL"


def test_check_info_nao_mexe_em_no_data():
    # app None -> NO_DATA, independentemente de info.
    c = _check("visitas[MLB1]", 9, None, info=True)
    assert c["verdict"] == "NO_DATA"


def test_verdict_tolerancia_relativa():
    # Sanidade do nucleo de verdict (nao regride com a mudanca do _check).
    assert _verdict(100, 100) == "PASS"
    assert _verdict(101, 100, tol=0.05) == "PASS"   # 1% dentro de 5%
    assert _verdict(110, 100, tol=0.05) == "FAIL"   # 10% fora de 5%
    assert _verdict(0, 0) == "PASS"
    assert _verdict(None, 100) == "NO_DATA"
    assert _verdict(100, None) == "ERROR"


def test_harness_estoque_usa_soma_de_variacoes_E42():
    """O harness deve computar ml_stock com a MESMA regra do sync (E9): itens com
    variacoes -> soma. Se voltar a usar available_quantity do topo, reintroduz o bug
    no verificador (falso-FAIL). Testa a fonte compartilhada."""
    from app.jobs.tasks_listings import stock_from_item

    item_com_variacoes = {
        "available_quantity": 19,  # topo subconta
        "variations": [
            {"available_quantity": 20},
            {"available_quantity": 30},
            {"available_quantity": 19},
        ],
    }
    assert stock_from_item(item_com_variacoes) == 69  # painel do ML

    item_sem_variacoes = {"available_quantity": 33, "variations": []}
    assert stock_from_item(item_sem_variacoes) == 33


# ─── E37: blocos plugaveis ──────────────────────────────────────────────────

def test_normalize_blocks_none_vira_default():
    assert _normalize_blocks(None) == frozenset(DEFAULT_BLOCKS)
    assert _normalize_blocks(set()) == frozenset(DEFAULT_BLOCKS)


def test_normalize_blocks_subconjunto():
    assert _normalize_blocks({"sales"}) == frozenset({"sales"})
    assert _normalize_blocks({"sales", "reputation"}) == frozenset({"sales", "reputation"})


def test_normalize_blocks_ignora_desconhecido_e_normaliza_caixa():
    # nomes desconhecidos sao descartados; caixa e espacos normalizados.
    assert _normalize_blocks({" Sales ", "banana"}) == frozenset({"sales"})


def test_normalize_blocks_so_desconhecido_vira_default():
    # se sobrar vazio apos filtrar, roda o DEFAULT (nunca placar vazio por engano).
    assert _normalize_blocks({"banana", "xyz"}) == frozenset(DEFAULT_BLOCKS)


def test_shipping_e_opt_in_fora_do_default():
    # 'shipping' e um bloco valido (KNOWN) mas NAO roda por padrao (opt-in): faz 1
    # chamada de /shipments/{id}/costs por pedido -> pesado, fora do gate rapido.
    assert "shipping" in KNOWN_BLOCKS
    assert "shipping" not in DEFAULT_BLOCKS
    # pedido explicito respeita shipping
    assert _normalize_blocks({"shipping"}) == frozenset({"shipping"})
    # default NAO inclui shipping
    assert "shipping" not in _normalize_blocks(None)


def test_all_blocks_retrocompat_igual_default():
    assert frozenset(ALL_BLOCKS) == frozenset(DEFAULT_BLOCKS)
