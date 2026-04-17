"""Testes do plugin tiered_autonomy."""
import sqlite3
import time
from datetime import datetime, timedelta

import pytest

from plugins.tiered_autonomy import (
    init_schema,
    get_tier,
    set_tier,
    guard,
    audit,
    verify_audit_chain,
    record_outcome,
    is_dormant,
    ActionBlocked,
    ERR_THRESHOLD,
    KILL_THRESHOLD,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    init_schema(c)
    c.commit()
    yield c
    c.close()


# ---------- schema / tier lookup ----------

def test_init_schema_cria_tabelas(conn):
    tables = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert {"action_tiers", "agent_breakers", "audit_log"} <= tables


def test_default_tier_read_file_eh_l0(conn):
    tier, human = get_tier(conn, "read_file")
    assert tier == "L0"
    assert human is False


def test_default_tier_edit_file_eh_l3_com_humano(conn):
    tier, human = get_tier(conn, "edit_file")
    assert tier == "L3"
    assert human is True


def test_default_tier_deploy_eh_l4(conn):
    tier, human = get_tier(conn, "deploy")
    assert tier == "L4"
    assert human is True


def test_action_desconhecida_default_l3(conn):
    tier, human = get_tier(conn, "acao_nunca_vista")
    assert tier == "L3"
    assert human is True


def test_set_tier_upsert(conn):
    set_tier(conn, "minha_acao", "L1", False)
    assert get_tier(conn, "minha_acao") == ("L1", False)
    set_tier(conn, "minha_acao", "L4", True)
    assert get_tier(conn, "minha_acao") == ("L4", True)


# ---------- guard() ----------

def test_guard_allowed_l0(conn):
    outcome = guard(conn, "curiosa", "read_file", target="a.py")
    assert outcome == "allowed"


def test_guard_pending_human_em_l3(conn):
    outcome = guard(conn, "developer", "edit_file", target="b.py")
    assert outcome == "pending_human"


def test_guard_audit_grava_entrada(conn):
    guard(conn, "curiosa", "read_file", target="x")
    rows = conn.execute("SELECT * FROM audit_log").fetchall()
    assert len(rows) == 1


def test_guard_bloqueia_agente_killed(conn):
    # mata explicitamente
    conn.execute(
        "INSERT INTO agent_breakers (agent_name, killed, killed_reason) VALUES (?, 1, 'test')",
        ("badguy",),
    )
    with pytest.raises(ActionBlocked):
        guard(conn, "badguy", "read_file", target="x")


def test_guard_bloqueia_dormant(conn):
    future = (datetime.now() + timedelta(hours=1)).isoformat(sep=" ", timespec="seconds")
    conn.execute(
        "INSERT INTO agent_breakers (agent_name, dormant_until) VALUES (?, ?)",
        ("sleeper", future),
    )
    with pytest.raises(ActionBlocked):
        guard(conn, "sleeper", "read_file", target="x")


def test_guard_dormant_passado_nao_bloqueia(conn):
    past = (datetime.now() - timedelta(hours=1)).isoformat(sep=" ", timespec="seconds")
    conn.execute(
        "INSERT INTO agent_breakers (agent_name, dormant_until) VALUES (?, ?)",
        ("wakeup", past),
    )
    outcome = guard(conn, "wakeup", "read_file", target="x")
    assert outcome == "allowed"


def test_guard_killswitch_por_repeticao(conn):
    # 5 tentativas da mesma ação => kill na 5ª+1
    for i in range(KILL_THRESHOLD):
        guard(conn, "loopy", "read_file", target="same")
    # próxima deve matar
    with pytest.raises(ActionBlocked):
        guard(conn, "loopy", "read_file", target="same")
    # agente agora aparece killed
    row = conn.execute(
        "SELECT killed FROM agent_breakers WHERE agent_name='loopy'"
    ).fetchone()
    assert row[0] == 1


# ---------- circuit breaker de erro consecutivo ----------

def test_record_outcome_erros_ativam_dormant(conn):
    for _ in range(ERR_THRESHOLD):
        record_outcome(conn, "falho", success=False)
    assert is_dormant(conn, "falho") is True


def test_record_outcome_sucesso_zera_contador(conn):
    record_outcome(conn, "misto", success=False)
    record_outcome(conn, "misto", success=False)
    record_outcome(conn, "misto", success=True)  # zera
    record_outcome(conn, "misto", success=False)
    assert is_dormant(conn, "misto") is False


# ---------- audit hash encadeado ----------

def test_audit_chain_integra(conn):
    audit(conn, "a1", "read_file", "x", "L0", "allowed")
    audit(conn, "a1", "save_episode", None, "L1", "allowed", {"k": "v"})
    audit(conn, "a2", "edit_file", "y.py", "L3", "pending_human")
    ok, bad = verify_audit_chain(conn)
    assert ok is True
    assert bad is None


def test_audit_chain_detecta_tampering(conn):
    audit(conn, "a1", "read_file", "x", "L0", "allowed")
    audit(conn, "a1", "save_episode", None, "L1", "allowed")
    audit(conn, "a2", "read_file", "z", "L0", "allowed")
    # adultera o payload do registro 2 sem recalcular hash
    conn.execute("UPDATE audit_log SET target='ADULTERADO' WHERE id=2")
    ok, bad = verify_audit_chain(conn)
    assert ok is False
    assert bad == 2


def test_audit_hash_muda_com_conteudo(conn):
    h1 = audit(conn, "a", "read_file", "x", "L0", "allowed")
    h2 = audit(conn, "a", "read_file", "y", "L0", "allowed")
    assert h1 != h2


def test_audit_prev_hash_liga_registros(conn):
    h1 = audit(conn, "a", "read_file", "x", "L0", "allowed")
    h2 = audit(conn, "a", "read_file", "y", "L0", "allowed")
    row = conn.execute("SELECT prev_hash FROM audit_log WHERE hash=?", (h2,)).fetchone()
    assert row[0] == h1
