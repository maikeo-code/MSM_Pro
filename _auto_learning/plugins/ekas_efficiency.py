"""
Plugin 3.1 — ekas_efficiency

Adiciona ao subsistema EKAS:
- Tabela ekas_usage_log (contador diário de tokens/custo)
- Budget cap diário em USD (default $0.50 em dev)
- Helper build_cache_control_messages() para aplicar prompt caching Anthropic
- Circuit breaker BudgetExceeded quando o cap é estourado

Este plugin NÃO importa anthropic — apenas prepara os dados. Os chamadores
(ekas/processors/pipeline.py e ekas/intelligence/query_engine.py) podem
integrar opcionalmente consultando check_budget() antes de chamar a API e
log_usage() depois da resposta.

Pricing Anthropic (abr/2026, USD por 1M tokens) — ajustar se mudar:
- Haiku 4.5        : input $1.00  / output $5.00
- Sonnet 4.6       : input $3.00  / output $15.00
- Opus 4.6         : input $15.00 / output $75.00
- Cached input     : ~10% do preço de input (economia de 90%)
- Batch API        : 50% de desconto sobre tudo
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constantes de pricing (USD por token)
# ---------------------------------------------------------------------------
PRICING = {
    "haiku":  {"input": 1.00  / 1_000_000, "output": 5.00  / 1_000_000},
    "sonnet": {"input": 3.00  / 1_000_000, "output": 15.00 / 1_000_000},
    "opus":   {"input": 15.00 / 1_000_000, "output": 75.00 / 1_000_000},
}
CACHED_INPUT_DISCOUNT = 0.10  # 10% do preço normal de input
BATCH_DISCOUNT = 0.50         # 50% off no Batch API

DEFAULT_BUDGET_USD_DAY = 0.50
DEFAULT_BUDGET_TOKENS_DAY = 200_000


class BudgetExceeded(Exception):
    """Disparado quando o cap diário de custo/tokens do EKAS é ultrapassado."""


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ekas_usage_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    day            TEXT NOT NULL,          -- YYYY-MM-DD
    ts             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    caller         TEXT,                   -- pipeline | query_engine | test
    model          TEXT,                   -- haiku | sonnet | opus
    input_tokens   INTEGER DEFAULT 0,
    output_tokens  INTEGER DEFAULT 0,
    cached_tokens  INTEGER DEFAULT 0,
    batch          INTEGER DEFAULT 0,      -- 1 = Batch API (50% off)
    cost_usd       REAL    DEFAULT 0.0,
    details        TEXT
);
CREATE INDEX IF NOT EXISTS idx_ekas_usage_day ON ekas_usage_log(day);
CREATE INDEX IF NOT EXISTS idx_ekas_usage_caller ON ekas_usage_log(caller, day);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """Aplica o schema do plugin (idempotente)."""
    conn.executescript(SCHEMA_SQL)


# ---------------------------------------------------------------------------
# Cálculo de custo
# ---------------------------------------------------------------------------
def _model_family(model: str) -> str:
    m = (model or "").lower()
    if "opus" in m:
        return "opus"
    if "sonnet" in m:
        return "sonnet"
    return "haiku"  # default conservador


def compute_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
    batch: bool = False,
) -> float:
    """
    Calcula custo USD de uma chamada.

    - input_tokens: total enviado (inclui cached_tokens)
    - cached_tokens: parte do input que foi hit de cache (fica no preço reduzido)
    - output_tokens: tokens gerados
    - batch: True => 50% off em tudo
    """
    fam = _model_family(model)
    p = PRICING[fam]
    fresh_input = max(0, input_tokens - cached_tokens)
    cost = (
        fresh_input * p["input"]
        + cached_tokens * p["input"] * CACHED_INPUT_DISCOUNT
        + output_tokens * p["output"]
    )
    if batch:
        cost *= BATCH_DISCOUNT
    return round(cost, 6)


# ---------------------------------------------------------------------------
# Budget cap
# ---------------------------------------------------------------------------
def _budget_usd() -> float:
    return float(os.environ.get("MAX_EKAS_USD_DIA", DEFAULT_BUDGET_USD_DAY))


def _budget_tokens() -> int:
    return int(os.environ.get("MAX_EKAS_TOKENS_DIA", DEFAULT_BUDGET_TOKENS_DAY))


def _today() -> str:
    return date.today().isoformat()


def get_today_usage(conn: sqlite3.Connection) -> dict:
    """Retorna {tokens_in, tokens_out, cached, cost_usd} do dia corrente."""
    row = conn.execute(
        """
        SELECT
            COALESCE(SUM(input_tokens), 0)  AS tokens_in,
            COALESCE(SUM(output_tokens), 0) AS tokens_out,
            COALESCE(SUM(cached_tokens), 0) AS cached,
            COALESCE(SUM(cost_usd), 0.0)    AS cost_usd
        FROM ekas_usage_log WHERE day = ?
        """,
        (_today(),),
    ).fetchone()
    return {
        "tokens_in":  row[0] if row else 0,
        "tokens_out": row[1] if row else 0,
        "cached":     row[2] if row else 0,
        "cost_usd":   row[3] if row else 0.0,
    }


def check_budget(conn: sqlite3.Connection, planned_cost_usd: float = 0.0) -> None:
    """
    Valida se a próxima chamada cabe no cap. Levanta BudgetExceeded caso contrário.

    Uso: chame ANTES de fazer a chamada à API Anthropic:

        check_budget(conn, planned_cost_usd=0.01)
    """
    usage = get_today_usage(conn)
    cap_usd = _budget_usd()
    cap_tok = _budget_tokens()
    if usage["cost_usd"] + planned_cost_usd > cap_usd:
        raise BudgetExceeded(
            f"EKAS budget USD excedido: "
            f"{usage['cost_usd']:.4f} + {planned_cost_usd:.4f} > {cap_usd:.4f}"
        )
    if usage["tokens_in"] + usage["tokens_out"] > cap_tok:
        raise BudgetExceeded(
            f"EKAS budget tokens excedido: "
            f"{usage['tokens_in'] + usage['tokens_out']} > {cap_tok}"
        )


def log_usage(
    conn: sqlite3.Connection,
    caller: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
    batch: bool = False,
    details: Optional[str] = None,
) -> float:
    """
    Registra uma chamada concluída. Retorna o custo em USD calculado.
    Uso: chame DEPOIS de receber a resposta da API Anthropic.
    """
    cost = compute_cost(model, input_tokens, output_tokens, cached_tokens, batch)
    conn.execute(
        """
        INSERT INTO ekas_usage_log
          (day, caller, model, input_tokens, output_tokens,
           cached_tokens, batch, cost_usd, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _today(), caller, model,
            int(input_tokens), int(output_tokens), int(cached_tokens),
            1 if batch else 0, cost, details,
        ),
    )
    return cost


