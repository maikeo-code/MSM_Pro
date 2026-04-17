"""Testes do plugin functional_emotions."""
import sqlite3
import pytest

from plugins.functional_emotions import (
    init_schema,
    get_emotions,
    set_emotions,
    on_agent_used,
    on_agent_rested,
    on_low_confidence_area,
    on_area_explored,
    update_after_action,
    choose_agent,
    score_agent_for_task,
    needs_human_gate,
    BOREDOM_INCREMENT,
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
        "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_emotions'"
    ).fetchone()
    assert row is not None


def test_get_emotions_cria_default(conn):
    em = get_emotions(conn, "novo")
    assert em["boredom"] == 0.0
    assert em["curiosity"] == 0.5
    assert em["fear"] == 0.0
    assert em["joy"] == 0.0


def test_set_emotions_clampeia(conn):
    set_emotions(conn, "a", boredom=5.0, fear=-1.0)
    em = get_emotions(conn, "a")
    assert em["boredom"] == 1.0
    assert em["fear"] == 0.0


def test_on_agent_used_incrementa_boredom(conn):
    on_agent_used(conn, "a")
    on_agent_used(conn, "a")
    em = get_emotions(conn, "a")
    assert em["boredom"] == pytest.approx(BOREDOM_INCREMENT * 2, rel=1e-6)


def test_on_agent_used_nao_passa_de_1(conn):
    for _ in range(100):
        on_agent_used(conn, "a")
    em = get_emotions(conn, "a")
    assert em["boredom"] == 1.0


def test_on_agent_rested_reduz_boredom(conn):
    set_emotions(conn, "a", boredom=0.8)
    on_agent_rested(conn, "a")
    em = get_emotions(conn, "a")
    assert em["boredom"] < 0.8


def test_on_low_confidence_sobe_curiosity(conn):
    before = get_emotions(conn, "a")["curiosity"]
    on_low_confidence_area(conn, "a")
    after = get_emotions(conn, "a")["curiosity"]
    assert after > before


def test_on_area_explored_decai_curiosity(conn):
    set_emotions(conn, "a", curiosity=0.9)
    on_area_explored(conn, "a")
    em = get_emotions(conn, "a")
    assert em["curiosity"] < 0.9
    assert em["curiosity"] >= 0.1  # piso


def test_update_after_falha_sobe_fear(conn):
    update_after_action(conn, "a", success=False)
    em = get_emotions(conn, "a")
    assert em["fear"] > 0


def test_update_sucesso_decai_fear(conn):
    set_emotions(conn, "a", fear=0.5)
    update_after_action(conn, "a", success=True)
    em = get_emotions(conn, "a")
    assert em["fear"] < 0.5


def test_update_humano_aprovou_sobe_joy(conn):
    update_after_action(conn, "a", success=True, human_approved=True)
    em = get_emotions(conn, "a")
    assert em["joy"] > 0


def test_choose_agent_vazio_retorna_none(conn):
    assert choose_agent(conn, []) is None


def test_choose_agent_unico_retorna_ele(conn):
    assert choose_agent(conn, ["solo"]) == "solo"


def test_choose_agent_prefere_menos_entediado(conn):
    set_emotions(conn, "cansado", boredom=0.9)
    set_emotions(conn, "descansado", boredom=0.0)
    chosen = choose_agent(conn, ["cansado", "descansado"])
    assert chosen == "descansado"


def test_choose_agent_prefere_mais_curioso(conn):
    set_emotions(conn, "apatico", curiosity=0.1)
    set_emotions(conn, "curioso", curiosity=0.9)
    chosen = choose_agent(conn, ["apatico", "curioso"])
    assert chosen == "curioso"


def test_choose_agent_evita_com_medo(conn):
    set_emotions(conn, "medroso", fear=0.9)
    set_emotions(conn, "normal", fear=0.0)
    chosen = choose_agent(conn, ["medroso", "normal"])
    assert chosen == "normal"


def test_score_agent_para_task_monotonico():
    low_curio = {"boredom": 0, "curiosity": 0.1, "fear": 0, "joy": 0}
    high_curio = {"boredom": 0, "curiosity": 0.9, "fear": 0, "joy": 0}
    assert score_agent_for_task(high_curio) > score_agent_for_task(low_curio)


def test_needs_human_gate_com_fear_alto(conn):
    set_emotions(conn, "stressed", fear=0.7)
    assert needs_human_gate(conn, "stressed") is True


def test_needs_human_gate_com_fear_baixo(conn):
    set_emotions(conn, "chill", fear=0.1)
    assert needs_human_gate(conn, "chill") is False
