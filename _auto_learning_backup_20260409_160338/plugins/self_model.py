"""
Plugin 3.4 — self_model

Gera um relatório semanal "como eu estou" lendo as próprias tabelas:
- cycles (saúde dos ciclos)
- action_log (taxa sucesso/falha)
- agents (fitness e agentes obsoletos)
- feedbacks (o que aprendi)
- ekas_usage_log (custo — se plugin ekas_efficiency ativo)
- learned_rules (regras novas)
- area_scores (evolução)

Saída: Markdown <=1 página em _auto_learning/docs/self_model_YYYY-WW.md
Filosofia: direto, numérico, sem floreio. 3 números importantes no topo.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


DEFAULT_REPORT_DIR = Path(__file__).parent.parent.parent / "_auto_learning" / "docs"
OBSOLETE_FITNESS_THRESHOLD = 30.0
OBSOLETE_DAYS_UNUSED = 14


def _week_label(dt: Optional[datetime] = None) -> str:
    dt = dt or datetime.now()
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _count(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    try:
        row = conn.execute(sql, params).fetchone()
        return (row[0] or 0) if row else 0
    except sqlite3.OperationalError:
        return 0


def _collect_cycle_health(conn: sqlite3.Connection, since: str) -> dict:
    total = _count(
        conn, "SELECT COUNT(*) FROM cycles WHERE started_at >= ?", (since,)
    )
    completed = _count(
        conn,
        "SELECT COUNT(*) FROM cycles WHERE started_at >= ? AND status='completed'",
        (since,),
    )
    errored = _count(
        conn,
        "SELECT COUNT(*) FROM cycles WHERE started_at >= ? AND status='error'",
        (since,),
    )
    avg_score_row = conn.execute(
        """
        SELECT AVG(score_global) FROM cycles
        WHERE started_at >= ? AND score_global IS NOT NULL
        """,
        (since,),
    ).fetchone()
    avg_score = avg_score_row[0] if avg_score_row else None
    return {
        "total": total,
        "completed": completed,
        "errored": errored,
        "avg_score": round(avg_score, 1) if avg_score is not None else None,
    }


def _collect_action_stats(conn: sqlite3.Connection, since: str) -> dict:
    if not _table_exists(conn, "action_log"):
        return {"total": 0, "success": 0, "failure": 0, "skipped": 0}
    total = _count(
        conn, "SELECT COUNT(*) FROM action_log WHERE created_at >= ?", (since,)
    )
    success = _count(
        conn,
        "SELECT COUNT(*) FROM action_log WHERE created_at >= ? AND result='success'",
        (since,),
    )
    failure = _count(
        conn,
        "SELECT COUNT(*) FROM action_log WHERE created_at >= ? AND result='failure'",
        (since,),
    )
    skipped = _count(
        conn,
        "SELECT COUNT(*) FROM action_log WHERE created_at >= ? AND result='skipped'",
        (since,),
    )
    return {"total": total, "success": success, "failure": failure, "skipped": skipped}


def _collect_cost(conn: sqlite3.Connection, since: str) -> Optional[dict]:
    if not _table_exists(conn, "ekas_usage_log"):
        return None
    row = conn.execute(
        """
        SELECT
            COALESCE(SUM(input_tokens),0),
            COALESCE(SUM(output_tokens),0),
            COALESCE(SUM(cached_tokens),0),
            COALESCE(SUM(cost_usd),0.0)
        FROM ekas_usage_log WHERE ts >= ?
        """,
        (since,),
    ).fetchone()
    return {
        "tokens_in":  row[0],
        "tokens_out": row[1],
        "cached":     row[2],
        "cost_usd":   round(row[3], 4),
    }


def _collect_new_rules(conn: sqlite3.Connection, since: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT rule_text FROM learned_rules
        WHERE created_at >= ? AND active=1
        ORDER BY created_at DESC LIMIT 5
        """,
        (since,),
    ).fetchall()
    return [r[0] for r in rows]


