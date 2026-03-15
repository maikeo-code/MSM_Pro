"""
============================================================
DESINSTALADOR DO SISTEMA DE AUTO-APRENDIZADO
============================================================
Remove o sistema do projeto, restaurando o CLAUDE.md original.
Exporta todos os aprendizados ANTES de remover.

Uso:
    python desinstalar.py C:\\caminho\\do\\projeto
    python desinstalar.py .

O que faz:
    1. Exporta tudo (planos, sucessos, falhas, regras) para um ZIP
    2. Restaura o CLAUDE.md original (remove a secao adicionada)
    3. Remove a pasta _auto_learning/
    4. Limpa o .gitignore
    5. Projeto volta EXATAMENTE como era antes da instalacao
============================================================
"""

import os
import sys
import shutil
import zipfile
import json
from pathlib import Path
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LEARNING_FOLDER = "_auto_learning"
CLAUDE_SECTION_MARKER = "## AUTO-LEARNING SYSTEM"


def export_before_removal(project_dir: Path) -> str:
    """Exporta todos os dados de aprendizado para um ZIP antes de remover."""
    base = project_dir / LEARNING_FOLDER
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"auto_learning_export_{timestamp}.zip"
    zip_path = project_dir / zip_name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(base):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(project_dir)
                zf.write(file_path, arcname)

    # Tamanho do ZIP
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  Exportado: {zip_name} ({size_mb:.1f} MB)")
    return zip_name


def restore_claude_md(project_dir: Path):
    """Remove APENAS a secao de auto-learning do CLAUDE.md, preservando todo o resto."""
    claude_md = project_dir / "CLAUDE.md"

    if not claude_md.exists():
        print("  CLAUDE.md nao encontrado (nada para restaurar)")
        return

    content = claude_md.read_text(encoding="utf-8")

    if CLAUDE_SECTION_MARKER not in content:
        print("  CLAUDE.md nao tem secao de auto-learning (ja esta limpo)")
        return

    # Encontra onde a secao comeca
    # A secao e precedida por "\n\n---\n\n## AUTO-LEARNING SYSTEM"
    # Remove tudo a partir do marcador "---" que precede a secao
    lines = content.split("\n")
    cut_index = None

    for i, line in enumerate(lines):
        if line.strip() == CLAUDE_SECTION_MARKER:
            # Volta para encontrar o "---" que precede a secao
            cut_index = i
            # Procura o "---" acima (pode ter linhas vazias entre)
            for j in range(i - 1, max(i - 5, -1), -1):
                if lines[j].strip() == "---":
                    cut_index = j
                    break
            # Remove linhas vazias extras acima do corte
            while cut_index > 0 and lines[cut_index - 1].strip() == "":
                cut_index -= 1
            break

    if cut_index is not None:
        restored = "\n".join(lines[:cut_index])
        # Garante que termina com uma newline limpa
        restored = restored.rstrip() + "\n"
        claude_md.write_text(restored, encoding="utf-8")
        print("  CLAUDE.md restaurado (secao de auto-learning removida)")
    else:
        print("  AVISO: Marcador encontrado mas nao conseguiu cortar. Verifique manualmente.")


def clean_gitignore(project_dir: Path):
    """Remove entradas do auto-learning do .gitignore."""
    gitignore = project_dir / ".gitignore"

    if not gitignore.exists():
        return

    content = gitignore.read_text(encoding="utf-8")

    if LEARNING_FOLDER not in content:
        return

    lines = content.split("\n")
    cleaned = []
    skip_section = False

    for line in lines:
        if line.strip() == "# Auto-Learning System":
            skip_section = True
            continue
        if skip_section:
            if line.strip().startswith(LEARNING_FOLDER):
                continue
            elif line.strip() == "":
                skip_section = False
                continue
            else:
                skip_section = False

        cleaned.append(line)

    # Remove linhas vazias extras no final
    result = "\n".join(cleaned).rstrip() + "\n"

    # Se o gitignore ficou vazio (so tinha nossas entradas), deleta
    if result.strip() == "":
        gitignore.unlink()
        print("  .gitignore removido (estava vazio)")
    else:
        gitignore.write_text(result, encoding="utf-8")
        print("  .gitignore limpo (entradas de auto-learning removidas)")


