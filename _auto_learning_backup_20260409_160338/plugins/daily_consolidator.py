"""
Plugin 3.5 — daily_consolidator

Consolidação diária heurística (ZERO custo — sem LLM por default).

Algoritmo:
1. Varre memory_episodic do dia corrente
2. Clusteriza por (agent_name, action) e similaridade Jaccard do campo details
3. Para cada cluster com >=3 eventos, sumariza em memory_semantic
4. Dedup: se já existe semantic com key similar (>0.92), apenas reforça confidence
5. Ebbinghaus decay: memórias semânticas não referenciadas há >30 dias perdem
   10% de confidence a cada rodada (até mínimo 0.1)

Não há LLM aqui. Se quiser ativar LLM no futuro, ligue CONSOLIDATOR_USE_LLM=true
e implemente a chamada em summarize_cluster_llm(), mas isso fica para depois.
"""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, date
from typing import Iterable


DEDUP_THRESHOLD = 0.92
MIN_CLUSTER_SIZE = 3
DECAY_DAYS = 30
DECAY_FACTOR = 0.9
MIN_CONFIDENCE = 0.1


_TOKEN_RE = re.compile(r"[a-zA-ZÀ-ÿ0-9_]+")


def _tokenize(text: str) -> set[str]:
    if not text:
        return set()
    return {t.lower() for t in _TOKEN_RE.findall(text) if len(t) > 2}


