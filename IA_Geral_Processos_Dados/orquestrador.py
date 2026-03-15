"""
============================================================
ORQUESTRADOR CENTRAL — IA Geral Processos e Dados
============================================================
Gerencia todos os projetos registrados:
- Sincroniza regras globais com instancias locais
- Coleta metricas de cada projeto
- Promove regras locais a globais
- Instala auto-learning em novos projetos

Uso:
    python orquestrador.py status          # status de todos os projetos
    python orquestrador.py sync            # sincroniza regras
    python orquestrador.py install <path>  # instala em novo projeto
    python orquestrador.py report          # gera relatorio cruzado
============================================================
"""

import json
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
PROJETOS_DIR = BASE_DIR / "projetos"
REGRAS_GLOBAIS_DIR = BASE_DIR / "regras_globais"
KIT_DIR = BASE_DIR / "kit_instalador"
DOCS_DIR = BASE_DIR / "docs"


def carregar_projetos() -> list[dict]:
    """Carrega config.json de todos os projetos registrados."""
    projetos = []
    for pasta in sorted(PROJETOS_DIR.iterdir()):
        config_file = pasta / "config.json"
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                config["_pasta"] = pasta.name
                projetos.append(config)
    return projetos


def cmd_status():
    """Mostra status de todos os projetos."""
    projetos = carregar_projetos()

    print()
    print("=" * 65)
    print(" IA GERAL — STATUS DOS PROJETOS")
    print("=" * 65)
    print()

    # Regras globais
    regras = list(REGRAS_GLOBAIS_DIR.glob("regra_*.md"))
    print(f"  Regras globais ativas: {len(regras)}")
    print()

    # Tabela de projetos
    print(f"  {'Projeto':<20} {'Status':<12} {'Learning':<12} {'Ciclos':<8} {'Regras':<8}")
    print(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*8} {'-'*8}")

    for p in projetos:
        nome = p.get("nome", p["_pasta"])
        status = p.get("status", "?")
        learning = "Sim" if p.get("auto_learning_instalado") else "Nao"
        ciclos = p.get("ciclos_completados", 0)
        regras_count = p.get("regras_aprendidas", 0)
        print(f"  {nome:<20} {status:<12} {learning:<12} {ciclos:<8} {regras_count:<8}")

    print()
    print("=" * 65)


def cmd_sync():
    """Sincroniza regras globais com projetos ativos."""
    projetos = carregar_projetos()
    regras_globais = list(REGRAS_GLOBAIS_DIR.glob("regra_*.md"))

    print()
    print("=" * 65)
    print(" SINCRONIZACAO DE REGRAS")
    print("=" * 65)
    print()
    print(f"  Regras globais: {len(regras_globais)}")
    print()

    for p in projetos:
        nome = p.get("nome", p["_pasta"])
        caminho = p.get("caminho_local", "")

        if not caminho or not p.get("auto_learning_instalado"):
            print(f"  [{nome}] Pulado (sem caminho ou sem auto-learning)")
            continue

        projeto_path = Path(caminho)
        regras_dir = projeto_path / "_auto_learning" / "regras"

        if not regras_dir.exists():
            print(f"  [{nome}] Pasta de regras nao encontrada em {regras_dir}")
            continue

        copiadas = 0
        for regra in regras_globais:
            destino = regras_dir / regra.name
            if not destino.exists():
                shutil.copy2(regra, destino)
                copiadas += 1

        print(f"  [{nome}] {copiadas} regras novas sincronizadas")

    print()
    print("  Sincronizacao concluida.")
    print("=" * 65)


def cmd_install(projeto_path: str):
    """Instala auto-learning em um novo projeto."""
    instalador = KIT_DIR / "instalar.py"
    if not instalador.exists():
        print("ERRO: instalar.py nao encontrado no kit_instalador/")
        sys.exit(1)

    os.system(f'python "{instalador}" "{projeto_path}"')

    # Pergunta se quer registrar
    nome = Path(projeto_path).name
    pasta_projeto = PROJETOS_DIR / nome.lower().replace(" ", "_")
    pasta_projeto.mkdir(parents=True, exist_ok=True)

    config = {
        "nome": nome,
        "descricao": "",
        "status": "ativo",
        "caminho_local": str(Path(projeto_path).resolve()),
        "repositorio": "",
        "stack": "",
        "deploy": "",
        "auto_learning_instalado": True,
        "ciclos_completados": 0,
        "regras_aprendidas": 0,
        "modulos": [],
        "apis_externas": [],
        "data_registro": datetime.now().strftime("%Y-%m-%d"),
    }

    config_file = pasta_projeto / "config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"\nProjeto registrado em: projetos/{pasta_projeto.name}/config.json")


def cmd_report():
    """Gera relatorio cruzado de todos os projetos."""
    projetos = carregar_projetos()
    regras = list(REGRAS_GLOBAIS_DIR.glob("regra_*.md"))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    report = f"""# Relatorio Cruzado — IA Geral
Data: {timestamp}

## Resumo
- Projetos registrados: {len(projetos)}
- Projetos ativos: {sum(1 for p in projetos if p.get('status') == 'ativo')}
- Regras globais: {len(regras)}
- Total ciclos (todos projetos): {sum(p.get('ciclos_completados', 0) for p in projetos)}

## Por Projeto
"""
    for p in projetos:
        nome = p.get("nome", p["_pasta"])
        report += f"""
### {nome}
- Status: {p.get('status', '?')}
- Auto-learning: {'Sim' if p.get('auto_learning_instalado') else 'Nao'}
- Ciclos: {p.get('ciclos_completados', 0)}
- Regras locais: {p.get('regras_aprendidas', 0)}
- Stack: {p.get('stack', 'N/A')}
- Modulos: {', '.join(p.get('modulos', [])) or 'Nenhum'}
"""

    report += f"""
## Regras Globais ({len(regras)})
"""
    for r in sorted(regras):
        report += f"- {r.stem}\n"

    report_file = DOCS_DIR / f"relatorio_{datetime.now().strftime('%Y%m%d')}.md"
    report_file.write_text(report.strip(), encoding="utf-8")
    print(f"Relatorio salvo em: {report_file}")


def main():
    if len(sys.argv) < 2:
        print("Uso: python orquestrador.py <comando> [args]")
        print("Comandos: status, sync, install <path>, report")
        sys.exit(1)

    comando = sys.argv[1]

    if comando == "status":
        cmd_status()
    elif comando == "sync":
        cmd_sync()
    elif comando == "install":
        if len(sys.argv) < 3:
            print("Uso: python orquestrador.py install <caminho-do-projeto>")
            sys.exit(1)
        cmd_install(sys.argv[2])
    elif comando == "report":
        cmd_report()
    else:
        print(f"Comando desconhecido: {comando}")
        sys.exit(1)


if __name__ == "__main__":
    main()
