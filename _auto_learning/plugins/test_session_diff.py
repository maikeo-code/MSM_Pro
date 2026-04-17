"""Testes do plugin session_diff."""
import sqlite3
import pytest

from plugins.session_diff import what_changed


def _schema(conn):
    conn.executescript("""
    CREATE TABLE session_checkpoints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        cycle_id INTEGER, phase TEXT, resumed INTEGER DEFAULT 0
    );
    CREATE TABLE cycles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ended_at TIMESTAMP, status TEXT
    );
    CREATE TABLE feedbacks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        source TEXT, topic TEXT, question TEXT, answer TEXT
    );
    CREATE TABLE learned_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        rule_text TEXT, active INTEGER DEFAULT 1
    );
    CREATE TABLE falhas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        still_unresolved INTEGER DEFAULT 1, feedback_id INTEGER, topic TEXT, what_failed TEXT
    );
    CREATE TABLE human_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status TEXT DEFAULT 'PENDING', question TEXT
    );
    CREATE TABLE code_changes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        rolled_back INTEGER DEFAULT 0, file_path TEXT, change_type TEXT
    );
    CREATE TABLE agents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE, fitness_score REAL DEFAULT 50
    );
    CREATE TABLE agent_performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        agent_id INTEGER, agent_name TEXT, score_delta REAL DEFAULT 0
    );
    """)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    _schema(c)
    c.commit()
    yield c
    c.close()


def test_what_changed_sem_checkpoint(conn):
    md = what_changed(conn)
    assert "Resumo geral" in md
    assert "Ciclos completados" in md


def test_what_changed_com_dados(conn):
    conn.execute("INSERT INTO cycles (status) VALUES ('completed')")
    conn.execute("INSERT INTO feedbacks (source, topic, question, answer) VALUES ('a','b','c','d')")
    conn.execute("INSERT INTO learned_rules (rule_text) VALUES ('regra nova')")
    conn.execute("INSERT INTO falhas (still_unresolved, feedback_id, topic, what_failed) VALUES (1, 1, 't', 'f')")
    conn.commit()
    md = what_changed(conn)
    assert "1" in md  # pelo menos 1 ciclo
    assert "regra nova" in md


def test_what_changed_mostra_hip_pendente(conn):
    conn.execute("INSERT INTO human_questions (status, question) VALUES ('PENDING', 'teste')")
    conn.commit()
    md = what_changed(conn)
    assert "HIP pendentes" in md


def test_what_changed_formato_markdown(conn):
    md = what_changed(conn)
    assert md.startswith("## ")
    assert "- **" in md