# ---------------------------------------------------------------------------
# Prompt caching helper
# ---------------------------------------------------------------------------
def build_cache_control_messages(
    system_prompt: str,
    stable_context: str,
    user_prompt: str,
) -> dict:
    """
    Monta o dicionário de parâmetros para client.messages.create()
    já com cache_control ephemeral no system_prompt e no stable_context.

    Devolve algo como:
        {
            "system": [
                {"type": "text", "text": <system_prompt>,
                 "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": <stable_context>,
                 "cache_control": {"type": "ephemeral"}},
            ],
            "messages": [{"role": "user", "content": <user_prompt>}],
        }

    Chamador integra:
        params = build_cache_control_messages(SYSTEM, CONTEXT, pergunta)
        resp = client.messages.create(model=..., max_tokens=..., **params)
    """
    return {
        "system": [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": stable_context,
                "cache_control": {"type": "ephemeral"},
            },
        ],
        "messages": [{"role": "user", "content": user_prompt}],
    }


# ---------------------------------------------------------------------------
# Integração conveniente
# ---------------------------------------------------------------------------
def ensure_initialized(db_path: Path | str) -> None:
    """Garante que o schema do plugin exista no banco apontado."""
    conn = sqlite3.connect(str(db_path))
    try:
        init_schema(conn)
        conn.commit()
    finally:
        conn.close()
