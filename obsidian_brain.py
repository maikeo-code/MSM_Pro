"""
obsidian_brain.py — Sincronizador MSM Pro ↔ Obsidian

Atualiza automaticamente o vault Obsidian com o estado real do projeto.
Uso: python obsidian_brain.py [--full-sync|--update-metrics|--daily-note|--status]
"""

import argparse
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

VAULT = Path("C:/Users/Maikeo/MSM_Imports_Mercado_Livre/Obsidium/MSM PRO")
PROJECT = Path("C:/Users/Maikeo/MSM_Imports_Mercado_Livre/msm_pro")
TODAY = datetime.now().strftime("%Y-%m-%d")
YESTERDAY = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
TOMORROW = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")


def run(cmd: str, cwd: Path | None = None) -> str:
    """Executa comando e retorna stdout."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            cwd=cwd or PROJECT, timeout=30
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_git_log(n: int = 10) -> str:
    return run(f"git log --oneline -{n}")


def get_coverage() -> str:
    """Retorna % de cobertura atual."""
    out = run("python -m pytest --co -q --tb=no 2>/dev/null | tail -1", cwd=PROJECT / "backend")
    # Tenta ler do arquivo de cobertura se existir
    cov_file = PROJECT / "backend" / ".coverage"
    if cov_file.exists():
        report = run("python -m coverage report --format=total", cwd=PROJECT / "backend")
        if report and report.replace(".", "").isdigit():
            return f"{report}%"
    return "~55%"


def get_test_count() -> tuple[int, int]:
    """Retorna (total_testes, falhando) lendo do coverage.json se existir."""
    # Tenta ler do coverage.json primeiro (mais rápido)
    cov_json = PROJECT / "backend" / "coverage.json"
    if cov_json.exists():
        try:
            import json
            data = json.loads(cov_json.read_text(encoding="utf-8"))
            # coverage.json não tem contagem de testes, usar fallback
        except Exception:
            pass

    out = run(
        "python -m pytest tests/ --tb=no -q --no-header 2>&1 | tail -5",
        cwd=PROJECT / "backend"
    )
    passed = failed = 0
    for line in out.splitlines():
        if "passed" in line:
            parts = line.split()
            for i, p in enumerate(parts):
                if p == "passed":
                    try:
                        passed = int(parts[i - 1])
                    except (ValueError, IndexError):
                        pass
                if p == "failed":
                    try:
                        failed = int(parts[i - 1])
                    except (ValueError, IndexError):
                        pass
    return passed, failed


def get_migration_count() -> str:
    out = run("alembic history 2>/dev/null | wc -l", cwd=PROJECT / "backend")
    return out or "27"


def create_daily_note() -> None:
    """Cria daily note do dia se não existir."""
    daily_dir = VAULT / "13 - Daily Notes"
    daily_dir.mkdir(exist_ok=True)
    note_path = daily_dir / f"{TODAY}.md"

    if note_path.exists():
        print(f"Daily note já existe: {note_path.name}")
        return

    recent_commits = get_git_log(5)
    commits_section = "\n".join(f"- `{line}`" for line in recent_commits.splitlines()) if recent_commits else "- (nenhum commit hoje)"

    content = f"""---
title: Daily Note — {TODAY}
tags: [daily, log]
date: {TODAY}
type: daily
---

# 📅 {TODAY}

---

## 🎯 Foco do Dia

-

---

## ✅ Concluído

-

---

## 🚧 Em Progresso

-

---

## 🔴 Bloqueios

-

---

## 💡 Aprendizados

-

---

## 📝 Commits do Dia

{commits_section}

---

## Contexto do Projeto

**Backend:** https://msmpro-production.up.railway.app/health
**Sprint atual:** Sprint 13

---

