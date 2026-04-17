"""
Plugin 3.6 — functional_emotions

Emoções funcionais como PESOS NUMÉRICOS (não teatro) que modulam a
seleção de agentes. Tudo implementado em tabela separada para não
alterar o schema do core.

- boredom    cresce quando agente é usado repetidamente; força exploração
- curiosity  sobe em áreas de baixa confiança; força perguntas novas
- fear       cresce após falhas; força HIP antes de ações arriscadas
- joy        cresce após sucessos humano-aprovados; reforça rotas boas

Função principal:
    choose_agent(conn, candidates, domain) -> agent_name
    reage a sucesso/falha via update_after_action()
"""

from __future__ import annotations

import sqlite3
from typing import Optional


BOREDOM_INCREMENT = 0.08
BOREDOM_DECAY_REST = 0.5   # quando agente descansa um ciclo, boredom *= 0.5
CURIOSITY_BASE = 0.5
CURIOSITY_GAIN_LOW_CONFIDENCE = 0.1
CURIOSITY_DECAY_EXPLORED = 0.85
FEAR_GAIN_ON_FAIL = 0.15
FEAR_DECAY_ON_SUCCESS = 0.8
JOY_GAIN_ON_APPROVED = 0.1
JOY_DECAY = 0.95

CLAMP_MIN = 0.0
CLAMP_MAX = 1.0


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agent_emotions (
    agent_name TEXT PRIMARY KEY,
    boredom    REAL DEFAULT 0.0,
    curiosity  REAL DEFAULT 0.5,
    fear       REAL DEFAULT 0.0,
    joy        REAL DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_emotions_bored    ON agent_emotions(boredom DESC);
CREATE INDEX IF NOT EXISTS idx_emotions_curious  ON agent_emotions(curiosity DESC);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)


def _clamp(v: float) -> float:
    return max(CLAMP_MIN, min(CLAMP_MAX, v))


def _ensure_row(conn: sqlite3.Connection, agent_name: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO agent_emotions (agent_name) VALUES (?)",
        (agent_name,),
    )


def get_emotions(conn: sqlite3.Connection, agent_name: str) -> dict:
    _ensure_row(conn, agent_name)
    row = conn.execute(
        "SELECT boredom, curiosity, fear, joy FROM agent_emotions "
        "WHERE agent_name=?",
        (agent_name,),
    ).fetchone()
    return {
        "boredom":   row[0],
        "curiosity": row[1],
        "fear":      row[2],
        "joy":       row[3],
    }


def set_emotions(
    conn: sqlite3.Connection,
    agent_name: str,
    *,
    boredom: Optional[float] = None,
    curiosity: Optional[float] = None,
    fear: Optional[float] = None,
    joy: Optional[float] = None,
) -> None:
    _ensure_row(conn, agent_name)
    cur = get_emotions(conn, agent_name)
    if boredom   is not None: cur["boredom"]   = _clamp(boredom)
    if curiosity is not None: cur["curiosity"] = _clamp(curiosity)
    if fear      is not None: cur["fear"]      = _clamp(fear)
    if joy       is not None: cur["joy"]       = _clamp(joy)
    conn.execute(
        """
        UPDATE agent_emotions
        SET boredom=?, curiosity=?, fear=?, joy=?, updated_at=CURRENT_TIMESTAMP
        WHERE agent_name=?
        """,
        (cur["boredom"], cur["curiosity"], cur["fear"], cur["joy"], agent_name),
    )


# ---------------------------------------------------------------------------
# Hooks de atualização
# ---------------------------------------------------------------------------
def on_agent_used(conn: sqlite3.Connection, agent_name: str) -> None:
    """Chamado toda vez que um agente é escolhido para uma tarefa."""
    _ensure_row(conn, agent_name)
    conn.execute(
        """
        UPDATE agent_emotions
        SET boredom = MIN(1.0, boredom + ?),
            updated_at = CURRENT_TIMESTAMP
        WHERE agent_name=?
        """,
        (BOREDOM_INCREMENT, agent_name),
    )


