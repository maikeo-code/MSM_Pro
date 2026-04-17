"""Testes do plugin daily_consolidator."""
import sqlite3
from datetime import datetime, timedelta, date

import pytest

from plugins.daily_consolidator import (
    jaccard,
    cluster_episodes,
    summarize_cluster,
    consolidate_day,
    apply_decay,
)


def _minimal_schema(conn):
    conn.executescript("""
    CREATE TABLE memory_episodic (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        cycle_id INTEGER,
        agent_name TEXT,
        action TEXT,
        target TEXT,
        result TEXT,
        details TEXT
    );
    CREATE TABLE memory_semantic (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        category TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        confidence REAL DEFAULT 0.5,
        UNIQUE(category, key)
    );
    """)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    _minimal_schema(c)
    c.commit()
    yield c
    c.close()


# ---------- jaccard ----------

def test_jaccard_identicos():
    assert jaccard("texto igual aqui", "texto igual aqui") == 1.0


def test_jaccard_vazio_vs_vazio():
    assert jaccard("", "") == 1.0


def test_jaccard_disjunto():
    assert jaccard("aaa bbb ccc", "xxx yyy zzz") == 0.0


def test_jaccard_parcial():
    sim = jaccard("python rocks ok", "python ok yes")
    assert 0 < sim < 1


# ---------- clustering ----------

def test_cluster_agrupa_por_agente_e_acao():
    episodes = [
        {"agent_name": "a", "action": "x", "details": "foo bar"},
        {"agent_name": "a", "action": "x", "details": "foo bar"},
        {"agent_name": "a", "action": "y", "details": "foo bar"},
    ]
    clusters = cluster_episodes(episodes)
    assert len(clusters) == 2


def test_cluster_separa_detalhes_muito_diferentes():
    episodes = [
        {"agent_name": "a", "action": "x", "details": "alpha beta gamma"},
        {"agent_name": "a", "action": "x", "details": "zeta omega delta"},
    ]
    clusters = cluster_episodes(episodes, similarity_threshold=0.8)
    assert len(clusters) == 2


def test_cluster_junta_detalhes_similares():
    episodes = [
        {"agent_name": "a", "action": "x", "details": "login oauth token falhou"},
        {"agent_name": "a", "action": "x", "details": "login oauth token expirou"},
        {"agent_name": "a", "action": "x", "details": "login oauth token invalido"},
    ]
    clusters = cluster_episodes(episodes, similarity_threshold=0.4)
    assert len(clusters) == 1
    assert len(clusters[0]) == 3


# ---------- summarize ----------

def test_summarize_cluster_formato_basico():
    cluster = [
        {"agent_name": "dev", "action": "fix", "target": "auth.py", "result": "success"},
        {"agent_name": "dev", "action": "fix", "target": "auth.py", "result": "success"},
    ]
    s = summarize_cluster(cluster)
    assert s["category"] == "consolidated_dev"
    assert s["key"] == "fix"
    assert "2 ocorrências" in s["value"]
    assert "auth.py" in s["value"]
    assert 0 < s["confidence"] <= 0.95


# ---------- consolidate_day ----------

def _insert_episode(conn, agent, action, target, result, details):
    conn.execute(
        """INSERT INTO memory_episodic (agent_name, action, target, result, details)
           VALUES (?, ?, ?, ?, ?)""",
        (agent, action, target, result, details),
    )


def test_consolidate_day_cria_semantic_para_cluster_grande(conn):
    for i in range(3):
        _insert_episode(
            conn, "dev", "edit_file", f"file{i}.py", "success",
            "refatoracao de funcao duplicada",
        )
    conn.commit()
    stats = consolidate_day(conn)
    assert stats["episodes"] == 3
    assert stats["created"] == 1
    row = conn.execute("SELECT * FROM memory_semantic").fetchone()
    assert row is not None


def test_consolidate_day_ignora_clusters_pequenos(conn):
    _insert_episode(conn, "dev", "edit_file", "a.py", "success", "detalhe x")
    _insert_episode(conn, "dev", "edit_file", "b.py", "success", "detalhe x")
    conn.commit()
    stats = consolidate_day(conn, min_cluster_size=3)
    assert stats["created"] == 0


def test_consolidate_day_reforco_em_segunda_rodada(conn):
    for i in range(3):
        _insert_episode(conn, "dev", "fix", "x.py", "success", "texto")
    conn.commit()
    s1 = consolidate_day(conn)
    s2 = consolidate_day(conn)
    assert s1["created"] == 1
    assert s2["reinforced"] >= 1 or s2["created"] == 0


def test_consolidate_day_dia_vazio(conn):
    stats = consolidate_day(conn)
    assert stats["episodes"] == 0
    assert stats["created"] == 0


# ---------- decay ----------

def test_apply_decay_reduz_confidence_de_antigas(conn):
    old = (datetime.now() - timedelta(days=60)).isoformat(sep=" ", timespec="seconds")
    conn.execute(
        "INSERT INTO memory_semantic (category, key, value, confidence, updated_at) "
        "VALUES ('c','k','v', 0.9, ?)",
        (old,),
    )
    conn.commit()
    n = apply_decay(conn, days=30)
    assert n == 1
    row = conn.execute("SELECT confidence FROM memory_semantic").fetchone()
    assert row[0] < 0.9


def test_apply_decay_poupa_recentes(conn):
    conn.execute(
        "INSERT INTO memory_semantic (category, key, value, confidence) "
        "VALUES ('c','k','v', 0.9)"
    )
    conn.commit()
    n = apply_decay(conn, days=30)
    assert n == 0


def test_apply_decay_respeita_minimo(conn):
    old = (datetime.now() - timedelta(days=60)).isoformat(sep=" ", timespec="seconds")
    conn.execute(
        "INSERT INTO memory_semantic (category, key, value, confidence, updated_at) "
        "VALUES ('c','k','v', 0.05, ?)",
        (old,),
    )
    conn.commit()
    apply_decay(conn)
    row = conn.execute("SELECT confidence FROM memory_semantic").fetchone()
    assert row[0] >= 0.1  # não pode descer abaixo de MIN
