"""
Plugin 3.3 — memory_procedural

Camada de memória procedural: "skills" versionadas.
Uma skill é uma função Python pura, com assinatura padronizada,
registrada no banco e armazenada em disco para reuso entre projetos.

Ciclo de vida:
1. developer agent escreve código reutilizável
2. Após 3 execuções bem-sucedidas do mesmo padrão, promove-se a skill
3. Skill ganha versão, métricas e fica disponível via run_skill()
4. Skills não usadas por >30 dias viram status='DEPRECATED'
5. Skills podem ser promovidas a 'STABLE' após uso consistente

Armazenamento de código: arquivos .py em <skills_dir>/<name>_v<n>.py
Banco: tabela skills com metadados e estatísticas de uso.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional


DEFAULT_SKILLS_DIR = Path(__file__).parent.parent.parent / "_auto_learning" / "skills"
DEPRECATE_AFTER_DAYS = 30
MAX_ACTIVE_SKILLS = 20


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS skills (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    name          TEXT NOT NULL,
    version       INTEGER NOT NULL DEFAULT 1,
    description   TEXT NOT NULL,
    code_path     TEXT NOT NULL,
    signature     TEXT,                 -- JSON {inputs, output}
    tags          TEXT,                 -- csv
    status        TEXT NOT NULL DEFAULT 'ACTIVE'
                  CHECK(status IN ('ACTIVE','STABLE','DEPRECATED','KILLED')),
    times_used    INTEGER DEFAULT 0,
    times_success INTEGER DEFAULT 0,
    times_fail    INTEGER DEFAULT 0,
    last_used_at  TIMESTAMP,
    created_by    TEXT,
    UNIQUE(name, version)
);

CREATE INDEX IF NOT EXISTS idx_skills_status    ON skills(status, last_used_at DESC);
CREATE INDEX IF NOT EXISTS idx_skills_name      ON skills(name, version DESC);
"""


class SkillError(Exception):
    """Erro genérico ao carregar ou executar skill."""


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)


# ---------------------------------------------------------------------------
# Template de skill (usado ao criar)
# ---------------------------------------------------------------------------
SKILL_TEMPLATE = '''"""
Skill: {name} v{version}
Description: {description}

Assinatura:
    run(payload: dict) -> dict

payload: dicionário com os parâmetros de entrada
return : dicionário com o resultado (sempre inclua chave "ok": True/False)
"""

def run(payload: dict) -> dict:
{body}
'''


