"""
Skill: split_large_task

Dado um arquivo grande ou tarefa complexa, gera um plano de divisão
em N partes menores que cabem no contexto de um agente (~30k tokens).

Uso:
    from plugins.skill_split_task import split_file, split_task, estimate_tokens

    # Dividir arquivo grande
    plan = split_file("caminho/arquivo_enorme.py", max_tokens=30000)
    # → [{"part": 1, "start_line": 1, "end_line": 450, "est_tokens": 28000}, ...]

    # Dividir tarefa abstrata em subtarefas
    plan = split_task(
        description="Refatorar módulo de vendas (2100 linhas, 15 funções)",
        components=["auth", "kpi", "listagem", "filtros", "export"],
        max_per_agent=3,
    )
    # → [{"agent_id": 1, "components": ["auth", "kpi", "listagem"]}, ...]
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Optional


# Estimativa conservadora: 1 token ≈ 4 caracteres em código
# Para português/inglês misto, ~3.5 chars/token
CHARS_PER_TOKEN = 3.5
DEFAULT_MAX_TOKENS = 30_000


def estimate_tokens(text: str) -> int:
    """Estima tokens de um texto. Conservador (arredonda pra cima)."""
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def estimate_file_tokens(file_path: str | Path) -> dict:
    """Retorna {path, chars, lines, est_tokens} de um arquivo."""
    p = Path(file_path)
    if not p.exists():
        return {"path": str(p), "chars": 0, "lines": 0, "est_tokens": 0, "exists": False}
    content = p.read_text(encoding="utf-8", errors="replace")
    lines = content.count("\n") + 1
    return {
        "path": str(p),
        "chars": len(content),
        "lines": lines,
        "est_tokens": estimate_tokens(content),
        "exists": True,
    }


def split_file(
    file_path: str | Path,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_lines: int = 5,
) -> list[dict]:
    """
    Divide um arquivo em partes que cabem em max_tokens cada.

    Cada parte tem overlap_lines de sobreposição com a anterior para
    manter contexto de borda (funções cortadas, etc).

    Retorna lista de dicts:
    [
        {"part": 1, "start_line": 1, "end_line": 450, "est_tokens": 28500},
        {"part": 2, "start_line": 446, "end_line": 900, "est_tokens": 29200},
        ...
    ]
    """
    p = Path(file_path)
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    total = len(lines)
    if total == 0:
        return []

    # Estima tokens do arquivo inteiro
    total_tokens = estimate_tokens("".join(lines))
    if total_tokens <= max_tokens:
        return [{"part": 1, "start_line": 1, "end_line": total, "est_tokens": total_tokens}]

    # Calcula tamanho de cada parte em linhas
    avg_chars_per_line = sum(len(l) for l in lines) / total
    max_chars = int(max_tokens * CHARS_PER_TOKEN)
    lines_per_part = max(10, int(max_chars / avg_chars_per_line))

    parts = []
    start = 0
    part_num = 1
    while start < total:
        end = min(start + lines_per_part, total)
        chunk = "".join(lines[start:end])
        parts.append({
            "part": part_num,
            "start_line": start + 1,  # 1-indexed
            "end_line": end,
            "est_tokens": estimate_tokens(chunk),
        })
        part_num += 1
        start = max(start + 1, end - overlap_lines)  # overlap

    return parts


def split_task(
    description: str,
    components: list[str],
    max_per_agent: int = 3,
) -> list[dict]:
    """
    Divide uma lista de componentes em grupos que cabem por agente.

    Retorna:
    [
        {"agent_id": 1, "components": ["auth", "kpi", "listagem"],
         "description": "Agente 1: auth, kpi, listagem"},
        {"agent_id": 2, "components": ["filtros", "export"],
         "description": "Agente 2: filtros, export"},
    ]
    """
    if not components:
        return []
    n_agents = math.ceil(len(components) / max_per_agent)
    parts = []
    for i in range(n_agents):
        chunk = components[i * max_per_agent : (i + 1) * max_per_agent]
        parts.append({
            "agent_id": i + 1,
            "components": chunk,
            "description": f"Agente {i + 1}: {', '.join(chunk)}",
        })
    return parts


def split_directory(
    dir_path: str | Path,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    extensions: tuple[str, ...] = (".py", ".js", ".ts", ".jsx", ".tsx"),
) -> list[dict]:
    """
    Analisa todos os arquivos de um diretório e agrupa em batches
    que cabem em max_tokens cada.

    Retorna:
    [
        {"batch": 1, "files": ["a.py", "b.py"], "total_tokens": 28000},
        {"batch": 2, "files": ["c.py", "d.py"], "total_tokens": 25000},
    ]
    """
    d = Path(dir_path)
    if not d.exists():
        return []

    file_infos = []
    for ext in extensions:
        for f in d.rglob(f"*{ext}"):
            if "_auto_learning" in str(f) or "node_modules" in str(f):
                continue
            info = estimate_file_tokens(f)
            if info["est_tokens"] > 0:
                file_infos.append(info)

    # Ordena por tokens (menor primeiro para bin-packing guloso)
    file_infos.sort(key=lambda x: x["est_tokens"])

    batches = []
    current_batch: list[str] = []
    current_tokens = 0

    for fi in file_infos:
        if fi["est_tokens"] > max_tokens:
            # Arquivo individual já excede — vai sozinho (será split_file depois)
            batches.append({
                "batch": len(batches) + 1,
                "files": [fi["path"]],
                "total_tokens": fi["est_tokens"],
                "needs_split": True,
            })
            continue
        if current_tokens + fi["est_tokens"] > max_tokens:
            if current_batch:
                batches.append({
                    "batch": len(batches) + 1,
                    "files": current_batch,
                    "total_tokens": current_tokens,
                    "needs_split": False,
                })
            current_batch = [fi["path"]]
            current_tokens = fi["est_tokens"]
        else:
            current_batch.append(fi["path"])
            current_tokens += fi["est_tokens"]

    if current_batch:
        batches.append({
            "batch": len(batches) + 1,
            "files": current_batch,
            "total_tokens": current_tokens,
            "needs_split": False,
        })

    return batches


def generate_execution_plan(
    dir_path: str | Path,
    task_description: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict:
    """
    Gera um plano de execução completo: quantos agentes, quais arquivos cada um
    processa, e estimativa de custo em tokens.

    Retorna dict pronto para ser salvo como plano em _auto_learning/planos/.
    """
    batches = split_directory(dir_path, max_tokens=max_tokens)
    total_tokens = sum(b["total_tokens"] for b in batches)
    oversized = [b for b in batches if b.get("needs_split")]

    return {
        "task": task_description,
        "directory": str(dir_path),
        "total_files": sum(len(b["files"]) for b in batches),
        "total_tokens": total_tokens,
        "num_agents_needed": len(batches),
        "batches": batches,
        "oversized_files": [b["files"][0] for b in oversized],
        "estimated_cost_haiku_usd": round(total_tokens * 1.0 / 1_000_000, 4),
        "estimated_cost_sonnet_usd": round(total_tokens * 3.0 / 1_000_000, 4),
    }
