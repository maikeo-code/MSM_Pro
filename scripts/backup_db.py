#!/usr/bin/env python
"""Backup lógico do Postgres de produção (Plano Definitivo, Bloco A / E117).

Substitui `pg_dump` (não instalado nesta máquina) usando o COPY BINÁRIO do próprio
Postgres via asyncpg — mesmos bytes/tipos que o pg_dump produziria por tabela, sem
conversão em Python. Gera um diretório datado com um arquivo `.bin` por tabela + um
`manifest.json` (contagem de linhas, versão do Alembic, ordem FK-safe de restore).

Uso:
    python scripts/backup_db.py                 # lê DATABASE_URL do .env da raiz
    DATABASE_URL=postgresql://... python scripts/backup_db.py

Restore: ver scripts/restore_db.py e docs/handoff/RESTORE.md.

NUNCA versionar os arquivos de backup — contêm dados de clientes (orders, users).
O diretório backups/ é gitignored.
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parent.parent
BACKUP_ROOT = ROOT / "backups"


def _load_dsn() -> str:
    """DSN postgresql:// (asyncpg) a partir de env var ou do .env da raiz."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        env_path = ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("DATABASE_URL"):
                    url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not url:
        sys.exit("ERRO: DATABASE_URL não encontrado (env var ou .env da raiz).")
    # asyncpg não aceita o dialeto SQLAlchemy (+asyncpg/+psycopg)
    return url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg://", "postgresql://"
    )


async def _tables_fk_ordered(conn) -> list[str]:
    """Tabelas em ordem topológica (dependências primeiro) para restore FK-safe."""
    rows = await conn.fetch(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema='public' AND table_type='BASE TABLE'
        """
    )
    tables = {r["table_name"] for r in rows}
    # arestas: child -> parent (child depende de parent)
    deps = await conn.fetch(
        """
        SELECT tc.table_name AS child, ccu.table_name AS parent
        FROM information_schema.table_constraints tc
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
        WHERE tc.constraint_type='FOREIGN KEY' AND tc.table_schema='public'
        """
    )
    parents: dict[str, set] = {t: set() for t in tables}
    for d in deps:
        if d["child"] in tables and d["parent"] in tables and d["child"] != d["parent"]:
            parents[d["child"]].add(d["parent"])
    ordered, seen = [], set()
    while len(ordered) < len(tables):
        progressed = False
        for t in sorted(tables):
            if t in seen:
                continue
            if parents[t] <= seen:  # todos os pais já saíram
                ordered.append(t)
                seen.add(t)
                progressed = True
        if not progressed:  # ciclo (auto-ref já filtrado): despeja o resto
            for t in sorted(tables - seen):
                ordered.append(t)
                seen.add(t)
            break
    return ordered


async def main():
    dsn = _load_dsn()
    ts = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S")
    out_dir = BACKUP_ROOT / f"backup_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = await asyncpg.connect(dsn, timeout=60)
    try:
        alembic_rev = await conn.fetchval("SELECT version_num FROM alembic_version")
        tables = await _tables_fk_ordered(conn)
        manifest = {
            "created_at": ts,
            "alembic_version": alembic_rev,
            "format": "postgres COPY binary (per table)",
            "restore_order": tables,
            "row_counts": {},
        }
        print(f"Backup -> {out_dir}")
        print(f"alembic_version: {alembic_rev}")
        print(f"{'tabela':40} linhas")
        print("-" * 52)
        total = 0
        for t in tables:
            count = await conn.fetchval(f'SELECT count(*) FROM "{t}"')
            dest = out_dir / f"{t}.bin"
            await conn.copy_from_query(f'SELECT * FROM "{t}"', output=str(dest), format="binary")
            manifest["row_counts"][t] = count
            total += count
            print(f"{t:40} {count:>8}")
        print("-" * 52)
        print(f"{'TOTAL':40} {total:>8}")
        (out_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\nOK. manifest.json escrito. {len(tables)} tabelas, {total} linhas.")
        print(f"Restore: python scripts/restore_db.py {out_dir.name}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
