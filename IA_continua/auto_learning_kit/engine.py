"""
============================================================
MOTOR DE AUTO-APRENDIZADO
============================================================
Gerencia o ciclo infinito de perguntas, respostas, confrontos
e aprendizado entre múltiplas IAs.

Uso:
    python engine.py                    # inicia o loop
    python engine.py --cycles 10        # roda 10 ciclos
    python engine.py --export           # exporta dados
    python engine.py --status           # mostra status atual
============================================================
"""

import sqlite3
import json
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

# ============================================================
# CONFIGURAÇÃO
# ============================================================
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "db" / "learning.db"
LOGS_DIR = BASE_DIR / "logs"
EXPORTS_DIR = BASE_DIR / "exports"

# ============================================================
# BANCO DE DADOS
# ============================================================
class LearningDB:
    """Gerencia todas operações do banco de auto-aprendizado."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self):
        """Cria o banco se não existir."""
        schema_path = BASE_DIR / "db" / "schema.sql"
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        with open(schema_path, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
        conn.close()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    # ---------- CICLOS ----------
    def start_cycle(self) -> int:
        conn = self._conn()
        cur = conn.execute("INSERT INTO cycles (status) VALUES ('running')")
        cycle_id = cur.lastrowid
        conn.commit()
        conn.close()
        return cycle_id

    def end_cycle(self, cycle_id: int, summary: str = ""):
        conn = self._conn()
        conn.execute("""
            UPDATE cycles SET ended_at = CURRENT_TIMESTAMP, status = 'completed', summary = ?
            WHERE id = ?
        """, (summary, cycle_id))
        conn.commit()
        conn.close()

    def cancel_cycle(self, cycle_id: int):
        conn = self._conn()
        conn.execute("""
            UPDATE cycles SET ended_at = CURRENT_TIMESTAMP, status = 'cancelled'
            WHERE id = ?
        """, (cycle_id,))
        conn.commit()
        conn.close()

    # ---------- FEEDBACKS ----------
    def register_feedback(self, source: str, topic: str, question: str, answer: str,
                          feedback_text: str = "", sentiment: str = "neutro",
                          confidence: float = 0.5, cycle_id: int = None,
                          parent_id: int = None, tags: list = None) -> int:
        conn = self._conn()
        cur = conn.execute("""
            INSERT INTO feedbacks (source, topic, question, answer, feedback_text,
                                   sentiment, confidence, cycle_id, parent_id, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (source, topic, question, answer, feedback_text, sentiment,
              confidence, cycle_id, parent_id, json.dumps(tags or [])))
        fid = cur.lastrowid
        conn.commit()
        conn.close()
        return fid

    def get_feedback(self, feedback_id: int) -> Optional[dict]:
        conn = self._conn()
        row = conn.execute("SELECT * FROM feedbacks WHERE id = ?", (feedback_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_feedbacks_by_topic(self, topic: str, limit: int = 50) -> list:
        conn = self._conn()
        rows = conn.execute("""
            SELECT * FROM feedbacks WHERE topic LIKE ? ORDER BY created_at DESC LIMIT ?
        """, (f"%{topic}%", limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ---------- SUCESSOS ----------
    def register_success(self, feedback_id: int, topic: str, insight: str,
                         evidence: str = "", relevance_score: float = 0.5,
                         tags: list = None) -> int:
        conn = self._conn()
        # Verifica se já existe insight similar
        existing = conn.execute("""
            SELECT id, times_confirmed FROM sucessos WHERE topic = ? AND insight = ?
        """, (topic, insight)).fetchone()

        if existing:
            conn.execute("""
                UPDATE sucessos SET times_confirmed = times_confirmed + 1,
                relevance_score = MIN(1.0, relevance_score + 0.1)
                WHERE id = ?
            """, (existing["id"],))
            sid = existing["id"]
        else:
            cur = conn.execute("""
                INSERT INTO sucessos (feedback_id, topic, insight, evidence, relevance_score, tags)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (feedback_id, topic, insight, evidence, relevance_score, json.dumps(tags or [])))
            sid = cur.lastrowid
        conn.commit()
        conn.close()
        return sid

    def get_top_successes(self, limit: int = 20) -> list:
        conn = self._conn()
        rows = conn.execute("""
            SELECT * FROM sucessos ORDER BY relevance_score DESC, times_confirmed DESC LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ---------- FALHAS ----------
    def register_failure(self, feedback_id: int, topic: str, what_failed: str,
                         why_failed: str = "", tags: list = None) -> int:
        conn = self._conn()
        existing = conn.execute("""
            SELECT id, times_failed FROM falhas WHERE topic = ? AND what_failed = ?
        """, (topic, what_failed)).fetchone()

        if existing:
            conn.execute("""
                UPDATE falhas SET times_failed = times_failed + 1
                WHERE id = ?
            """, (existing["id"],))
            fid = existing["id"]
        else:
            cur = conn.execute("""
                INSERT INTO falhas (feedback_id, topic, what_failed, why_failed, tags)
                VALUES (?, ?, ?, ?, ?)
            """, (feedback_id, topic, what_failed, why_failed, json.dumps(tags or [])))
            fid = cur.lastrowid
        conn.commit()
        conn.close()
        return fid

    def get_unresolved_failures(self, limit: int = 20) -> list:
        conn = self._conn()
        rows = conn.execute("""
            SELECT * FROM falhas WHERE still_unresolved = TRUE
            ORDER BY times_failed DESC LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def mark_failure_resolved(self, failure_id: int, fix: str):
        conn = self._conn()
        conn.execute("""
            UPDATE falhas SET still_unresolved = FALSE, attempted_fix = ?, fix_worked = TRUE
            WHERE id = ?
        """, (fix, failure_id))
        conn.commit()
        conn.close()

    # ---------- PERGUNTAS GERADAS ----------
    def save_question(self, question: str, context: str = "", category: str = "exploratoria",
                      cycle_id: int = None) -> int:
        conn = self._conn()
        cur = conn.execute("""
            INSERT INTO generated_questions (cycle_id, question, context, category)
            VALUES (?, ?, ?, ?)
        """, (cycle_id, question, context, category))
        qid = cur.lastrowid
        conn.commit()
        conn.close()
        return qid

    def answer_question(self, question_id: int, answer: str, was_relevant: bool = None,
                        relevance_reason: str = ""):
        conn = self._conn()
        conn.execute("""
            UPDATE generated_questions SET answered = TRUE, answer = ?,
            was_relevant = ?, relevance_reason = ?
            WHERE id = ?
        """, (answer, was_relevant, relevance_reason, question_id))
        conn.commit()
        conn.close()

    def get_unanswered_questions(self, limit: int = 10) -> list:
        conn = self._conn()
        rows = conn.execute("""
            SELECT * FROM generated_questions WHERE answered = FALSE
            ORDER BY created_at ASC LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ---------- CONSENSO ----------
    def register_consensus(self, topic: str, agents: list, positions: dict,
                           verdict: str, agreement: float, reasoning: str) -> int:
        conn = self._conn()
        cur = conn.execute("""
            INSERT INTO consensus (topic, agents_involved, positions, final_verdict,
                                   agreement_level, reasoning)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (topic, json.dumps(agents), json.dumps(positions), verdict, agreement, reasoning))
        cid = cur.lastrowid
        conn.commit()
        conn.close()
        return cid

    # ---------- REGRAS ----------
    def create_rule(self, rule_text: str, source: str, confidence: float = 0.5,
                    tags: list = None) -> int:
        conn = self._conn()
        cur = conn.execute("""
            INSERT INTO learned_rules (rule_text, source, confidence, tags)
            VALUES (?, ?, ?, ?)
        """, (rule_text, source, confidence, json.dumps(tags or [])))
        rid = cur.lastrowid
        conn.commit()
        conn.close()
        return rid

    def update_rule_stats(self, rule_id: int, succeeded: bool):
        conn = self._conn()
        if succeeded:
            conn.execute("""
                UPDATE learned_rules SET times_applied = times_applied + 1,
                times_succeeded = times_succeeded + 1,
                confidence = MIN(1.0, confidence + 0.05)
                WHERE id = ?
            """, (rule_id,))
        else:
            conn.execute("""
                UPDATE learned_rules SET times_applied = times_applied + 1,
                times_failed = times_failed + 1,
                confidence = MAX(0.0, confidence - 0.1)
                WHERE id = ?
            """, (rule_id,))
            # Depreca regra se falhar muito
            conn.execute("""
                UPDATE learned_rules SET active = FALSE,
                deprecated_reason = 'Falhou 3+ vezes consecutivas'
                WHERE id = ? AND times_failed >= 3 AND confidence < 0.3
            """, (rule_id,))
        conn.commit()
        conn.close()

    def get_active_rules(self) -> list:
        conn = self._conn()
        rows = conn.execute("""
            SELECT * FROM learned_rules WHERE active = TRUE ORDER BY confidence DESC
        """).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ---------- ESTATÍSTICAS ----------
    def get_stats(self) -> dict:
        conn = self._conn()
        stats = {
            "total_feedbacks": conn.execute("SELECT COUNT(*) FROM feedbacks").fetchone()[0],
            "total_sucessos": conn.execute("SELECT COUNT(*) FROM sucessos").fetchone()[0],
            "total_falhas": conn.execute("SELECT COUNT(*) FROM falhas").fetchone()[0],
            "falhas_nao_resolvidas": conn.execute("SELECT COUNT(*) FROM falhas WHERE still_unresolved = TRUE").fetchone()[0],
            "total_perguntas": conn.execute("SELECT COUNT(*) FROM generated_questions").fetchone()[0],
            "perguntas_respondidas": conn.execute("SELECT COUNT(*) FROM generated_questions WHERE answered = TRUE").fetchone()[0],
            "perguntas_relevantes": conn.execute("SELECT COUNT(*) FROM generated_questions WHERE was_relevant = TRUE").fetchone()[0],
            "total_consensos": conn.execute("SELECT COUNT(*) FROM consensus").fetchone()[0],
            "regras_ativas": conn.execute("SELECT COUNT(*) FROM learned_rules WHERE active = TRUE").fetchone()[0],
            "regras_deprecadas": conn.execute("SELECT COUNT(*) FROM learned_rules WHERE active = FALSE").fetchone()[0],
            "total_ciclos": conn.execute("SELECT COUNT(*) FROM cycles").fetchone()[0],
            "ciclos_completos": conn.execute("SELECT COUNT(*) FROM cycles WHERE status = 'completed'").fetchone()[0],
        }
        conn.close()
        return stats

    # ---------- EXPORTAÇÃO ----------
    def export_all(self, output_dir: Path = EXPORTS_DIR) -> str:
        """Exporta todo o banco em JSON para análise."""
        conn = self._conn()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export = {
            "exported_at": timestamp,
            "stats": self.get_stats(),
            "sucessos": [dict(r) for r in conn.execute("SELECT * FROM sucessos ORDER BY relevance_score DESC").fetchall()],
            "falhas": [dict(r) for r in conn.execute("SELECT * FROM falhas ORDER BY times_failed DESC").fetchall()],
            "regras_ativas": [dict(r) for r in conn.execute("SELECT * FROM learned_rules WHERE active = TRUE").fetchall()],
            "consensos": [dict(r) for r in conn.execute("SELECT * FROM consensus ORDER BY created_at DESC LIMIT 100").fetchall()],
            "top_perguntas_relevantes": [dict(r) for r in conn.execute("SELECT * FROM generated_questions WHERE was_relevant = TRUE ORDER BY created_at DESC LIMIT 100").fetchall()],
        }
        conn.close()

        filepath = output_dir / f"export_{timestamp}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export, f, ensure_ascii=False, indent=2, default=str)
        return str(filepath)


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Motor de Auto-Aprendizado")
    parser.add_argument("--status", action="store_true", help="Mostra status do banco")
    parser.add_argument("--export", action="store_true", help="Exporta dados em JSON")
    parser.add_argument("--init", action="store_true", help="Inicializa o banco de dados")
    args = parser.parse_args()

    db = LearningDB()

    if args.init:
        print("Banco de dados inicializado com sucesso!")
        print(f"  Local: {DB_PATH}")
        return

    if args.status:
        stats = db.get_stats()
        print("\n=== STATUS DO AUTO-APRENDIZADO ===")
        for k, v in stats.items():
            print(f"  {k}: {v}")
        print()
        return

    if args.export:
        path = db.export_all()
        print(f"Dados exportados para: {path}")
        return

    print("Use --init, --status, --export, ou integre via import")


if __name__ == "__main__":
    main()