def jaccard(a: str, b: str) -> float:
    sa, sb = _tokenize(a), _tokenize(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    inter = sa & sb
    union = sa | sb
    return len(inter) / len(union)


# ---------------------------------------------------------------------------
# Clustering de episódios
# ---------------------------------------------------------------------------
def cluster_episodes(
    episodes: list[dict], similarity_threshold: float = 0.5
) -> list[list[dict]]:
    """
    Agrupa episódios por (agent_name, action) e depois por similaridade
    Jaccard do campo details. Retorna lista de clusters.
    """
    by_key: dict[tuple, list[dict]] = defaultdict(list)
    for ep in episodes:
        by_key[(ep.get("agent_name"), ep.get("action"))].append(ep)

    clusters: list[list[dict]] = []
    for _key, group in by_key.items():
        # Dentro do grupo, clustering aglomerativo simples (single-linkage)
        assigned: list[list[dict]] = []
        for ep in group:
            placed = False
            for cluster in assigned:
                rep = cluster[0]
                sim = jaccard(
                    ep.get("details", "") or "", rep.get("details", "") or ""
                )
                if sim >= similarity_threshold:
                    cluster.append(ep)
                    placed = True
                    break
            if not placed:
                assigned.append([ep])
        clusters.extend(assigned)
    return clusters


def summarize_cluster(cluster: list[dict]) -> dict:
    """
    Sumariza um cluster em um dict compatível com memory_semantic.
    Heurística: categoria = agent_name, key = action, value = descrição agregada.
    """
    agent = cluster[0].get("agent_name") or "unknown"
    action = cluster[0].get("action") or "unknown"
    targets = sorted(
        {c.get("target") for c in cluster if c.get("target")}
    )
    successes = sum(1 for c in cluster if c.get("result") == "success")
    total = len(cluster)
    confidence = min(0.5 + 0.1 * total, 0.95)

    value = (
        f"{agent}/{action}: {total} ocorrências no dia, "
        f"{successes} sucesso(s). "
    )
    if targets:
        value += f"Alvos: {', '.join(targets[:5])}"
        if len(targets) > 5:
            value += f" (+{len(targets)-5})"

    return {
        "category": f"consolidated_{agent}",
        "key": action,
        "value": value.strip(),
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Dedup contra memory_semantic existente
# ---------------------------------------------------------------------------
def _find_similar_semantic(
    conn: sqlite3.Connection,
    category: str,
    key: str,
    value: str,
    threshold: float = DEDUP_THRESHOLD,
) -> dict | None:
    row = conn.execute(
        "SELECT id, value, confidence FROM memory_semantic "
        "WHERE category=? AND key=?",
        (category, key),
    ).fetchone()
    if row is None:
        return None
    sim = jaccard(row[1] or "", value)
    if sim >= threshold:
        return {"id": row[0], "value": row[1], "confidence": row[2], "sim": sim}
    return None


def _upsert_semantic(
    conn: sqlite3.Connection,
    category: str,
    key: str,
    value: str,
    confidence: float,
) -> str:
    """Retorna 'created' | 'reinforced' indicando o tipo de operação."""
    existing = _find_similar_semantic(conn, category, key, value)
    if existing:
        # Reforço: confidence sobe, mas limitada
        new_conf = min(existing["confidence"] + 0.05, 0.99)
        conn.execute(
            "UPDATE memory_semantic SET confidence=?, updated_at=CURRENT_TIMESTAMP "
            "WHERE id=?",
            (new_conf, existing["id"]),
        )
        return "reinforced"
    # Insert novo
    conn.execute(
        """
        INSERT INTO memory_semantic (category, key, value, confidence)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(category, key) DO UPDATE SET
            value=excluded.value,
            confidence=MAX(memory_semantic.confidence, excluded.confidence),
            updated_at=CURRENT_TIMESTAMP
        """,
        (category, key, value, confidence),
    )
    return "created"


# ---------------------------------------------------------------------------
# Ebbinghaus decay
# ---------------------------------------------------------------------------
def apply_decay(
    conn: sqlite3.Connection,
    days: int = DECAY_DAYS,
    factor: float = DECAY_FACTOR,
) -> int:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(
        sep=" ", timespec="seconds"
    )
    cur = conn.execute(
        """
        UPDATE memory_semantic
        SET confidence = MAX(confidence * ?, ?),
            updated_at = CURRENT_TIMESTAMP
        WHERE updated_at < ?
        """,
        (factor, MIN_CONFIDENCE, cutoff),
    )
    return cur.rowcount


# ---------------------------------------------------------------------------
# API principal
# ---------------------------------------------------------------------------
def consolidate_day(
    conn: sqlite3.Connection,
    day: date | None = None,
    min_cluster_size: int = MIN_CLUSTER_SIZE,
) -> dict:
    """
    Roda a consolidação para um dia (default: hoje).
    Retorna estatísticas: {episodes, clusters, created, reinforced, decayed}.
    """
    # SQLite CURRENT_TIMESTAMP é UTC. Quando day é None, usamos DATE('now')
    # do próprio SQLite para garantir que a comparação fique na mesma tz.
    if day is None:
        rows = conn.execute(
            """
            SELECT cycle_id, agent_name, action, target, result, details
            FROM memory_episodic
            WHERE DATE(created_at) = DATE('now')
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT cycle_id, agent_name, action, target, result, details
            FROM memory_episodic
            WHERE DATE(created_at) = ?
            """,
            (day.isoformat(),),
        ).fetchall()
    episodes = [
        {
            "cycle_id": r[0],
            "agent_name": r[1],
            "action": r[2],
            "target": r[3],
            "result": r[4],
            "details": r[5],
        }
        for r in rows
    ]

    clusters = cluster_episodes(episodes)
    big_clusters = [c for c in clusters if len(c) >= min_cluster_size]

    created = 0
    reinforced = 0
    for cluster in big_clusters:
        summary = summarize_cluster(cluster)
        outcome = _upsert_semantic(
            conn,
            summary["category"],
            summary["key"],
            summary["value"],
            summary["confidence"],
        )
        if outcome == "created":
            created += 1
        else:
            reinforced += 1

    decayed = apply_decay(conn)

    return {
        "episodes": len(episodes),
        "clusters": len(clusters),
        "big_clusters": len(big_clusters),
        "created": created,
        "reinforced": reinforced,
        "decayed": decayed,
    }