def on_agent_rested(conn: sqlite3.Connection, agent_name: str) -> None:
    """Chamado em ciclos onde o agente NÃO foi usado (descanso)."""
    _ensure_row(conn, agent_name)
    conn.execute(
        """
        UPDATE agent_emotions
        SET boredom = MAX(0.0, boredom * ?),
            updated_at = CURRENT_TIMESTAMP
        WHERE agent_name=?
        """,
        (BOREDOM_DECAY_REST, agent_name),
    )


def on_low_confidence_area(conn: sqlite3.Connection, agent_name: str) -> None:
    """Sobe curiosity quando a área relevante tem confidence baixa."""
    _ensure_row(conn, agent_name)
    conn.execute(
        """
        UPDATE agent_emotions
        SET curiosity = MIN(1.0, curiosity + ?),
            updated_at = CURRENT_TIMESTAMP
        WHERE agent_name=?
        """,
        (CURIOSITY_GAIN_LOW_CONFIDENCE, agent_name),
    )


def on_area_explored(conn: sqlite3.Connection, agent_name: str) -> None:
    """Decai curiosity quando a área foi saturada de exploração."""
    _ensure_row(conn, agent_name)
    conn.execute(
        """
        UPDATE agent_emotions
        SET curiosity = MAX(0.1, curiosity * ?),
            updated_at = CURRENT_TIMESTAMP
        WHERE agent_name=?
        """,
        (CURIOSITY_DECAY_EXPLORED, agent_name),
    )


def update_after_action(
    conn: sqlite3.Connection,
    agent_name: str,
    success: bool,
    human_approved: bool = False,
) -> None:
    """
    Ajusta fear e joy após uma ação terminar.
    - Falha: fear sobe
    - Sucesso: fear decai; joy decai devagar
    - Sucesso + aprovação humana: joy sobe forte
    """
    _ensure_row(conn, agent_name)
    em = get_emotions(conn, agent_name)
    if success:
        em["fear"] = _clamp(em["fear"] * FEAR_DECAY_ON_SUCCESS)
        em["joy"]  = _clamp(em["joy"] * JOY_DECAY)
        if human_approved:
            em["joy"] = _clamp(em["joy"] + JOY_GAIN_ON_APPROVED)
    else:
        em["fear"] = _clamp(em["fear"] + FEAR_GAIN_ON_FAIL)
    set_emotions(
        conn, agent_name,
        boredom=em["boredom"], curiosity=em["curiosity"],
        fear=em["fear"], joy=em["joy"],
    )


# ---------------------------------------------------------------------------
# Árbitro de seleção
# ---------------------------------------------------------------------------
def score_agent_for_task(emotions: dict) -> float:
    """
    Score composto para seleção quando há múltiplos candidatos.
    Maior score = melhor escolha naquele momento.

    Heurística:
    - Curiosity positiva puxa pra cima
    - Joy positiva puxa pra cima (rota validada)
    - Boredom alta puxa pra baixo (precisa descansar)
    - Fear alta puxa pra baixo (pede humano)
    """
    return (
        1.0
        + 0.5 * emotions["curiosity"]
        + 0.5 * emotions["joy"]
        - 1.0 * emotions["boredom"]
        - 0.8 * emotions["fear"]
    )


def choose_agent(
    conn: sqlite3.Connection, candidates: list[str]
) -> Optional[str]:
    """
    Escolhe o melhor agente dentro de uma lista de candidatos possíveis.
    Retorna None se lista vazia.
    """
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    scored = []
    for name in candidates:
        em = get_emotions(conn, name)
        scored.append((score_agent_for_task(em), name))
    scored.sort(reverse=True)
    return scored[0][1]


def needs_human_gate(conn: sqlite3.Connection, agent_name: str) -> bool:
    """True se fear acumulado justifica parar e perguntar ao humano."""
    em = get_emotions(conn, agent_name)
    return em["fear"] >= 0.6