def _collect_low_confidence(conn: sqlite3.Connection, since: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT question FROM generated_questions
        WHERE created_at >= ?
          AND answered=1
          AND was_relevant=0
        ORDER BY created_at DESC LIMIT 5
        """,
        (since,),
    ).fetchall()
    return [r[0] for r in rows]


def _collect_obsolete_agents(
    conn: sqlite3.Connection,
    fitness_threshold: float = OBSOLETE_FITNESS_THRESHOLD,
    days_unused: int = OBSOLETE_DAYS_UNUSED,
) -> list[dict]:
    cutoff = (datetime.now() - timedelta(days=days_unused)).isoformat(
        sep=" ", timespec="seconds"
    )
    rows = conn.execute(
        """
        SELECT a.name, a.fitness_score,
               (SELECT MAX(recorded_at) FROM agent_performance p
                WHERE p.agent_id=a.id) AS last_used
        FROM agents a
        WHERE a.status='ACTIVE'
          AND (a.fitness_score < ?
               OR (SELECT MAX(recorded_at) FROM agent_performance p
                   WHERE p.agent_id=a.id) < ?
               OR (SELECT MAX(recorded_at) FROM agent_performance p
                   WHERE p.agent_id=a.id) IS NULL)
        ORDER BY a.fitness_score ASC LIMIT 5
        """,
        (fitness_threshold, cutoff),
    ).fetchall()
    return [
        {"name": r[0], "fitness": r[1], "last_used": r[2]} for r in rows
    ]


# ---------------------------------------------------------------------------
# API principal
# ---------------------------------------------------------------------------
def build_self_report(
    conn: sqlite3.Connection,
    days: int = 7,
    now: Optional[datetime] = None,
) -> str:
    """Retorna o conteúdo markdown do relatório."""
    now = now or datetime.now()
    since = (now - timedelta(days=days)).isoformat(sep=" ", timespec="seconds")

    health = _collect_cycle_health(conn, since)
    actions = _collect_action_stats(conn, since)
    cost = _collect_cost(conn, since)
    rules = _collect_new_rules(conn, since)
    chutes = _collect_low_confidence(conn, since)
    obsoletos = _collect_obsolete_agents(conn)

    success_rate = (
        actions["success"] / actions["total"] if actions["total"] else 0
    )

    lines: list[str] = []
    lines.append(f"# Self-model — {_week_label(now)}")
    lines.append("")
    lines.append(f"_Período: últimos {days} dias até {now.strftime('%Y-%m-%d %H:%M')}_")
    lines.append("")
    lines.append("## Três números")
    lines.append(f"- **Ciclos completos:** {health['completed']}/{health['total']}")
    lines.append(f"- **Taxa de sucesso de ações:** {success_rate*100:.0f}% "
                 f"({actions['success']}/{actions['total']})")
    if cost is not None:
        lines.append(f"- **Custo EKAS:** ${cost['cost_usd']} "
                     f"({cost['tokens_in']} in / {cost['tokens_out']} out)")
    else:
        lines.append("- **Custo EKAS:** — (plugin não ativo)")
    lines.append("")

    lines.append("## Saúde dos ciclos")
    lines.append(f"- Completados: {health['completed']}")
    lines.append(f"- Com erro: {health['errored']}")
    if health["avg_score"] is not None:
        lines.append(f"- Score médio: {health['avg_score']}")
    lines.append("")

    lines.append("## O que aprendi")
    if rules:
        for r in rules:
            lines.append(f"- {r}")
    else:
        lines.append("- (nenhuma regra nova)")
    lines.append("")

    lines.append("## Onde estou chutando")
    if chutes:
        for q in chutes:
            lines.append(f"- {q}")
    else:
        lines.append("- (nenhuma pergunta marcada como irrelevante)")
    lines.append("")

    lines.append("## Agentes obsoletos")
    if obsoletos:
        for a in obsoletos:
            last = a["last_used"] or "nunca"
            lines.append(
                f"- `{a['name']}` — fitness={a['fitness']} — último uso: {last}"
            )
    else:
        lines.append("- (nenhum agente obsoleto)")
    lines.append("")

    lines.append("## Recomendações para a semana que vem")
    recs = []
    if actions["total"] > 0 and success_rate < 0.6:
        recs.append("Taxa de sucesso baixa — investigar ações com result='failure' antes de abrir novas frentes")
    if cost and cost["cost_usd"] > 0.8 * 7 * 0.50:  # 80% do cap semanal default
        recs.append("Custo EKAS perto do teto — revisar cache hit e Batch API")
    if obsoletos:
        recs.append(f"Aposentar {len(obsoletos)} agente(s) obsoleto(s)")
    if not rules:
        recs.append("Nenhuma regra nova — considerar se o sistema está estagnado")
    if not recs:
        recs.append("Tudo verde — continuar no mesmo ritmo")
    for r in recs:
        lines.append(f"- {r}")
    lines.append("")

    return "\n".join(lines)


def generate_self_report(
    conn: sqlite3.Connection,
    days: int = 7,
    report_dir: Path = DEFAULT_REPORT_DIR,
    now: Optional[datetime] = None,
) -> Path:
    """Gera e salva o relatório. Retorna o path."""
    content = build_self_report(conn, days=days, now=now)
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    label = _week_label(now)
    path = report_dir / f"self_model_{label}.md"
    path.write_text(content, encoding="utf-8")
    return path
