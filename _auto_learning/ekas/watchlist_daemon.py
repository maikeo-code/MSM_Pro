"""
EKAS Watchlist Daemon v1.0
Verifica a watchlist periodicamente e executa coleta + processamento.

Modos de execucao:
  1. Unica vez:     python watchlist_daemon.py check
  2. Loop continuo: python watchlist_daemon.py loop --interval 3600
  3. Status:        python watchlist_daemon.py status
"""
import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime

# Load .env
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().strip().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from ekas_engine import EkasDB
from cycle_bridge import EkasCycleBridge

# Logging setup
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "watchlist_daemon.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ekas.watchlist")


def check_and_process(project_id: str = None, process_limit: int = 10):
    """Check watchlist, collect new items, and process them."""
    db = EkasDB()

    # Get project context
    context = ""
    if project_id:
        project = db.get_project(project_id)
        if project:
            context = f"{project['name']} - {project.get('description', '')}"

    bridge = EkasCycleBridge(project_id=project_id, project_context=context)

    # Check due watches
    due = db.get_due_watches()
    logger.info(f"Watches pendentes: {len(due)}")

    if not due:
        logger.info("Nenhum watch pendente. Verificando fontes RAW...")

    # Run collection for due watches
    if due:
        logger.info("Iniciando fase de coleta...")
        collection_result = bridge.run_collection_phase()
        logger.info(f"Coleta: {collection_result['watches_checked']} watches, "
                    f"{collection_result['items_new']} novos")
        if collection_result.get("errors"):
            for err in collection_result["errors"]:
                logger.warning(f"  Erro coleta: {err}")

    # Process RAW sources
    raw_count = len(db.get_sources_by_status("RAW", limit=100))
    if raw_count > 0:
        logger.info(f"Processando {min(raw_count, process_limit)} fontes RAW...")
        proc_result = bridge.run_processing_phase(limit=process_limit)
        logger.info(f"Processamento: {proc_result['processed']} OK, "
                    f"{proc_result['failed']} falhas, "
                    f"{proc_result['tokens_used']} tokens")
        if proc_result.get("errors"):
            for err in proc_result["errors"]:
                logger.warning(f"  Erro proc: {err}")
    else:
        logger.info("Nenhuma fonte RAW para processar.")

    # Run strategy
    logger.info("Atualizando estrategia...")
    strategy = bridge.run_strategy_phase()
    logger.info(f"Roadmap: {strategy['roadmap_items']} sugestoes")

    # Summary
    stats = db.get_stats()
    logger.info(f"Status EKAS: {stats['sources_total']} fontes, "
               f"{stats['competitors']} concorrentes, "
               f"{stats['features']} features, "
               f"{stats['opportunities_total']} oportunidades")

    return {"collection": due, "raw_remaining": raw_count, "stats": stats}


def run_loop(interval_seconds: int = 3600, project_id: str = None):
    """Run watchlist check in a continuous loop."""
    logger.info(f"Daemon iniciado. Intervalo: {interval_seconds}s. Projeto: {project_id or 'todos'}")

    while True:
        try:
            logger.info(f"--- Verificacao {datetime.now().strftime('%Y-%m-%d %H:%M')} ---")
            check_and_process(project_id)
        except KeyboardInterrupt:
            logger.info("Daemon parado pelo usuario.")
            break
        except Exception as e:
            logger.error(f"Erro no ciclo: {e}")

        logger.info(f"Proxima verificacao em {interval_seconds}s...")
        try:
            time.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("Daemon parado pelo usuario.")
            break


def show_status(project_id: str = None):
    """Show current EKAS status."""
    db = EkasDB()
    stats = db.get_stats()
    due = db.get_due_watches()
    raw = db.get_sources_by_status("RAW", limit=5)

    print("=== EKAS Watchlist Status ===")
    print(f"Projetos: {stats['projects']}")
    print(f"Fontes: {stats['sources_total']} (RAW: {stats['sources_raw']}, Processadas: {stats['sources_processed']})")
    print(f"Concorrentes: {stats['competitors']}")
    print(f"Features: {stats['features']}")
    print(f"Oportunidades: {stats['opportunities_total']}")
    print(f"Watches ativos: {stats['watchlist_active']}")
    print(f"Watches pendentes: {len(due)}")
    if due:
        print("\nWatches pendentes:")
        for w in due[:5]:
            print(f"  [{w['watch_type']}] {w['target']} (ultimo: {w.get('last_checked', 'nunca')})")
    if raw:
        print(f"\nFontes RAW aguardando processamento: {len(raw)}")
        for s in raw[:3]:
            print(f"  [{s['source_type']}] {s['title'][:50]}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="EKAS Watchlist Daemon")
    parser.add_argument("command", choices=["check", "loop", "status"],
                       help="check=unica vez, loop=continuo, status=ver estado")
    parser.add_argument("--interval", type=int, default=3600,
                       help="Intervalo em segundos para o modo loop (padrao: 3600)")
    parser.add_argument("--project", type=str, default=None,
                       help="ID do projeto (ex: msm_pro)")
    parser.add_argument("--limit", type=int, default=10,
                       help="Max fontes para processar por ciclo")

    args = parser.parse_args()

    if args.command == "check":
        check_and_process(args.project, args.limit)
    elif args.command == "loop":
        run_loop(args.interval, args.project)
    elif args.command == "status":
        show_status(args.project)
