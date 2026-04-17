"""Testes do plugin cross_project_sync."""
import json
import sqlite3
import pytest

from plugins.cross_project_sync import export_knowledge, import_knowledge


def _schema(conn):
    conn.executescript("""
    CREATE TABLE learned_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        rule_text TEXT NOT NULL, source TEXT, confidence REAL DEFAULT 0.5,
        active INTEGER DEFAULT 1, tags TEXT
    );
    CREATE TABLE memory_patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        pattern_type TEXT, description TEXT NOT NULL, occurrences INTEGER DEFAULT 1,
        confidence REAL DEFAULT 0.5, standard_fix TEXT, active INTEGER DEFAULT 1
    );
    CREATE TABLE memory_semantic (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        category TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
        confidence REAL DEFAULT 0.5, UNIQUE(category, key)
    );
    """)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    _schema(c)
    c.commit()
    yield c
    c.close()


def test_export_vazio(conn, tmp_path):
    r = export_knowledge(conn, exports_dir=tmp_path)
    assert r["total"] == 0
    assert r["rules"] == 0


def test_export_regras_alta_confianca(conn, tmp_path):
    conn.execute("INSERT INTO learned_rules (rule_text, confidence) VALUES ('boa', 0.9)")
    conn.execute("INSERT INTO learned_rules (rule_text, confidence) VALUES ('fraca', 0.3)")
    conn.commit()
    r = export_knowledge(conn, confidence_threshold=0.8, exports_dir=tmp_path)
    assert r["rules"] == 1
    data = json.loads(open(r["path"], encoding="utf-8").read())
    assert data["rules"][0]["rule_text"] == "boa"


def test_export_inclui_patterns_e_knowledge(conn, tmp_path):
    conn.execute("INSERT INTO memory_patterns (pattern_type, description, confidence) VALUES ('bug','desc',0.9)")
    conn.execute("INSERT INTO memory_semantic (category, key, value, confidence) VALUES ('c','k','v',0.85)")
    conn.commit()
    r = export_knowledge(conn, confidence_threshold=0.8, exports_dir=tmp_path)
    assert r["patterns"] == 1
    assert r["knowledge"] == 1


def test_import_cria_novas_regras(conn, tmp_path):
    # Exporta de "projeto A"
    conn.execute("INSERT INTO learned_rules (rule_text, confidence) VALUES ('regra A', 0.9)")
    conn.commit()
    r = export_knowledge(conn, confidence_threshold=0.8, exports_dir=tmp_path)

    # Importa em "projeto B" (novo banco)
    conn2 = sqlite3.connect(":memory:")
    _schema(conn2)
    result = import_knowledge(conn2, r["path"])
    assert result["imported"] == 1
    row = conn2.execute("SELECT * FROM learned_rules").fetchone()
    assert row is not None
    conn2.close()


def test_import_reforco_nao_duplica(conn, tmp_path):
    conn.execute("INSERT INTO learned_rules (rule_text, confidence) VALUES ('mesma', 0.9)")
    conn.commit()
    r = export_knowledge(conn, confidence_threshold=0.8, exports_dir=tmp_path)
    # Importa no MESMO banco
    result = import_knowledge(conn, r["path"])
    assert result["reinforced"] == 1
    assert result["imported"] == 0
    count = conn.execute("SELECT COUNT(*) FROM learned_rules").fetchone()[0]
    assert count == 1  # não duplicou


def test_import_cap_confidence_em_07(conn, tmp_path):
    conn.execute("INSERT INTO learned_rules (rule_text, confidence) VALUES ('top', 0.99)")
    conn.commit()
    r = export_knowledge(conn, confidence_threshold=0.8, exports_dir=tmp_path)
    conn2 = sqlite3.connect(":memory:")
    _schema(conn2)
    import_knowledge(conn2, r["path"])
    row = conn2.execute("SELECT confidence FROM learned_rules").fetchone()
    assert row[0] <= 0.7  # cap na importação
    conn2.close()
