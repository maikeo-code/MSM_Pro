#!/usr/bin/env python
"""Restore de um backup gerado por scripts/backup_db.py (Bloco A / E117).

Carrega os arquivos COPY binários de volta num Postgres ALVO. O schema tem que já
existir (rode `alembic upgrade head` no alvo antes). Ordem FK-safe vem do manifest;
FKs são desabilitadas durante a carga (session_replication_role=replica).

Uso:
    DATABASE_URL=<dsn_do_ALVO> python scripts/restore_db.py backup_YYYYMMDD_HHMMSS
    python scripts/restore_db.py <dir> --verify-only   # só confere contagens, não escreve

⚠️ SEGURANÇA: por padrão recusa restaurar sobre o MESMO host do backup de produção
sem a flag --force. Restore normal é para STAGING ou banco descartável.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parent.parent
BACKUP_ROOT = ROOT / "backups"


def _load_dsn() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        env_path = ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("DATABASE_URL"):
                    url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not url:
        sys.exit("ERRO: DATABASE_URL do ALVO não encontrado.")
    return url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg://", "postgresql://"
    )


async def main():
    args = [a for a in sys.argv[1:]]
    verify_only = "--verify-only" in args
    force = "--force" in args
    positional = [a for a in args if not a.startswith("--")]
    if not positional:
        sys.exit("Uso: python scripts/restore_db.py <dir_backup> [--verify-only] [--force]")
    backup_dir = BACKUP_ROOT / positional[0]
    if not backup_dir.exists():
        backup_dir = Path(positional[0])
    manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    tables = manifest["restore_order"]

    dsn = _load_dsn()
    conn = await asyncpg.connect(dsn, timeout=60)
    try:
        if verify_only:
            print(f"{'tabela':40} {'backup':>8} {'alvo':>8}")
            print("-" * 60)
            ok = True
            for t in tables:
                alvo = await conn.fetchval(f'SELECT count(*) FROM "{t}"')
                bkp = manifest["row_counts"][t]
                flag = "" if alvo == bkp else "  <-- DIVERGE"
                if alvo != bkp:
                    ok = False
                print(f"{t:40} {bkp:>8} {alvo:>8}{flag}")
            print("-" * 60)
            print("OK: contagens idênticas." if ok else "ATENÇÃO: há divergências.")
            return

        host = conn.get_settings().server_version  # apenas p/ garantir conexão viva
        server_addr = dsn.split("@", 1)[1].split("/", 1)[0] if "@" in dsn else "?"
        if "rlwy.net" in server_addr and not force:
            sys.exit(
                f"RECUSADO: alvo parece produção ({server_addr}). Restore é p/ staging/"
                "descartável. Use --force só se tiver CERTEZA (e backup fresco)."
            )
        print(f"Restore -> {server_addr} (pg {host})")
        # desabilita FKs durante a carga
        await conn.execute("SET session_replication_role = replica")
        total = 0
        for t in tables:
            await conn.execute(f'TRUNCATE TABLE "{t}" CASCADE')
        for t in tables:
            src = backup_dir / f"{t}.bin"
            await conn.copy_to_table(t, source=str(src), format="binary")
            n = await conn.fetchval(f'SELECT count(*) FROM "{t}"')
            total += n
            print(f"  {t:40} {n:>8}")
        await conn.execute("SET session_replication_role = DEFAULT")
        print(f"OK. {total} linhas restauradas em {len(tables)} tabelas.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