def remove_backups(project_dir: Path):
    """Remove os arquivos de backup do CLAUDE.md."""
    removed = 0
    for f in project_dir.glob("CLAUDE_backup_*.md"):
        f.unlink()
        removed += 1
    if removed:
        print(f"  {removed} arquivo(s) de backup removido(s)")


def remove_learning_folder(project_dir: Path):
    """Remove a pasta _auto_learning/ inteira."""
    base = project_dir / LEARNING_FOLDER
    if base.exists():
        shutil.rmtree(base)
        print(f"  Pasta {LEARNING_FOLDER}/ removida")
    else:
        print(f"  Pasta {LEARNING_FOLDER}/ nao encontrada")


def show_summary(project_dir: Path, zip_name: str):
    """Mostra resumo do que foi feito e onde encontrar os dados."""
    print()
    print("=" * 55)
    print(" DESINSTALACAO COMPLETA!")
    print("=" * 55)
    print()
    print(" O projeto voltou ao estado original.")
    print()
    print(" Seus aprendizados foram salvos em:")
    print(f"   {zip_name}")
    print()
    print(" O ZIP contem:")
    print("   +-- planos/ (todos os planos gerados)")
    print("   +-- docs/ (analises e documentacao)")
    print("   +-- regras/ (regras aprendidas)")
    print("   +-- db/learning.db (banco completo)")
    print("   +-- exports/ (exportacoes anteriores)")
    print()
    print(" Para consultar os planos depois:")
    print(f"   Descompacte {zip_name} em qualquer pasta")
    print()
    print("=" * 55)


def main():
    if len(sys.argv) < 2:
        print("Uso: python desinstalar.py <caminho-do-projeto>")
        print("Ex:  python desinstalar.py C:\\Users\\Meu\\projeto")
        print("Ex:  python desinstalar.py .")
        sys.exit(1)

    project_dir = Path(sys.argv[1]).resolve()

    if not project_dir.exists():
        print(f"ERRO: Diretorio nao existe: {project_dir}")
        sys.exit(1)

    base = project_dir / LEARNING_FOLDER
    if not base.exists():
        print(f"ERRO: Sistema nao esta instalado neste projeto ({LEARNING_FOLDER}/ nao encontrado)")
        sys.exit(1)

    project_name = project_dir.name

    print()
    print("=" * 55)
    print(" DESINSTALADOR — Sistema de Auto-Aprendizado")
    print("=" * 55)
    print(f" Projeto:  {project_name}")
    print(f" Caminho:  {project_dir}")
    print("=" * 55)
    print()

    # Mostra stats antes de remover
    try:
        sys.path.insert(0, str(base))
        from engine import LearningDB
        db = LearningDB(base / "db" / "learning.db")
        stats = db.get_stats()
        print(" Dados acumulados:")
        print(f"   Feedbacks: {stats['total_feedbacks']}")
        print(f"   Sucessos: {stats['total_sucessos']}")
        print(f"   Falhas: {stats['total_falhas']}")
        print(f"   Regras ativas: {stats['regras_ativas']}")
        print(f"   Ciclos completos: {stats['ciclos_completos']}")
        print()
    except Exception:
        pass

    resp = input(" Desinstalar? Dados serao exportados para ZIP antes. (s/N): ").strip().lower()
    if resp != "s":
        print(" Cancelado.")
        sys.exit(0)

    print()
    print("[1/5] Exportando dados para ZIP...")
    zip_name = export_before_removal(project_dir)

    print("[2/5] Restaurando CLAUDE.md original...")
    restore_claude_md(project_dir)

    print("[3/5] Limpando .gitignore...")
    clean_gitignore(project_dir)

    print("[4/5] Removendo backups do CLAUDE.md...")
    remove_backups(project_dir)

    print("[5/5] Removendo pasta _auto_learning/...")
    remove_learning_folder(project_dir)

    show_summary(project_dir, zip_name)


if __name__ == "__main__":
    main()
