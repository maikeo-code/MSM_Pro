"""
Plugin 3.7 — question_dedup

Evita que a agente 'curiosa' gere a mesma pergunta várias vezes.
Usa Jaccard + SequenceMatcher para encontrar duplicatas nas últimas N
perguntas. Se a nova pergunta for muito parecida com uma já existente,
descarta e incrementa um contador de "times_asked" na original.

Uso:
    from plugins.question_dedup import dedup_insert
    status = dedup_insert(conn, "Por que o endpoint /x retorna 500?", cycle_id=42)
    # status == 'inserted' | 'duplicate' (id da original em row_id)
"""

from __future__ import annotations

import re
import sqlite3
from difflib import SequenceMatcher
from typing import Optional


SIMILARITY_THRESHOLD = 0.85
WINDOW_SIZE = 200


SCHEMA_PATCH_SQL = """
-- Adiciona coluna times_asked se não existir (coluna opcional no plugin).
-- SQLite não tem 'ADD COLUMN IF NOT EXISTS', então usamos PRAGMA check.
"""


def ensure_times_asked_column(conn: sqlite3.Connection) -> None:
    """Adiciona coluna times_asked a generated_questions se faltar."""
    cols = {
        r[1]
        for r in conn.execute("PRAGMA table_info(generated_questions)").fetchall()
    }
    if "times_asked" not in cols:
        try:
            conn.execute(
                "ALTER TABLE generated_questions ADD COLUMN times_asked INTEGER DEFAULT 1"
            )
        except sqlite3.OperationalError:
            pass  # tabela pode não existir em ambiente de teste isolado


# ---------------------------------------------------------------------------
# Similaridade
# ---------------------------------------------------------------------------
_TOKEN_RE = re.compile(r"[a-zA-ZÀ-ÿ0-9_]+")


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "") if len(t) > 2}


def jaccard_similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def sequence_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def combined_similarity(a: str, b: str) -> float:
    """Média ponderada: Jaccard pega sinônimos, SequenceMatcher pega frases."""
    return 0.5 * jaccard_similarity(a, b) + 0.5 * sequence_similarity(a, b)


# ---------------------------------------------------------------------------
# Lookup e insert
# ---------------------------------------------------------------------------
def find_duplicate(
    conn: sqlite3.Connection,
    question: str,
    window: int = WINDOW_SIZE,
    threshold: float = SIMILARITY_THRESHOLD,
) -> Optional[int]:
    """
    Procura duplicata nas últimas `window` perguntas. Retorna id da original
    ou None se não encontrou.
    """
    rows = conn.execute(
        """
        SELECT id, question FROM generated_questions
        ORDER BY id DESC LIMIT ?
        """,
        (window,),
    ).fetchall()
    for rid, existing in rows:
        if combined_similarity(question, existing or "") >= threshold:
            return rid
    return None


def dedup_insert(
    conn: sqlite3.Connection,
    question: str,
    *,
    cycle_id: Optional[int] = None,
    context: Optional[str] = None,
    category: Optional[str] = None,
    priority: int = 0,
    window: int = WINDOW_SIZE,
    threshold: float = SIMILARITY_THRESHOLD,
) -> tuple[str, int]:
    """
    Insere em generated_questions se for nova.
    Se for duplicata, incrementa times_asked da original.

    Retorna (status, row_id) onde status é 'inserted' ou 'duplicate'.
    """
    ensure_times_asked_column(conn)

    dup_id = find_duplicate(conn, question, window=window, threshold=threshold)
    if dup_id is not None:
        conn.execute(
            "UPDATE generated_questions SET times_asked = COALESCE(times_asked, 1) + 1 "
            "WHERE id=?",
            (dup_id,),
        )
        return ("duplicate", dup_id)

    cur = conn.execute(
        """
        INSERT INTO generated_questions
          (question, context, category, priority, cycle_id, times_asked)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (question, context, category, priority, cycle_id),
    )
    return ("inserted", cur.lastrowid)
