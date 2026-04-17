"""Testes do plugin question_dedup."""
import sqlite3
import pytest

from plugins.question_dedup import (
    jaccard_similarity,
    sequence_similarity,
    combined_similarity,
    dedup_insert,
    find_duplicate,
    ensure_times_asked_column,
)


def _minimal_schema(conn):
    conn.executescript("""
    CREATE TABLE generated_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        cycle_id INTEGER,
        question TEXT NOT NULL,
        context TEXT,
        category TEXT,
        priority INTEGER DEFAULT 0,
        answered INTEGER DEFAULT 0,
        times_asked INTEGER DEFAULT 1
    );
    """)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    _minimal_schema(c)
    c.commit()
    yield c
    c.close()


def test_jaccard_identicas():
    assert jaccard_similarity("abc def ghi", "abc def ghi") == 1.0


def test_sequence_similarity_identicas():
    assert sequence_similarity("mesmo texto", "mesmo texto") == 1.0


def test_combined_similarity_zero():
    assert combined_similarity("aaa bbb ccc", "xxx yyy zzz") < 0.3


def test_dedup_primeira_vez_insere(conn):
    status, rid = dedup_insert(conn, "Por que o token expira?")
    assert status == "inserted"
    assert rid > 0


def test_dedup_pergunta_identica_duplica(conn):
    dedup_insert(conn, "Como funciona o cache Redis aqui?")
    status, rid = dedup_insert(conn, "Como funciona o cache Redis aqui?")
    assert status == "duplicate"
    row = conn.execute("SELECT times_asked FROM generated_questions WHERE id=?", (rid,)).fetchone()
    assert row[0] == 2


def test_dedup_pergunta_similar_duplica(conn):
    dedup_insert(conn, "Por que o endpoint /vendas retorna 500?")
    status, _ = dedup_insert(
        conn, "Por que o endpoint /vendas retorna 500 sempre?"
    )
    assert status == "duplicate"


def test_dedup_pergunta_diferente_insere(conn):
    dedup_insert(conn, "Como configurar o cache Redis?")
    status, _ = dedup_insert(conn, "Qual o limite de conexões do PostgreSQL?")
    assert status == "inserted"


def test_dedup_preserva_metadata_na_primeira(conn):
    dedup_insert(
        conn,
        "Teste de metadata",
        cycle_id=42,
        context="contexto teste",
        category="cat",
        priority=5,
    )
    row = conn.execute(
        "SELECT cycle_id, context, category, priority FROM generated_questions"
    ).fetchone()
    assert row[0] == 42
    assert row[1] == "contexto teste"
    assert row[2] == "cat"
    assert row[3] == 5


def test_ensure_times_asked_column_idempotente(conn):
    ensure_times_asked_column(conn)
    ensure_times_asked_column(conn)  # não explode


def test_find_duplicate_retorna_none_se_vazio(conn):
    assert find_duplicate(conn, "qualquer coisa") is None


def test_dedup_incrementa_multiplas_vezes(conn):
    dedup_insert(conn, "mesma pergunta todo dia")
    for _ in range(3):
        dedup_insert(conn, "mesma pergunta todo dia")
    row = conn.execute(
        "SELECT times_asked FROM generated_questions WHERE question=?",
        ("mesma pergunta todo dia",),
    ).fetchone()
    assert row[0] == 4  # 1 insert + 3 reforços


def test_dedup_threshold_customizado(conn):
    dedup_insert(conn, "texto base A B C")
    # com threshold baixíssimo, qualquer coisa vira duplicata
    status, _ = dedup_insert(conn, "completamente outro", threshold=0.01)
    assert status == "duplicate"
