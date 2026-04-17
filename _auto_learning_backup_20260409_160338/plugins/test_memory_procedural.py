"""Testes do plugin memory_procedural."""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from plugins.memory_procedural import (
    init_schema,
    register_skill,
    get_skill,
    list_skills,
    run_skill,
    deprecate_skill,
    promote_to_stable,
    auto_deprecate_stale,
    SkillError,
    MAX_ACTIVE_SKILLS,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    init_schema(c)
    c.commit()
    yield c
    c.close()


@pytest.fixture
def skills_dir(tmp_path):
    d = tmp_path / "skills"
    d.mkdir()
    return d


def test_init_schema_cria_tabela(conn):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='skills'"
    ).fetchone()
    assert row is not None


def test_register_skill_cria_arquivo(conn, skills_dir):
    meta = register_skill(
        conn,
        name="soma",
        description="Soma dois inteiros",
        code_body="a = payload.get('a', 0)\nb = payload.get('b', 0)\nreturn {'ok': True, 'value': a + b}",
        skills_dir=skills_dir,
    )
    assert meta["version"] == 1
    assert Path(meta["code_path"]).exists()
    assert "soma_v1.py" in meta["code_path"]


def test_register_skill_incrementa_versao(conn, skills_dir):
    register_skill(conn, "x", "desc", "return {'ok': True}", skills_dir=skills_dir)
    m2 = register_skill(conn, "x", "desc v2", "return {'ok': True}", skills_dir=skills_dir)
    assert m2["version"] == 2


def test_register_skill_respeita_cap(conn, skills_dir, monkeypatch):
    monkeypatch.setattr("plugins.memory_procedural.MAX_ACTIVE_SKILLS", 2)
    register_skill(conn, "a", "d", "return {'ok': True}", skills_dir=skills_dir)
    register_skill(conn, "b", "d", "return {'ok': True}", skills_dir=skills_dir)
    with pytest.raises(SkillError):
        register_skill(conn, "c", "d", "return {'ok': True}", skills_dir=skills_dir)


def test_get_skill_retorna_latest_ativa(conn, skills_dir):
    register_skill(conn, "calc", "v1", "return {'ok': True}", skills_dir=skills_dir)
    register_skill(conn, "calc", "v2", "return {'ok': True}", skills_dir=skills_dir)
    meta = get_skill(conn, "calc")
    assert meta is not None
    assert meta["version"] == 2


def test_get_skill_version_especifica(conn, skills_dir):
    register_skill(conn, "calc", "v1", "return {'ok': True}", skills_dir=skills_dir)
    register_skill(conn, "calc", "v2", "return {'ok': True}", skills_dir=skills_dir)
    m = get_skill(conn, "calc", version=1)
    assert m["version"] == 1


def test_get_skill_inexistente(conn):
    assert get_skill(conn, "fantasma") is None


def test_run_skill_executa_e_retorna(conn, skills_dir):
    register_skill(
        conn,
        "soma",
        "soma",
        "return {'ok': True, 'value': payload['a'] + payload['b']}",
        skills_dir=skills_dir,
    )
    r = run_skill(conn, "soma", {"a": 2, "b": 3})
    assert r["ok"] is True
    assert r["value"] == 5


def test_run_skill_atualiza_metricas(conn, skills_dir):
    register_skill(
        conn, "s", "d", "return {'ok': True}", skills_dir=skills_dir
    )
    run_skill(conn, "s", {})
    run_skill(conn, "s", {})
    row = conn.execute(
        "SELECT times_used, times_success FROM skills WHERE name='s'"
    ).fetchone()
    assert row[0] == 2
    assert row[1] == 2


def test_run_skill_captura_erro(conn, skills_dir):
    register_skill(
        conn, "bad", "d", "raise ValueError('oops')", skills_dir=skills_dir
    )
    r = run_skill(conn, "bad", {})
    assert r["ok"] is False
    assert "oops" in r["error"]
    row = conn.execute("SELECT times_fail FROM skills WHERE name='bad'").fetchone()
    assert row[0] == 1


def test_run_skill_inexistente(conn):
    with pytest.raises(SkillError):
        run_skill(conn, "nao_existe", {})


def test_deprecate_skill(conn, skills_dir):
    register_skill(conn, "velha", "d", "return {'ok': True}", skills_dir=skills_dir)
    assert deprecate_skill(conn, "velha", 1) is True
    assert get_skill(conn, "velha") is None  # não aparece em ACTIVE/STABLE


def test_promote_to_stable(conn, skills_dir):
    register_skill(conn, "boa", "d", "return {'ok': True}", skills_dir=skills_dir)
    assert promote_to_stable(conn, "boa", 1) is True
    meta = get_skill(conn, "boa")
    assert meta["status"] == "STABLE"


def test_auto_deprecate_stale_marca_antigas(conn, skills_dir):
    register_skill(conn, "antiga", "d", "return {'ok': True}", skills_dir=skills_dir)
    # força created_at antigo
    old = (datetime.now() - timedelta(days=60)).isoformat(sep=" ", timespec="seconds")
    conn.execute(
        "UPDATE skills SET created_at=?, last_used_at=NULL WHERE name='antiga'",
        (old,),
    )
    n = auto_deprecate_stale(conn, days=30)
    assert n == 1
    row = conn.execute("SELECT status FROM skills WHERE name='antiga'").fetchone()
    assert row[0] == "DEPRECATED"


def test_auto_deprecate_poupa_recentes(conn, skills_dir):
    register_skill(conn, "nova", "d", "return {'ok': True}", skills_dir=skills_dir)
    n = auto_deprecate_stale(conn, days=30)
    assert n == 0


def test_list_skills_filtra_status(conn, skills_dir):
    register_skill(conn, "a", "d", "return {'ok': True}", skills_dir=skills_dir)
    register_skill(conn, "b", "d", "return {'ok': True}", skills_dir=skills_dir)
    deprecate_skill(conn, "b", 1)
    active = list_skills(conn, status="ACTIVE")
    deprecated = list_skills(conn, status="DEPRECATED")
    assert len(active) == 1 and active[0]["name"] == "a"
    assert len(deprecated) == 1 and deprecated[0]["name"] == "b"
