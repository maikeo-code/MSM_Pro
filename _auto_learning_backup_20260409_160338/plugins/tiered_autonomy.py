"""
Plugin 3.2 — tiered_autonomy

Formaliza níveis de autonomia L0-L4, circuit breakers e audit log
com hash encadeado estilo blockchain-lite.

Níveis:
- L0  Leitura pura, análises, relatórios                  [automático]
- L1  Escrita em tabelas internas do SWARM                [automático]
- L2  Envio interno, commit em branch feature/*           [automático com audit]
- L3  Editar código do projeto alvo (com backup)          [APROVAÇÃO humana via HIP]
- L4  Responder cliente, push main, deploy, mexer preço   [APROVAÇÃO humana obrigatória]

Circuit breakers:
- 3 erros seguidos do MESMO agente => agente vai para status DORMANT por 1h
- Mesma (agent_name, action_type, target) 5x na última hora => KILL (status=KILLED)

Audit hash:
- Cada evento audit_log tem prev_hash e hash SHA256 do próprio conteúdo + prev_hash
- Função verify_audit_chain() valida a cadeia inteira
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Optional


# ---------------------------------------------------------------------------
# Tier defaults — mapeia action_type canônicos em nível L0-L4
# ---------------------------------------------------------------------------
DEFAULT_TIER_MAP = {
    # L0 — leitura pura
    "read_file":        ("L0", False),
    "get_context":      ("L0", False),
    "query_db":         ("L0", False),
    "get_patterns":     ("L0", False),
    "get_feedbacks":    ("L0", False),
    "run_analysis":     ("L0", False),
    # L1 — escrita interna SWARM
    "register_feedback":("L1", False),
    "save_episode":     ("L1", False),
    "save_knowledge":   ("L1", False),
    "save_checkpoint":  ("L1", False),
    "log_action":       ("L1", False),
    "create_rule":      ("L1", False),
    "open_debate":      ("L1", False),
    "save_pattern":     ("L1", False),
    # L2 — commit feature branch / audit
    "git_commit_feature": ("L2", False),
    "run_test":         ("L2", False),
    "create_agent":     ("L2", False),
    # L3 — edita código alvo (gate humano)
    "edit_file":        ("L3", True),
    "create_file":      ("L3", True),
    "delete_file":      ("L3", True),
    "refactor":         ("L3", True),
    "modify_schema":    ("L3", True),
    # L4 — fora do repo ou irreversível
    "git_push_main":    ("L4", True),
    "deploy":           ("L4", True),
    "send_customer":    ("L4", True),
    "change_price":     ("L4", True),
    "delete_branch":    ("L4", True),
}


class ActionBlocked(Exception):
    """Ação foi barrada por tier, circuit breaker ou audit."""


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS action_tiers (
    action_type     TEXT PRIMARY KEY,
    tier            TEXT NOT NULL CHECK(tier IN ('L0','L1','L2','L3','L4')),
    requires_human  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS agent_breakers (
    agent_name       TEXT PRIMARY KEY,
    consecutive_errs INTEGER DEFAULT 0,
    dormant_until    TIMESTAMP,
    killed           INTEGER DEFAULT 0,
    killed_reason    TEXT,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    agent_name  TEXT,
    action_type TEXT NOT NULL,
    target      TEXT,
    tier        TEXT,
    outcome     TEXT CHECK(outcome IN ('allowed','blocked','pending_human','executed','failed')),
    payload     TEXT,
    prev_hash   TEXT,
    hash        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_log_agent ON audit_log(agent_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action_type, created_at DESC);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    # Semeia mapa default (sem sobrescrever customizações do usuário)
    for action_type, (tier, requires_human) in DEFAULT_TIER_MAP.items():
        conn.execute(
            """
            INSERT OR IGNORE INTO action_tiers (action_type, tier, requires_human)
            VALUES (?, ?, ?)
            """,
            (action_type, tier, 1 if requires_human else 0),
        )


# ---------------------------------------------------------------------------
# Consulta de tier
# ---------------------------------------------------------------------------
def get_tier(conn: sqlite3.Connection, action_type: str) -> tuple[str, bool]:
    row = conn.execute(
        "SELECT tier, requires_human FROM action_tiers WHERE action_type = ?",
        (action_type,),
    ).fetchone()
    if row is None:
        # Default seguro: ação desconhecida é L3 (exige humano)
        return ("L3", True)
    return (row[0], bool(row[1]))


def set_tier(
    conn: sqlite3.Connection,
    action_type: str,
    tier: str,
    requires_human: bool,
) -> None:
    assert tier in ("L0", "L1", "L2", "L3", "L4")
    conn.execute(
        """
        INSERT INTO action_tiers (action_type, tier, requires_human)
        VALUES (?, ?, ?)
        ON CONFLICT(action_type) DO UPDATE SET
            tier=excluded.tier,
            requires_human=excluded.requires_human
        """,
        (action_type, tier, 1 if requires_human else 0),
    )


# ---------------------------------------------------------------------------
# Circuit breakers
# ---------------------------------------------------------------------------
DORMANT_MINUTES = 60
KILL_WINDOW_MIN = 60
KILL_THRESHOLD = 5
ERR_THRESHOLD = 3


def _parse_ts(s: str) -> datetime:
    # SQLite TIMESTAMP default é 'YYYY-MM-DD HH:MM:SS'
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def record_outcome(
    conn: sqlite3.Connection,
    agent_name: str,
    success: bool,
) -> None:
    """Alimenta o circuit breaker de erro consecutivo."""
    row = conn.execute(
        "SELECT consecutive_errs, killed FROM agent_breakers WHERE agent_name=?",
        (agent_name,),
    ).fetchone()
    cur = row[0] if row else 0
    if success:
        cur = 0
    else:
        cur += 1

    dormant_until = None
    if cur >= ERR_THRESHOLD:
        dormant_until = (datetime.now() + timedelta(minutes=DORMANT_MINUTES)).isoformat(
            sep=" ", timespec="seconds"
        )

    if row is None:
        conn.execute(
            """
            INSERT INTO agent_breakers (agent_name, consecutive_errs, dormant_until)
            VALUES (?, ?, ?)
            """,
            (agent_name, cur, dormant_until),
        )
    else:
        conn.execute(
            """
            UPDATE agent_breakers
            SET consecutive_errs=?, dormant_until=?, updated_at=CURRENT_TIMESTAMP
            WHERE agent_name=?
            """,
            (cur, dormant_until, agent_name),
        )


def is_dormant(conn: sqlite3.Connection, agent_name: str) -> bool:
    row = conn.execute(
        "SELECT dormant_until, killed FROM agent_breakers WHERE agent_name=?",
        (agent_name,),
    ).fetchone()
    if not row:
        return False
    if row[1]:
        return True
    if row[0] is None:
        return False
    return _parse_ts(row[0]) > datetime.now()


def _repeat_count_last_hour(
    conn: sqlite3.Connection,
    agent_name: str,
    action_type: str,
    target: Optional[str],
) -> int:
    cutoff = (datetime.now() - timedelta(minutes=KILL_WINDOW_MIN)).isoformat(
        sep=" ", timespec="seconds"
    )
    return conn.execute(
        """
        SELECT COUNT(*) FROM audit_log
        WHERE agent_name=? AND action_type=? AND COALESCE(target,'')=COALESCE(?, '')
          AND created_at >= ?
        """,
        (agent_name, action_type, target, cutoff),
    ).fetchone()[0]


def _kill_agent(conn: sqlite3.Connection, agent_name: str, reason: str) -> None:
    row = conn.execute(
        "SELECT agent_name FROM agent_breakers WHERE agent_name=?", (agent_name,)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE agent_breakers SET killed=1, killed_reason=? WHERE agent_name=?",
            (reason, agent_name),
        )
    else:
        conn.execute(
            "INSERT INTO agent_breakers (agent_name, killed, killed_reason) VALUES (?, 1, ?)",
            (agent_name, reason),
        )


# ---------------------------------------------------------------------------
# Audit hash encadeado
# ---------------------------------------------------------------------------
def _last_hash(conn: sqlite3.Connection) -> Optional[str]:
    row = conn.execute(
        "SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else None


def _compute_hash(
    prev_hash: Optional[str],
    agent_name: str,
    action_type: str,
    target: Optional[str],
    tier: str,
    outcome: str,
    payload: Optional[str],
) -> str:
    raw = json.dumps(
        {
            "prev": prev_hash or "",
            "agent": agent_name,
            "action": action_type,
            "target": target,
            "tier": tier,
            "outcome": outcome,
            "payload": payload,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def audit(
    conn: sqlite3.Connection,
    agent_name: str,
    action_type: str,
    target: Optional[str],
    tier: str,
    outcome: str,
    payload: Optional[dict] = None,
) -> str:
    """Grava uma entrada no audit_log com hash encadeado. Retorna o hash."""
    payload_s = json.dumps(payload, ensure_ascii=False) if payload else None
    prev = _last_hash(conn)
    h = _compute_hash(prev, agent_name, action_type, target, tier, outcome, payload_s)
    conn.execute(
        """
        INSERT INTO audit_log
          (agent_name, action_type, target, tier, outcome, payload, prev_hash, hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (agent_name, action_type, target, tier, outcome, payload_s, prev, h),
    )
    return h


