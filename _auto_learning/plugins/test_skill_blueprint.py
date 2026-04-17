"""Testes do plugin skill_blueprint."""
import pytest
from pathlib import Path

from plugins.skill_blueprint import (
    generate_structure_md,
    generate_dependencies_md,
    generate_execution_order_md,
    generate_agents_plan_md,
    generate_blueprint,
    _topological_sort,
)

SAMPLE_COMPONENTS = [
    {"path": "src/", "type": "dir", "purpose": "Código fonte"},
    {"path": "src/config.py", "type": "file", "purpose": "Configuração", "est_lines": 50},
    {"path": "src/auth/", "type": "dir", "purpose": "Autenticação"},
    {"path": "src/auth/client.py", "type": "file", "purpose": "OAuth client",
     "est_lines": 200, "depends_on": ["src/config.py"]},
    {"path": "src/auth/tokens.py", "type": "file", "purpose": "Token manager",
     "est_lines": 150, "depends_on": ["src/auth/client.py"]},
    {"path": "src/api.py", "type": "file", "purpose": "Endpoints REST",
     "est_lines": 300, "depends_on": ["src/auth/tokens.py", "src/config.py"]},
]


def test_generate_structure_md_contem_arvore():
    md = generate_structure_md("TestProject", SAMPLE_COMPONENTS)
    assert "TestProject" in md
    assert "config.py" in md
    assert "client.py" in md
    assert "```" in md


def test_generate_dependencies_md_mostra_grafo():
    md = generate_dependencies_md("TestProject", SAMPLE_COMPONENTS)
    assert "src/config.py" in md
    assert "→" in md
    assert "Raízes" in md


def test_generate_dependencies_md_roots():
    md = generate_dependencies_md("TestProject", SAMPLE_COMPONENTS)
    assert "src/config.py" in md.split("Raízes")[1]


def test_topological_sort_order():
    order = _topological_sort(SAMPLE_COMPONENTS)
    # config.py deve vir antes de client.py
    assert order.index("src/config.py") < order.index("src/auth/client.py")
    # client.py antes de tokens.py
    assert order.index("src/auth/client.py") < order.index("src/auth/tokens.py")
    # tokens.py antes de api.py
    assert order.index("src/auth/tokens.py") < order.index("src/api.py")


def test_topological_sort_sem_deps():
    components = [
        {"path": "a.py", "type": "file"},
        {"path": "b.py", "type": "file"},
    ]
    order = _topological_sort(components)
    assert len(order) == 2


def test_generate_execution_order_md_numerado():
    md = generate_execution_order_md("Test", SAMPLE_COMPONENTS)
    assert "1. " in md
    assert "src/config.py" in md


def test_generate_agents_plan_md_distribui():
    md = generate_agents_plan_md("Test", SAMPLE_COMPONENTS, max_lines_per_agent=300)
    assert "Agente 1" in md
    assert "Agente" in md


def test_generate_agents_plan_md_respeita_max():
    md = generate_agents_plan_md("Test", SAMPLE_COMPONENTS, max_lines_per_agent=100)
    # Com max=100, config(50)+client(200) já estoura, deve ter múltiplos agentes
    agent_count = md.count("### Agente")
    assert agent_count >= 2


def test_generate_blueprint_cria_4_arquivos(tmp_path):
    result = generate_blueprint(
        "MeuProjeto", SAMPLE_COMPONENTS, blueprint_dir=tmp_path
    )
    assert len(result["files"]) == 4
    for f in result["files"]:
        assert Path(f).exists()
    assert "blueprint_meuprojeto" in result["dir"]


def test_generate_blueprint_retorna_execution_order(tmp_path):
    result = generate_blueprint(
        "Test", SAMPLE_COMPONENTS, blueprint_dir=tmp_path
    )
    assert "src/config.py" in result["execution_order"]
    assert result["num_agents"] >= 1


def test_generate_blueprint_pasta_criada(tmp_path):
    result = generate_blueprint("X", SAMPLE_COMPONENTS, blueprint_dir=tmp_path)
    assert Path(result["dir"]).is_dir()
