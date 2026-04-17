"""
============================================================
SWARM GENESIS v7.0 — DESINSTALADOR
Remove o sistema do projeto preservando os dados.

Uso (executar de dentro da pasta _auto_learning):
    python desinstalar.py
============================================================
"""

import os
import sys
import json
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

BASE_DIR = Path(__file__).parent


def get_stats():
    """Obtem estatisticas antes de remover."""
    db_path = BASE_DIR / "db" / "learning.db"
    if not db_path.exists():
        return {}
    try:
        conn = sqlite3.connect(db_path)
        stats = {}
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        for t in tables:
            try:
                # Table name from sqlite_master is safe but quote for defense
                stats[t] = conn.execute(
                    f'SELECT COUNT(*) FROM "{t}"'
                ).fetchone()[0]
            except Exception:
                stats[t] = "?"
        conn.close()
        return stats
    except Exception:
        return {}


def export_before_remove():
    """Exporta todos os dados antes de remover."""
    db_path = BASE_DIR / "db" / "learning.db"
    if not db_path.exists():
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_dir = BASE_DIR.parent / f"_auto_learning_export_{ts}"
    export_dir.mkdir(exist_ok=True)

    # Copia banco
    shutil.copy2(db_path, export_dir / "learning.db")

    # Exporta JSON
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name != 'schema_version'"
        ).fetchall()]
        export = {"exported_at": ts, "version": "7.0"}
        for t in tables:
            try:
                rows = conn.execute(f'SELECT * FROM "{t}"').fetchall()
                export[t] = [dict(r) for r in rows]
            except Exception:
                export[t] = []
        conn.close()
        with open(export_dir / "export_completo.json", "w", encoding="utf-8") as f:
            json.dump(export, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        print(f"  Aviso: export JSON falhou ({e}), mas o .db foi copiado")

    # Copia docs e regras
    for subdir in ["docs", "regras", "planos", "agents"]:
        src = BASE_DIR / subdir
        if src.exists():
            shutil.copytree(src, export_dir / subdir, dirs_exist_ok=True)

    return export_dir


def remove_claude_md_section():
    """Remove a secao SWARM GENESIS do CLAUDE.md."""
    claude_md = BASE_DIR.parent / "CLAUDE.md"
    if not claude_md.exists():
        return

    content = claude_md.read_text(encoding="utf-8")
    for marker in ["## SWARM GENESIS v7.0", "## SWARM GENESIS v6.0", "## SWARM GENESIS v5.0", "## SWARM GENESIS v4.0"]:
        if marker in content:
            idx = content.find(marker)
            # Find start: preceding --- separator
            sep_start = content.rfind("---", 0, idx)
            start = sep_start if sep_start > 0 else idx
            # Find end: next top-level ## header (not ###) or --- after marker
            end = len(content)
            search_from = content.find("\n", idx)
            if search_from > 0:
                next_sep = content.find("\n---\n", search_from)
                # Find next ## header that is NOT a ### subsection
                pos = search_from
                next_header = -1
                while True:
                    pos = content.find("\n## ", pos + 1)
                    if pos < 0:
                        break
                    # Check it's exactly "## " not "### "
                    after_hash = content[pos+1:]
                    if after_hash.startswith("## ") and not after_hash.startswith("### "):
                        next_header = pos
                        break
                candidates = [c for c in [next_sep, next_header] if c > 0]
                if candidates:
                    end = min(candidates)
            before = content[:start].rstrip()
            after = content[end:].lstrip("\n")
            content = before + ("\n\n" + after if after else "") + "\n"
            claude_md.write_text(content, encoding="utf-8")
            print("  Secao removida do CLAUDE.md")
            return

    print("  Nenhuma secao SWARM encontrada no CLAUDE.md")


def clean_gitignore():
    """Remove entradas do SWARM GENESIS do .gitignore."""
    gitignore = BASE_DIR.parent / ".gitignore"
    if not gitignore.exists():
        return
    lines = gitignore.read_text(encoding="utf-8").splitlines()
    new_lines = []
    skip = False
    for line in lines:
        if "SWARM GENESIS" in line:
            skip = True
            continue
        if skip and line.startswith("_auto_learning"):
            continue
        skip = False
        new_lines.append(line)
    gitignore.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print("  .gitignore limpo")


def main():
    print(f"\n{'='*60}")
    print(f"  SWARM GENESIS v7.0 — Desinstalador")
    print(f"{'='*60}\n")

    # Mostrar estatisticas
    stats = get_stats()
    if stats:
        print("  Dados acumulados no sistema:")
        for table, count in sorted(stats.items()):
            if count and count != "?" and count > 0:
                print(f"    {table}: {count} registros")
        print()

    # Confirmar
    resp = input("  Deseja desinstalar? Todos os dados serao exportados primeiro. (s/n): ")
    if resp.lower() not in ("s", "sim", "y", "yes"):
        print("  Cancelado.")
        sys.exit(0)

    # Exportar
    print("\n  Exportando dados...")
    export_dir = export_before_remove()
    if export_dir:
        print(f"  Dados exportados para: {export_dir}")

    # Remover secao do CLAUDE.md
    print("\n  Limpando CLAUDE.md...")
    remove_claude_md_section()

    # Limpar .gitignore
    clean_gitignore()

    # Remover pasta
    print(f"\n  Removendo {BASE_DIR}...")
    try:
        # Move para fora antes de remover (evita problemas de CWD)
        os.chdir(BASE_DIR.parent)
        shutil.rmtree(BASE_DIR)
        print("  Pasta removida")
    except Exception as e:
        print(f"  Nao foi possivel remover automaticamente: {e}")
        print(f"  Remova manualmente: {BASE_DIR}")

    print(f"""
{'='*60}
  Desinstalacao concluida!

  Seus dados foram preservados em:
    {export_dir or '(nenhum dado encontrado)'}

  Para restaurar os dados no futuro:
    1. Reinstale o sistema: python instalar.py <projeto>
    2. Copie o learning.db do export para _auto_learning/db/
{'='*60}
""")


if __name__ == "__main__":
    main()
