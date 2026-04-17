"""
Plugin: session_diff

Gera um resumo curto de "o que mudou desde o último checkpoint" para
o protocolo de despertar. Evita reler tudo e economiza contexto.

Uso:
    from plugins.session_diff import what_changed
    diff = what_changed(conn)
    # → string markdown com 5-10 linhas
"""

from __future__ import annotations

import sqlite3
from typing import Optional


def what_changed(conn: sqlite3.Connection) -> str:
    """
    Retorna um resumo markdown curto do que aconteceu desde o último
    checkpoint retomado. Se não há checkpoint, retorna resumo geral.
    """
    # Encontra o último checkpoint retomado
    last_cp = conn.execute(
        """SELECT id, cycle_id, phase, created_at
           FROM session_checkpoints
           ORDER BY id DESC LIMIT 1"""
    ).fetchone()

    if last_cp:
        since = last_cp[3]  # created_at
        cp_cycle = last_cp[1]
        header = f"Desde o checkpoint (ciclo {cp_cycle}, fase {last_cp[2]}, {since}):"
    else:
        since = "1970-01-01"
        header = "Resumo geral (sem checkpoint anterior):"

    lines = [f"## {header}", ""]

    # Ciclos completados
    n_cycles = conn.execute(
        "SELECT COUNT(*) FROM cycles WHERE status='completed' AND ended_at > ?",
        (since,),
    ).fetchone()[0]
    lines.append(f"- **Ciclos completados:** {n_cycles}")

    # Feedbacks novos
    n_feedbacks = conn.execute(
        "SELECT COUNT(*) FROM feedbacks WHERE created_at > ?", (since,),
    ).fetchone()[0]
    lines.append(f"- **Feedbacks novos:** {n_feedbacks}")

    # Regras novas
    rules = conn.execute(
        "SELECT rule_text FROM learned_rules WHERE created_at > ? AND active=1",
        (since,),
    ).fetchall()
    if rules:
        lines.append(f"- **Regras novas:** {len(rules)}")
        for r in rules[:3]:
            lines.append(f"  - {r[0][:80]}")
        if len(rules) > 3:
            lines.append(f"  - (+{len(rules)-3} mais)")
    else:
        lines.append("- **Regras novas:** 0")

    # Falhas não resolvidas
    n_unresolved = conn.execute(
        "SELECT COUNT(*) FROM falhas WHERE still_unresolved=1 AND created_at > ?",
        (since,),
    ).fetchone()[0]
    if n_unresolved > 0:
        lines.append(f"- **Falhas novas não resolvidas:** {n_unresolved}")

    # Code changes
    try:
        n_changes = conn.execute(
            "SELECT COUNT(*) FROM code_changes WHERE created_at > ?", (since,),
        ).fetchone()[0]
        n_rolled = conn.execute(
            "SELECT COUNT(*) FROM code_changes WHERE created_at > ? AND rolled_back=1",
            (since,),
        ).fetchone()[0]
        if n_changes > 0:
            lines.append(f"- **Edições de código:** {n_changes} ({n_rolled} revertidas)")
    except sqlite3.OperationalError:
        pass

    # Perguntas HIP pendentes
    n_hip = conn.execute(
        "SELECT COUNT(*) FROM human_questions WHERE status='PENDING'",
    ).fetchone()[0]
    if n_hip > 0:
        lines.append(f"- **Perguntas HIP pendentes:** {n_hip}")

    # Agentes fitness changed
    try:
        perf = conn.execute(
            """SELECT agent_name, SUM(score_delta)
               FROM agent_performance ap
               JOIN agents a ON ap.agent_id = a.id
               WHERE ap.recorded_at > ?
               GROUP BY agent_name
               HAVING ABS(SUM(score_delta)) > 5
               ORDER BY SUM(score_delta) DESC LIMIT 3""",
            (since,),
        ).fetchall()
        if perf:
            lines.append("- **Mudanças de fitness relevantes:**")
            for name, delta in perf:
                sign = "+" if delta > 0 else ""
                lines.append(f"  - `{name}` {sign}{delta:.1f}")
    except sqlite3.OperationalError:
        pass

    lines.append("")
    return "\n".join(lines)
