"""
Skill: generate_blueprint

Gera a arquitetura/blueprint completo de um subprojeto ANTES de
qualquer linha de código ser escrita.

Saídas (todas em _auto_learning/planos/blueprint_<nome>/):
- STRUCTURE.md       — árvore de pastas e arquivos a criar
- DEPENDENCIES.md    — grafo de dependências entre componentes
- EXECUTION_ORDER.md — ordem exata de implementação (topological sort)
- AGENTS_PLAN.md     — qual agente faz o quê, quantos são necessários

Filosofia: "meça duas vezes, corte uma".
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


DEFAULT_BLUEPRINT_DIR = (
    Path(__file__).parent.parent.parent / "_auto_learning" / "planos"
)


def _sanitize_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name).lower()


def generate_structure_md(
    project_name: str,
    components: list[dict],
) -> str:
    """
    Gera o conteúdo de STRUCTURE.md.

    components: [
        {"path": "src/auth/", "type": "dir", "purpose": "Autenticação OAuth"},
        {"path": "src/auth/client.py", "type": "file", "purpose": "Cliente OAuth ML",
         "est_lines": 200, "depends_on": ["src/config.py"]},
        ...
    ]
    """
    lines = [
        f"# Blueprint — {project_name}",
        f"_Gerado em {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        "## Estrutura de Pastas e Arquivos",
        "",
        "```",
    ]

    # Árvore visual
    dirs = sorted({c["path"] for c in components if c["type"] == "dir"})
    files = sorted(
        [(c["path"], c.get("purpose", "")) for c in components if c["type"] == "file"]
    )
    for d in dirs:
        indent = "  " * (d.count("/") - 1)
        lines.append(f"{indent}{d}")
    for f, purpose in files:
        indent = "  " * (f.count("/") - 1)
        lines.append(f"{indent}{f.split('/')[-1]}  ← {purpose}")
    lines.append("```")
    lines.append("")

    # Tabela detalhada
    lines.append("## Detalhamento")
    lines.append("")
    lines.append("| Arquivo | Propósito | Est. linhas | Depende de |")
    lines.append("|---|---|---|---|")
    for c in components:
        if c["type"] == "file":
            deps = ", ".join(c.get("depends_on", []))
            lines.append(
                f"| `{c['path']}` | {c.get('purpose','-')} | "
                f"{c.get('est_lines','?')} | {deps or '-'} |"
            )
    lines.append("")
    return "\n".join(lines)


def generate_dependencies_md(
    project_name: str,
    components: list[dict],
) -> str:
    """Gera DEPENDENCIES.md com grafo de dependências em texto."""
    lines = [
        f"# Dependências — {project_name}",
        "",
        "## Grafo (texto)",
        "",
    ]
    for c in components:
        if c["type"] == "file" and c.get("depends_on"):
            for dep in c["depends_on"]:
                lines.append(f"  {dep} → {c['path']}")
    lines.append("")

    # Nós sem dependência (podem começar primeiro)
    roots = [
        c["path"]
        for c in components
        if c["type"] == "file" and not c.get("depends_on")
    ]
    lines.append("## Raízes (sem dependência — começar por estes)")
    for r in roots:
        lines.append(f"- `{r}`")
    lines.append("")
    return "\n".join(lines)


def _topological_sort(components: list[dict]) -> list[str]:
    """Ordena arquivos por dependência (Kahn's algorithm)."""
    files = {c["path"]: c for c in components if c["type"] == "file"}
    in_degree: dict[str, int] = {p: 0 for p in files}
    adj: dict[str, list[str]] = {p: [] for p in files}

    for path, comp in files.items():
        for dep in comp.get("depends_on", []):
            if dep in adj:
                adj[dep].append(path)
                in_degree[path] += 1

    queue = [p for p, d in in_degree.items() if d == 0]
    order = []
    while queue:
        queue.sort()
        node = queue.pop(0)
        order.append(node)
        for neighbor in adj.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Se sobrou algum (ciclo), adiciona no final
    remaining = [p for p in files if p not in order]
    order.extend(sorted(remaining))
    return order


def generate_execution_order_md(
    project_name: str,
    components: list[dict],
) -> str:
    """Gera EXECUTION_ORDER.md com ordem topológica."""
    order = _topological_sort(components)
    lines = [
        f"# Ordem de Execução — {project_name}",
        "",
        "Implementar EXATAMENTE nesta ordem (dependências resolvidas):",
        "",
    ]
    for i, path in enumerate(order, 1):
        comp = next((c for c in components if c["path"] == path), {})
        lines.append(
            f"{i}. `{path}` — {comp.get('purpose', '')} "
            f"(~{comp.get('est_lines', '?')} linhas)"
        )
    lines.append("")
    return "\n".join(lines)


def generate_agents_plan_md(
    project_name: str,
    components: list[dict],
    max_lines_per_agent: int = 500,
) -> str:
    """Gera AGENTS_PLAN.md distribuindo arquivos por agentes."""
    order = _topological_sort(components)
    files = {c["path"]: c for c in components if c["type"] == "file"}

    agents: list[dict] = []
    current: dict = {"id": 1, "files": [], "total_lines": 0}

    for path in order:
        comp = files.get(path, {})
        est = comp.get("est_lines", 100)
        if current["total_lines"] + est > max_lines_per_agent and current["files"]:
            agents.append(current)
            current = {"id": len(agents) + 1, "files": [], "total_lines": 0}
        current["files"].append(path)
        current["total_lines"] += est

    if current["files"]:
        agents.append(current)

    lines = [
        f"# Plano de Agentes — {project_name}",
        "",
        f"**Total de agentes necessários:** {len(agents)}",
        f"**Max linhas por agente:** {max_lines_per_agent}",
        "",
    ]
    for a in agents:
        lines.append(f"### Agente {a['id']} (~{a['total_lines']} linhas)")
        for f in a["files"]:
            comp = files.get(f, {})
            lines.append(f"- `{f}` — {comp.get('purpose', '')}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# API principal
# ---------------------------------------------------------------------------
def generate_blueprint(
    project_name: str,
    components: list[dict],
    blueprint_dir: Path = DEFAULT_BLUEPRINT_DIR,
    max_lines_per_agent: int = 500,
) -> dict:
    """
    Gera todos os 4 arquivos do blueprint numa subpasta.

    Retorna {dir, files: [path1, path2, ...], num_agents, execution_order}.
    """
    safe_name = _sanitize_name(project_name)
    out_dir = Path(blueprint_dir) / f"blueprint_{safe_name}"
    out_dir.mkdir(parents=True, exist_ok=True)

    docs = {
        "STRUCTURE.md": generate_structure_md(project_name, components),
        "DEPENDENCIES.md": generate_dependencies_md(project_name, components),
        "EXECUTION_ORDER.md": generate_execution_order_md(project_name, components),
        "AGENTS_PLAN.md": generate_agents_plan_md(
            project_name, components, max_lines_per_agent
        ),
    }

    paths = []
    for name, content in docs.items():
        p = out_dir / name
        p.write_text(content, encoding="utf-8")
        paths.append(str(p))

    return {
        "dir": str(out_dir),
        "files": paths,
        "num_agents": len(
            generate_agents_plan_md(project_name, components, max_lines_per_agent)
            .split("### Agente")
        ) - 1,
        "execution_order": _topological_sort(components),
    }
