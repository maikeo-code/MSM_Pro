"""Testes do plugin skill_split_task."""
import pytest
from pathlib import Path

from plugins.skill_split_task import (
    estimate_tokens,
    estimate_file_tokens,
    split_file,
    split_task,
    split_directory,
    generate_execution_plan,
)


def test_estimate_tokens_proporcional():
    t1 = estimate_tokens("x" * 100)
    t2 = estimate_tokens("x" * 1000)
    assert t2 > t1
    assert t2 == pytest.approx(t1 * 10, rel=0.1)


def test_estimate_tokens_vazio():
    assert estimate_tokens("") == 0


def test_estimate_file_tokens_inexistente():
    info = estimate_file_tokens("/nao/existe.py")
    assert info["exists"] is False
    assert info["est_tokens"] == 0


def test_estimate_file_tokens_real(tmp_path):
    f = tmp_path / "test.py"
    f.write_text("x" * 7000, encoding="utf-8")
    info = estimate_file_tokens(f)
    assert info["exists"] is True
    assert info["est_tokens"] > 0
    assert info["lines"] == 1
    assert info["chars"] == 7000


def test_split_file_pequeno_nao_divide(tmp_path):
    f = tmp_path / "small.py"
    f.write_text("print('hello')\n" * 10, encoding="utf-8")
    parts = split_file(f, max_tokens=30000)
    assert len(parts) == 1
    assert parts[0]["part"] == 1


def test_split_file_grande_divide(tmp_path):
    f = tmp_path / "big.py"
    # ~100k chars = ~28k tokens, max_tokens=10k deve dar ~3 partes
    f.write_text("x = 1  # linha de codigo\n" * 4000, encoding="utf-8")
    parts = split_file(f, max_tokens=10000)
    assert len(parts) >= 2
    assert parts[0]["start_line"] == 1
    assert parts[-1]["end_line"] == 4000


def test_split_file_overlap(tmp_path):
    f = tmp_path / "overlap.py"
    f.write_text("linha\n" * 1000, encoding="utf-8")
    parts = split_file(f, max_tokens=500, overlap_lines=5)
    if len(parts) >= 2:
        # parte 2 deve começar ANTES de onde parte 1 terminou
        assert parts[1]["start_line"] < parts[0]["end_line"]


def test_split_file_inexistente():
    assert split_file("/nao/existe.py") == []


def test_split_task_divide_componentes():
    plan = split_task(
        description="Refatorar módulo",
        components=["auth", "kpi", "listagem", "filtros", "export"],
        max_per_agent=2,
    )
    assert len(plan) == 3
    assert plan[0]["agent_id"] == 1
    assert len(plan[0]["components"]) == 2


def test_split_task_vazio():
    assert split_task("desc", [], max_per_agent=3) == []


def test_split_task_cabe_em_um():
    plan = split_task("desc", ["a", "b"], max_per_agent=5)
    assert len(plan) == 1


def test_split_directory(tmp_path):
    # Cria alguns arquivos
    (tmp_path / "a.py").write_text("x = 1\n" * 100, encoding="utf-8")
    (tmp_path / "b.py").write_text("y = 2\n" * 100, encoding="utf-8")
    (tmp_path / "c.txt").write_text("ignore me", encoding="utf-8")
    batches = split_directory(tmp_path, max_tokens=50000)
    assert len(batches) >= 1
    # c.txt não deve aparecer (extensão errada)
    all_files = [f for b in batches for f in b["files"]]
    assert not any("c.txt" in f for f in all_files)


def test_split_directory_vazio(tmp_path):
    assert split_directory(tmp_path) == []


def test_generate_execution_plan(tmp_path):
    (tmp_path / "main.py").write_text("print('hi')\n" * 50, encoding="utf-8")
    plan = generate_execution_plan(tmp_path, "Analisar projeto X")
    assert plan["task"] == "Analisar projeto X"
    assert plan["total_files"] >= 1
    assert plan["num_agents_needed"] >= 1
    assert "estimated_cost_haiku_usd" in plan
