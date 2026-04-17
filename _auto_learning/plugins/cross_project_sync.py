"""
Plugin: cross_project_sync

Exporta regras/padrões/skills com alta confiança de um projeto e
importa em outro. Permite que 5 projetos aprendam juntos em vez
de em silo.

Exporta: learned_rules (confidence > threshold), memory_patterns (confidence > threshold),
         skills (status STABLE).
Formato: JSON em _auto_learning/exports/cross_sync_YYYYMMDD.json

Importa: lê o JSON, verifica duplicata por rule_text/description, insere ou reforça.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


DEFAULT_EXPORTS_DIR = Path(__file__).parent.parent / "exports"
CONFIDENCE_THRESHOLD = 0.8


def export_knowledge(
    conn: sqlite3.Connection,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
    exports_dir: Path = DEFAULT_EXPORTS_DIR,
) -> dict:
    """
    Exporta regras, padrões e skills de alta confiança para JSON.
    Retorna {path, rules, patterns, skills, total}.
    """
    exports_dir = Path(exports_dir)
    exports_dir.mkdir(parents=True, exist_ok=True)

    # Regras
    rules = []
    for r in conn.execute(
        "SELECT rule_text, source, confidence, tags FROM learned_rules "
        "WHERE active=1 AND confidence >= ?",
        (confidence_threshold,),
    ).fetchall():
        rules.append({
            "rule_text": r[0], "source": r[1],
            "confidence": r[2], "tags": r[3],
        })

    # Padrões
    patterns = []
    for r in conn.execute(
        "SELECT pattern_type, description, occurrences, confidence, standard_fix "
        "FROM memory_patterns WHERE active=1 AND confidence >= ?",
        (confidence_threshold,),
    ).fetchall():
        patterns.append({
            "pattern_type": r[0], "description": r[1],
            "occurrences": r[2], "confidence": r[3], "standard_fix": r[4],
        })

    # Skills estáveis
    skills = []
    has_skills = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='skills'"
    ).fetchone()
    if has_skills:
        for r in conn.execute(
            "SELECT name, version, description, tags FROM skills WHERE status='STABLE'"
        ).fetchall():
            skills.append({
                "name": r[0], "version": r[1],
                "description": r[2], "tags": r[3],
            })

    # Conhecimento semântico universal
    knowledge = []
    for r in conn.execute(
        "SELECT category, key, value, confidence FROM memory_semantic "
        "WHERE confidence >= ?",
        (confidence_threshold,),
    ).fetchall():
        knowledge.append({
            "category": r[0], "key": r[1],
            "value": r[2], "confidence": r[3],
        })

    payload = {
        "exported_at": datetime.now().isoformat(),
        "confidence_threshold": confidence_threshold,
        "rules": rules,
        "patterns": patterns,
        "skills": skills,
        "knowledge": knowledge,
    }

    path = exports_dir / f"cross_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "path": str(path),
        "rules": len(rules),
        "patterns": len(patterns),
        "skills": len(skills),
        "knowledge": len(knowledge),
        "total": len(rules) + len(patterns) + len(skills) + len(knowledge),
    }


def _rule_exists(conn: sqlite3.Connection, rule_text: str) -> Optional[int]:
    row = conn.execute(
        "SELECT id FROM learned_rules WHERE rule_text = ?", (rule_text,)
    ).fetchone()
    return row[0] if row else None


def _pattern_exists(conn: sqlite3.Connection, description: str) -> Optional[int]:
    row = conn.execute(
        "SELECT id FROM memory_patterns WHERE description = ?", (description,)
    ).fetchone()
    return row[0] if row else None


def _knowledge_exists(conn: sqlite3.Connection, category: str, key: str) -> Optional[int]:
    row = conn.execute(
        "SELECT id FROM memory_semantic WHERE category=? AND key=?", (category, key)
    ).fetchone()
    return row[0] if row else None


def import_knowledge(
    conn: sqlite3.Connection,
    json_path: str | Path,
) -> dict:
    """
    Importa regras/padrões/conhecimento de outro projeto.
    Duplicatas são reforçadas (confidence sobe), não duplicadas.
    Retorna {imported, skipped, reinforced}.
    """
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))

    imported = 0
    skipped = 0
    reinforced = 0

    # Regras
    for rule in data.get("rules", []):
        existing = _rule_exists(conn, rule["rule_text"])
        if existing:
            conn.execute(
                "UPDATE learned_rules SET confidence = MIN(confidence + 0.05, 0.99) WHERE id=?",
                (existing,),
            )
            reinforced += 1
        else:
            conn.execute(
                "INSERT INTO learned_rules (rule_text, source, confidence, tags) VALUES (?, ?, ?, ?)",
                (
                    rule["rule_text"],
                    f"cross_project:{rule.get('source', 'unknown')}",
                    min(rule.get("confidence", 0.5), 0.7),  # cap na importação
                    rule.get("tags"),
                ),
            )
            imported += 1

    # Padrões
    for pat in data.get("patterns", []):
        existing = _pattern_exists(conn, pat["description"])
        if existing:
            conn.execute(
                "UPDATE memory_patterns SET confidence = MIN(confidence + 0.05, 0.99), "
                "occurrences = occurrences + 1 WHERE id=?",
                (existing,),
            )
            reinforced += 1
        else:
            conn.execute(
                """INSERT INTO memory_patterns
                   (pattern_type, description, occurrences, confidence, standard_fix)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    pat["pattern_type"], pat["description"],
                    pat.get("occurrences", 1),
                    min(pat.get("confidence", 0.5), 0.7),
                    pat.get("standard_fix"),
                ),
            )
            imported += 1

    # Conhecimento semântico
    for k in data.get("knowledge", []):
        existing = _knowledge_exists(conn, k["category"], k["key"])
        if existing:
            conn.execute(
                "UPDATE memory_semantic SET confidence = MIN(confidence + 0.05, 0.99) WHERE id=?",
                (existing,),
            )
            reinforced += 1
        else:
            conn.execute(
                "INSERT OR IGNORE INTO memory_semantic (category, key, value, confidence) "
                "VALUES (?, ?, ?, ?)",
                (k["category"], k["key"], k["value"], min(k.get("confidence", 0.5), 0.7)),
            )
            imported += 1

    return {"imported": imported, "skipped": skipped, "reinforced": reinforced}