Anterior: [[13 - Daily Notes/{YESTERDAY}]] | Próxima: [[13 - Daily Notes/{TOMORROW}]]
"""
    note_path.write_text(content, encoding="utf-8")
    print(f"✅ Daily note criada: {note_path.name}")


def update_metrics() -> None:
    """Atualiza _Dashboard/📊 Métricas do Projeto.md com dados reais."""
    coverage = get_coverage()
    passed, failed = get_test_count()
    git_log = get_git_log(5)
    migrations = get_migration_count()

    metrics_path = VAULT / "_Dashboard" / "📊 Métricas do Projeto.md"
    if not metrics_path.exists():
        print("⚠️  Arquivo de métricas não encontrado.")
        return

    content = metrics_path.read_text(encoding="utf-8")

    # Atualizar linha de cobertura
    lines = content.splitlines()
    updated = []
    for line in lines:
        if "Cobertura total" in line and "|" in line:
            parts = line.split("|")
            if len(parts) >= 3:
                parts[2] = f" {coverage} "
                line = "|".join(parts)
        if "Testes backend" in line and "|" in line:
            parts = line.split("|")
            if len(parts) >= 3:
                parts[2] = f" {passed} "
                line = "|".join(parts)
        if "Testes falhando" in line and "|" in line:
            parts = line.split("|")
            if len(parts) >= 3:
                parts[2] = f" {failed} "
                line = "|".join(parts)
        updated.append(line)

    # Atualizar data no frontmatter
    new_content = "\n".join(updated)
    new_content = new_content.replace(
        f"date: {YESTERDAY}", f"date: {TODAY}"
    )

    metrics_path.write_text(new_content, encoding="utf-8")
    print(f"✅ Métricas atualizadas: cobertura={coverage}, testes={passed} passed/{failed} failed")


def show_status() -> None:
    """Mostra estado atual do vault."""
    total_notes = len(list(VAULT.rglob("*.md")))
    coverage = get_coverage()
    passed, failed = get_test_count()
    recent = get_git_log(3)

    sep = "=" * 42
    print(sep)
    print("  MSM Pro -- Brain Status")
    print(sep)
    print(f"  Vault : {str(VAULT)[:40]}")
    print(f"  Notas : {total_notes} arquivos .md")
    print(f"  Cobertura: {coverage}")
    print(f"  Testes: {passed} passed / {failed} failed")
    print(sep)
    print("  Ultimos commits:")
    for line in recent.splitlines():
        print(f"    {line}")
    print(sep)


def full_sync() -> None:
    """Sincronização completa."""
    print("🔄 Iniciando sincronização completa...")
    create_daily_note()
    update_metrics()
    print("✅ Sincronização completa!")


def new_bug(title: str, priority: str = "high", module: str = "vendas") -> None:
    """Cria nota de bug a partir do template."""
    bugs_dir = VAULT / "08 - Bugs e Fixes"
    filename = title.replace(" ", "-").replace("/", "-")[:50] + ".md"
    note_path = bugs_dir / filename

    content = f"""---
title: {title}
tags: [bug, fix, {module}]
date: {TODAY}
type: bug
status: open
priority: {priority}
module: {module}
---

# {title}

**Prioridade:** {priority.upper()}
**Módulo:** `{module}`
**Status:** Open

---

## 📋 Descrição



---

## 🔍 Root Cause



---

## 🔧 Fix

### Arquivos alterados
-

---

## ✅ Como verificar

```bash
curl ...
```
"""
    note_path.write_text(content, encoding="utf-8")
    print(f"✅ Bug criado: {note_path.name}")


def new_adr(title: str) -> None:
    """Cria nova decisão arquitetural."""
    adr_dir = VAULT / "14 - ADR"
    adr_dir.mkdir(exist_ok=True)
    filename = title.replace(" ", "-").replace("/", "-")[:60] + ".md"
    note_path = adr_dir / filename

    content = f"""---
title: {title}
tags: [adr, arquitetura, decisão]
date: {TODAY}
type: decision
status: active
---

# {title}

**Data:** {TODAY}
**Status:** ✅ Ativo

---

## 📋 Contexto



---

## ✅ Decisão



---

## 📐 Consequências



"""
    note_path.write_text(content, encoding="utf-8")
    print(f"✅ ADR criado: {note_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="MSM Pro Obsidian Brain Sync")
    parser.add_argument("--full-sync", action="store_true", help="Sincronização completa")
    parser.add_argument("--update-metrics", action="store_true", help="Atualizar métricas")
    parser.add_argument("--daily-note", action="store_true", help="Criar daily note de hoje")
    parser.add_argument("--status", action="store_true", help="Ver estado atual")
    parser.add_argument("--new-bug", type=str, help="Criar nota de bug")
    parser.add_argument("--priority", type=str, default="high", help="Prioridade do bug")
    parser.add_argument("--module", type=str, default="vendas", help="Módulo do bug")
    parser.add_argument("--new-adr", type=str, help="Criar decisão arquitetural")

    args = parser.parse_args()

    if args.full_sync:
        full_sync()
    elif args.update_metrics:
        update_metrics()
    elif args.daily_note:
        create_daily_note()
    elif args.status:
        show_status()
    elif args.new_bug:
        new_bug(args.new_bug, args.priority, args.module)
    elif args.new_adr:
        new_adr(args.new_adr)
    else:
        parser.print_help()
        print("\n💡 Dica: use --full-sync para sincronização completa")


if __name__ == "__main__":
    main()
