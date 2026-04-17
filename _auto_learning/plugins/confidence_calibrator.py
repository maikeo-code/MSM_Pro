"""
Plugin: confidence_calibrator

Rastreia se previsões de alta confiança se confirmaram.
Ensina o sistema a confiar em si mesmo (ou não).

Conceito:
- Cada regra/padrão tem um confidence score.
- Quando uma regra é aplicada e o resultado é observado (sucesso/falha),
  registramos o par (predicted_confidence, actual_outcome).
- Periodicamente calculamos a calibração: se regras com confidence 0.9
  acertam só 60% das vezes, o sistema está overconfident.

Métricas:
- calibration_error: |predicted_confidence - actual_success_rate| por faixa
- brier_score: média de (predicted - actual)^2 — quanto menor, melhor

Saída: relatório markdown + ajuste automático de confidence.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS calibration_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_type     TEXT NOT NULL CHECK(source_type IN ('rule','pattern','knowledge')),
    source_id       INTEGER NOT NULL,
    predicted_conf  REAL NOT NULL,
    actual_outcome  INTEGER NOT NULL CHECK(actual_outcome IN (0, 1)),
    context         TEXT
);
CREATE INDEX IF NOT EXISTS idx_calib_source ON calibration_log(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_calib_conf   ON calibration_log(predicted_conf);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)


def record_prediction(
    conn: sqlite3.Connection,
    source_type: str,
    source_id: int,
    predicted_conf: float,
    actual_outcome: bool,
    context: Optional[str] = None,
) -> None:
    """Registra uma previsão e seu resultado real."""
    conn.execute(
        """INSERT INTO calibration_log
           (source_type, source_id, predicted_conf, actual_outcome, context)
           VALUES (?, ?, ?, ?, ?)""",
        (source_type, source_id, predicted_conf, 1 if actual_outcome else 0, context),
    )


def _bucket(conf: float) -> str:
    """Agrupa confidence em faixas de 0.1."""
    bucket = int(conf * 10) / 10
    return f"{bucket:.1f}-{bucket + 0.1:.1f}"


def compute_calibration(conn: sqlite3.Connection) -> dict:
    """
    Calcula calibração por faixa de confidence.
    Retorna {buckets: {faixa: {predicted, actual, count, error}}, brier_score}.
    """
    rows = conn.execute(
        "SELECT predicted_conf, actual_outcome FROM calibration_log"
    ).fetchall()

    if not rows:
        return {"buckets": {}, "brier_score": None, "total_predictions": 0}

    from collections import defaultdict
    buckets: dict[str, dict] = defaultdict(lambda: {"sum_pred": 0, "sum_actual": 0, "count": 0})

    brier_sum = 0.0
    for pred, actual in rows:
        b = _bucket(pred)
        buckets[b]["sum_pred"] += pred
        buckets[b]["sum_actual"] += actual
        buckets[b]["count"] += 1
        brier_sum += (pred - actual) ** 2

    result = {}
    for b, data in sorted(buckets.items()):
        avg_pred = data["sum_pred"] / data["count"]
        avg_actual = data["sum_actual"] / data["count"]
        result[b] = {
            "predicted": round(avg_pred, 3),
            "actual": round(avg_actual, 3),
            "count": data["count"],
            "error": round(abs(avg_pred - avg_actual), 3),
        }

    return {
        "buckets": result,
        "brier_score": round(brier_sum / len(rows), 4),
        "total_predictions": len(rows),
    }


def generate_calibration_report(conn: sqlite3.Connection) -> str:
    """Gera relatório markdown da calibração."""
    cal = compute_calibration(conn)
    lines = [
        "# Relatório de Calibração",
        f"_Gerado em {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        f"**Total de previsões registradas:** {cal['total_predictions']}",
    ]
    if cal["brier_score"] is not None:
        lines.append(f"**Brier Score:** {cal['brier_score']} (0 = perfeito, 1 = péssimo)")
        if cal["brier_score"] < 0.1:
            lines.append("_Calibração excelente_")
        elif cal["brier_score"] < 0.25:
            lines.append("_Calibração boa_")
        else:
            lines.append("_Calibração ruim — sistema está overconfident ou underconfident_")
    lines.append("")

    if cal["buckets"]:
        lines.append("## Por faixa de confiança")
        lines.append("")
        lines.append("| Faixa | Previsto | Real | N | Erro |")
        lines.append("|---|---|---|---|---|")
        for faixa, data in cal["buckets"].items():
            emoji = "✅" if data["error"] < 0.15 else "⚠️" if data["error"] < 0.3 else "❌"
            lines.append(
                f"| {faixa} | {data['predicted']:.0%} | {data['actual']:.0%} | "
                f"{data['count']} | {data['error']:.0%} {emoji} |"
            )
    else:
        lines.append("_Nenhuma previsão registrada ainda._")

    lines.append("")
    return "\n".join(lines)


def auto_adjust_confidence(conn: sqlite3.Connection, min_samples: int = 5) -> int:
    """
    Ajusta automaticamente o confidence de regras/padrões baseado na
    calibração real. Só ajusta se tiver pelo menos min_samples observações.
    Retorna número de itens ajustados.
    """
    adjusted = 0

    for source_type, table, id_col in [
        ("rule", "learned_rules", "id"),
        ("pattern", "memory_patterns", "id"),
    ]:
        rows = conn.execute(
            f"""
            SELECT source_id, AVG(actual_outcome), COUNT(*)
            FROM calibration_log
            WHERE source_type = ?
            GROUP BY source_id
            HAVING COUNT(*) >= ?
            """,
            (source_type, min_samples),
        ).fetchall()

        for source_id, actual_rate, count in rows:
            # Ajuste: move confidence 20% na direção do resultado real
            current = conn.execute(
                f"SELECT confidence FROM {table} WHERE {id_col}=?", (source_id,)
            ).fetchone()
            if current is None:
                continue
            old_conf = current[0]
            new_conf = old_conf + 0.2 * (actual_rate - old_conf)
            new_conf = max(0.1, min(0.99, new_conf))
            if abs(new_conf - old_conf) > 0.01:
                conn.execute(
                    f"UPDATE {table} SET confidence=? WHERE {id_col}=?",
                    (round(new_conf, 3), source_id),
                )
                adjusted += 1

    return adjusted