def verify_audit_chain(conn: sqlite3.Connection) -> tuple[bool, Optional[int]]:
    """
    Revalida toda a cadeia de audit_log. Retorna (ok, bad_id).
    bad_id aponta o primeiro registro corrompido (None se tudo íntegro).
    """
    rows = conn.execute(
        """
        SELECT id, agent_name, action_type, target, tier, outcome, payload,
               prev_hash, hash
        FROM audit_log ORDER BY id ASC
        """
    ).fetchall()
    expected_prev = None
    for r in rows:
        rid, agent, atype, target, tier, outcome, payload, prev, h = r
        if prev != expected_prev:
            return (False, rid)
        want = _compute_hash(prev, agent, atype, target, tier, outcome, payload)
        if want != h:
            return (False, rid)
        expected_prev = h
    return (True, None)


# ---------------------------------------------------------------------------
# API principal — guard()
# ---------------------------------------------------------------------------
def guard(
    conn: sqlite3.Connection,
    agent_name: str,
    action_type: str,
    target: Optional[str] = None,
    payload: Optional[dict] = None,
) -> str:
    """
    Avalia se a ação pode prosseguir. Retorna outcome:
      'allowed'        — pode executar automaticamente
      'pending_human'  — gravada como pendente, deve-se abrir HIP
      'blocked'        — breaker/kill/dormant; não executar

    Levanta ActionBlocked quando é o caso — chamador pode capturar e tratar.
    Sempre grava no audit_log, qualquer que seja o desfecho.
    """
    # 1. Agente morto ou dormente?
    row = conn.execute(
        "SELECT killed, dormant_until FROM agent_breakers WHERE agent_name=?",
        (agent_name,),
    ).fetchone()
    if row:
        if row[0]:
            audit(conn, agent_name, action_type, target, "?", "blocked",
                  {"reason": "agent_killed", **(payload or {})})
            raise ActionBlocked(f"Agent {agent_name} está KILLED")
        if row[1] and _parse_ts(row[1]) > datetime.now():
            audit(conn, agent_name, action_type, target, "?", "blocked",
                  {"reason": "agent_dormant", **(payload or {})})
            raise ActionBlocked(f"Agent {agent_name} está DORMANT até {row[1]}")

    # 2. Repetição excessiva (kill switch)
    if _repeat_count_last_hour(conn, agent_name, action_type, target) >= KILL_THRESHOLD:
        _kill_agent(conn, agent_name, f"repetiu {action_type} {KILL_THRESHOLD}x em {KILL_WINDOW_MIN}min")
        audit(conn, agent_name, action_type, target, "?", "blocked",
              {"reason": "repetition_killswitch"})
        raise ActionBlocked(
            f"Agent {agent_name} foi KILLED: repetiu {action_type} demais"
        )

    # 3. Tier lookup
    tier, needs_human = get_tier(conn, action_type)

    if needs_human:
        audit(conn, agent_name, action_type, target, tier, "pending_human", payload)
        return "pending_human"

    audit(conn, agent_name, action_type, target, tier, "allowed", payload)
    return "allowed"
