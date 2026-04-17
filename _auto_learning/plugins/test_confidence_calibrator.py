"""Testes do plugin confidence_calibrator."""
import sqlite3
import pytest

from plugins.confidence_calibrator import (
    init_schema,
    record_prediction,
    compute_calibration,
    generate_calibration_report,
    auto_adjust_confidence,
)


def _full_schema(conn):
    conn.executescript("""
    CREATE TABLE learned_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_text TEXT, confidence REAL DEFAULT 0.5, active INTEGER DEFAULT 1
    );
    CREATE TABLE memory_patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT, confidence REAL DEFAULT 0.5, active INTEGER DEFAULT 1
    );
    """)
    init_schema(conn)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    _full_schema(c)
    c.commit()
    yield c
    c.close()


def test_init_schema_cria_tabela(conn):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='calibration_log'"
    ).fetchone()
    assert row is not None


def test_record_prediction_persiste(conn):
    record_prediction(conn, "rule", 1, 0.9, True, "teste")
    row = conn.execute("SELECT * FROM calibration_log").fetchone()
    assert row is not None


def test_compute_calibration_vazio(conn):
    cal = compute_calibration(conn)
    assert cal["total_predictions"] == 0
    assert cal["brier_score"] is None


def test_compute_calibration_perfeita(conn):
    # Previu 0.9 e acertou todas
    for _ in range(10):
        record_prediction(conn, "rule", 1, 0.9, True)
    cal = compute_calibration(conn)
    assert cal["brier_score"] < 0.02
    assert cal["buckets"]["0.9-1.0"]["actual"] == 1.0


def test_compute_calibration_overconfident(conn):
    # Previu 0.9 mas acertou 50%
    for i in range(10):
        record_prediction(conn, "rule", 1, 0.9, i % 2 == 0)
    cal = compute_calibration(conn)
    bucket = cal["buckets"]["0.9-1.0"]
    assert bucket["error"] > 0.3  # overconfident


def test_generate_report_markdown(conn):
    for i in range(5):
        record_prediction(conn, "rule", 1, 0.8, True)
    md = generate_calibration_report(conn)
    assert "Calibração" in md
    assert "Brier Score" in md


def test_generate_report_vazio(conn):
    md = generate_calibration_report(conn)
    assert "Nenhuma previsão" in md


def test_auto_adjust_overconfident(conn):
    # Regra com confidence 0.9 mas acerta só 50%
    conn.execute("INSERT INTO learned_rules (rule_text, confidence) VALUES ('r1', 0.9)")
    conn.commit()
    for i in range(10):
        record_prediction(conn, "rule", 1, 0.9, i % 2 == 0)
    conn.commit()
    n = auto_adjust_confidence(conn, min_samples=5)
    assert n >= 1
    new_conf = conn.execute("SELECT confidence FROM learned_rules WHERE id=1").fetchone()[0]
    assert new_conf < 0.9  # ajustou pra baixo


def test_auto_adjust_underconfident(conn):
    conn.execute("INSERT INTO learned_rules (rule_text, confidence) VALUES ('r1', 0.3)")
    conn.commit()
    for _ in range(10):
        record_prediction(conn, "rule", 1, 0.3, True)  # acerta tudo com conf baixa
    conn.commit()
    auto_adjust_confidence(conn, min_samples=5)
    new_conf = conn.execute("SELECT confidence FROM learned_rules WHERE id=1").fetchone()[0]
    assert new_conf > 0.3  # ajustou pra cima


def test_auto_adjust_ignora_poucos_samples(conn):
    conn.execute("INSERT INTO learned_rules (rule_text, confidence) VALUES ('r1', 0.9)")
    conn.commit()
    record_prediction(conn, "rule", 1, 0.9, False)  # só 1 sample
    conn.commit()
    n = auto_adjust_confidence(conn, min_samples=5)
    assert n == 0  # não ajustou