# ---------------------------------------------------------------------------
# Registro e leitura
# ---------------------------------------------------------------------------
def _latest_version(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute(
        "SELECT MAX(version) FROM skills WHERE name=?", (name,)
    ).fetchone()
    return (row[0] or 0) if row else 0


def register_skill(
    conn: sqlite3.Connection,
    name: str,
    description: str,
    code_body: str,
    skills_dir: Path = DEFAULT_SKILLS_DIR,
    signature: Optional[dict] = None,
    tags: Optional[list[str]] = None,
    created_by: Optional[str] = None,
) -> dict:
    """
    Registra uma nova skill. Se o nome já existe, cria a próxima versão.

    code_body: corpo do função run() (já indentado com 4 espaços) ou texto livre.
    Retorna dict com {id, name, version, code_path}.
    """
    # Valida cap de skills ativas
    active_count = conn.execute(
        "SELECT COUNT(*) FROM skills WHERE status IN ('ACTIVE','STABLE')"
    ).fetchone()[0]
    if active_count >= MAX_ACTIVE_SKILLS:
        raise SkillError(
            f"Cap de {MAX_ACTIVE_SKILLS} skills ativas atingido. "
            f"Deprecie alguma antes de registrar nova."
        )

    version = _latest_version(conn, name) + 1
    skills_dir = Path(skills_dir)
    skills_dir.mkdir(parents=True, exist_ok=True)
    code_path = skills_dir / f"{name}_v{version}.py"

    # normaliza indentação do corpo
    body = code_body.strip("\n")
    if not body:
        body = "    return {'ok': False, 'error': 'empty skill'}"
    if not body.startswith("    "):
        body = "\n".join("    " + line if line else line for line in body.splitlines())

    code_path.write_text(
        SKILL_TEMPLATE.format(
            name=name, version=version, description=description, body=body
        ),
        encoding="utf-8",
    )

    cur = conn.execute(
        """
        INSERT INTO skills
          (name, version, description, code_path, signature, tags, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            version,
            description,
            str(code_path),
            json.dumps(signature) if signature else None,
            ",".join(tags) if tags else None,
            created_by,
        ),
    )
    return {
        "id": cur.lastrowid,
        "name": name,
        "version": version,
        "code_path": str(code_path),
    }


def get_skill(
    conn: sqlite3.Connection, name: str, version: Optional[int] = None
) -> Optional[dict]:
    """Retorna metadados da skill pelo nome (última versão ativa se version=None)."""
    if version is None:
        row = conn.execute(
            """
            SELECT * FROM skills
            WHERE name=? AND status IN ('ACTIVE','STABLE')
            ORDER BY version DESC LIMIT 1
            """,
            (name,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM skills WHERE name=? AND version=?", (name, version)
        ).fetchone()
    if row is None:
        return None
    cols = [d[0] for d in conn.execute("SELECT * FROM skills LIMIT 0").description]
    return dict(zip(cols, row))


def list_skills(
    conn: sqlite3.Connection, status: Optional[str] = None
) -> list[dict]:
    if status:
        rows = conn.execute(
            "SELECT * FROM skills WHERE status=? ORDER BY name, version DESC",
            (status,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM skills ORDER BY name, version DESC"
        ).fetchall()
    cols = [d[0] for d in conn.execute("SELECT * FROM skills LIMIT 0").description]
    return [dict(zip(cols, r)) for r in rows]


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------
def _load_module(code_path: Path):
    spec = importlib.util.spec_from_file_location(
        f"skill_{code_path.stem}", code_path
    )
    if spec is None or spec.loader is None:
        raise SkillError(f"Não foi possível carregar {code_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_skill(
    conn: sqlite3.Connection,
    name: str,
    payload: dict,
    version: Optional[int] = None,
) -> dict:
    """Carrega e executa skill, atualizando métricas no banco."""
    meta = get_skill(conn, name, version)
    if meta is None:
        raise SkillError(f"Skill {name} v{version or 'latest'} não encontrada")
    code_path = Path(meta["code_path"])
    if not code_path.exists():
        raise SkillError(f"Arquivo da skill sumiu: {code_path}")

    ok = False
    try:
        mod = _load_module(code_path)
        if not hasattr(mod, "run"):
            raise SkillError(f"Skill {name} v{meta['version']} não expõe run()")
        result = mod.run(payload)
        ok = bool(result.get("ok")) if isinstance(result, dict) else False
        return result if isinstance(result, dict) else {"ok": ok, "value": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        conn.execute(
            """
            UPDATE skills SET
                times_used    = times_used + 1,
                times_success = times_success + ?,
                times_fail    = times_fail + ?,
                last_used_at  = CURRENT_TIMESTAMP,
                updated_at    = CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (1 if ok else 0, 0 if ok else 1, meta["id"]),
        )


# ---------------------------------------------------------------------------
# Manutenção
# ---------------------------------------------------------------------------
def deprecate_skill(
    conn: sqlite3.Connection, name: str, version: int, reason: str = ""
) -> bool:
    cur = conn.execute(
        "UPDATE skills SET status='DEPRECATED', updated_at=CURRENT_TIMESTAMP "
        "WHERE name=? AND version=?",
        (name, version),
    )
    return cur.rowcount > 0


def promote_to_stable(
    conn: sqlite3.Connection, name: str, version: int
) -> bool:
    cur = conn.execute(
        "UPDATE skills SET status='STABLE', updated_at=CURRENT_TIMESTAMP "
        "WHERE name=? AND version=?",
        (name, version),
    )
    return cur.rowcount > 0


def auto_deprecate_stale(
    conn: sqlite3.Connection, days: int = DEPRECATE_AFTER_DAYS
) -> int:
    """Marca como DEPRECATED skills ACTIVE sem uso há mais de N dias."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(
        sep=" ", timespec="seconds"
    )
    cur = conn.execute(
        """
        UPDATE skills
        SET status='DEPRECATED', updated_at=CURRENT_TIMESTAMP
        WHERE status='ACTIVE'
          AND (
            (last_used_at IS NULL AND created_at < ?)
            OR (last_used_at IS NOT NULL AND last_used_at < ?)
          )
        """,
        (cutoff, cutoff),
    )
    return cur.rowcount
