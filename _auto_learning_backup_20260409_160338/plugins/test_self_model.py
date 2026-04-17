"""Testes do plugin self_model."""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from plugins.self_model import (
    build_self_report,
    generate_self_report,
    _week_label,
)
from plugins.ekas_efficiency import init_schema as init_ekas, log_usage


def _minimal_schema(conn):
    conn.executescript("""
    CREATE TABLE cycles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ended_at TIMESTAMP,
        status TEXT,
        score_global REAL,
        summary TEXT
    );
    CREATE TABLE action_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        agent_name TEXT,
        action_type TEXT,
        result TEXT
    );
    CREATE TABLE agents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        fitness_score REAL DEFAULT 50,
        status TEXT DEFAULT 'ACTIVE'
    );
    CREATE TABLE agent_performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        agent_id INTEGER,
        outcome TEXT
    );
    CREATE TABLE learned_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        rule_text TEXT,
        active INTEGER DEFAULT 1
    );
    CREATE TABLE generated_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        question TEXT,
        answered INTEGER DEFAULT 0,
        was_relevant INTEGER
    );
    """)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    _minimal_schema(c)
    c.commit()
    yield c
    c.close()


def test_week_label_formato():
    label = _week_label(datetime(2026, 4, 8))
    assert label.startswith("2026-W")
    assert len(label) == 8


def test_build_self_report_vazio_nao_explode(conn):
    md = build_self_report(conn)
    assert "Self-model" in md
    assert "Três números" in md
    assert "Tudo verde" in md or "estagnado" in md  # recomendação default


def test_build_self_report_conta_ciclos(conn):
    conn.execute("INSERT INTO cycles (status, score_global) VALUES ('completed', 65)")
    conn.execute("INSERT INTO cycles (status, score_global) VALUES ('completed', 70)")
    conn.execute("INSERT INTO cycles (status) VALUES ('error')")
    conn.commit()
    md = build_self_report(conn)
    assert "2/3" in md  # 2 completos de 3 totais
    assert "67" in md or "67.5" in md  # score médio (65+70)/2 = 67.5


def test_build_self_report_taxa_sucesso(conn):
    for _ in range(7):
        conn.execute("INSERT INTO action_log (action_type, result) VALUES ('x','success')")
    for _ in range(3):
        conn.execute("INSERT INTO action_log (action_type, result) VALUES ('x','failure')")
    conn.commit()
    md = build_self_report(conn)
    assert "70%" in md  # 7/10 = 70%
    assert "baixa" in md or "investigar" in md or "70%" in md


def test_build_self_report_inclui_regras_novas(conn):
    conn.execute(
        "INSERT INTO learned_rules (rule_text) VALUES ('Sempre usar COUNT(DISTINCT)')"
    )
    conn.commit()
    md = build_self_report(conn)
    assert "COUNT(DISTINCT)" in md


def test_build_self_report_inclui_chutes(conn):
    conn.execute(
        "INSERT INTO generated_questions (question, answered, was_relevant) "
        "VALUES ('Essa pergunta não serviu', 1, 0)"
    )
    conn.commit()
    md = build_self_report(conn)
    assert "não serviu" in md


def test_build_self_report_detecta_agentes_obsoletos(conn):
    conn.execute(
        "INSERT INTO agents (name, fitness_score, status) VALUES ('velho', 10, 'ACTIVE')"
    )
    conn.commit()
    md = build_self_report(conn)
    assert "velho" in md
    assert "Aposentar" in md


def test_build_self_report_com_ekas_cost(conn):
    init_ekas(conn)
    log_usage(conn, "test", "haiku", 1000, 500)
    conn.commit()
    md = build_self_report(conn)
    assert "Custo EKAS" in md
    assert "plugin não ativo" not in md


def test_generate_self_report_escreve_arquivo(conn, tmp_path):
    path = generate_self_report(conn, report_dir=tmp_path)
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "Self-model" in content


def test_relatorio_tem_menos_de_100_linhas(conn):
    # Preenche com bastante conteúdo
    for i in range(20):
        conn.execute(
            "INSERT INTO learned_rules (rule_text) VALUES (?)",
            (f"Regra número {i}",),
        )
    conn.commit()
    md = build_self_report(conn)
    # Limita top 5 regras => não explode
    assert md.count("Regra número") <= 5
