#!/usr/bin/env python
"""Modo sombra da troca de fonte de vendas (Plano Definitivo, Bloco A / E120).

Antes de virar a chave da Fase 4 (E52), rode este script por alguns dias para
MEDIR a diferença entre os dois modos SEM mudar nada exibido no app:
  - legacy_max     (atual): max(snapshot, order)
  - order_additive (futuro): Order como fonte aditiva única

Para um dia (default D-1 em BRT) e cada conta ML, calcula os KPIs nos dois modos e
imprime o diff de vendas/pedidos/receita, além de uma linha JSON estruturada por
conta (para agregação em log). A virada só deve acontecer quando todo diff estiver
zerado ou explicado (dias legados sem order, etc.).

Uso (rodar de dentro de backend/, com o banco de produção):
    cd backend
    DATABASE_URL="<dsn_de_prod>" PYTHONPATH=. python ../scripts/shadow_diff.py            # D-1
    DATABASE_URL="<dsn_de_prod>" PYTHONPATH=. python ../scripts/shadow_diff.py 2026-07-11  # dia X

Achado da 1ª rodada (2026-07-15, dias 07-11 e 07-14): vendas/pedidos/receita_total
BATEM entre os modos → a virada legacy_max→order_additive, sozinha, NÃO muda a
contagem quando snapshot e Order já concordam. O que order_additive garante é a
ADITIVIDADE (Σdias==janela, ver test_metrics_source_flag::test_order_additive_e_aditivo).
A única divergência observada é `vendas_concluidas` (fórmula subtrai cancelados que
no modo Order já estão fora da receita) — é a etapa E59, a reconciliar contra o painel.
"""
import asyncio
import json
import sys
from datetime import date, datetime, timedelta

from sqlalchemy import select

# registra TODOS os mappers (relationships cruzam módulos: User->Product, etc.)
import app.auth.models  # noqa: F401
import app.produtos.models  # noqa: F401
import app.vendas.models  # noqa: F401
import app.concorrencia.models  # noqa: F401
import app.alertas.models  # noqa: F401
import app.reputacao.models  # noqa: F401
import app.ads.models  # noqa: F401
import app.intel.models  # noqa: F401
import app.financeiro.models  # noqa: F401
import app.atendimento.models  # noqa: F401
from app.auth.models import MLAccount
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.vendas.metrics import BRT, aggregate_metrics
from app.vendas.models import Listing


async def _mode(db, listing_ids, dia, mode):
    settings.metrics_source = mode
    return await aggregate_metrics(db, listing_ids, dia, dia)


async def main():
    if len(sys.argv) > 1:
        dia = date.fromisoformat(sys.argv[1])
    else:
        dia = (datetime.now(BRT) - timedelta(days=1)).date()

    original = settings.metrics_source
    piores = 0
    try:
        async with AsyncSessionLocal() as db:
            accounts = (await db.execute(select(MLAccount))).scalars().all()
            print(f"MODO SOMBRA — dia {dia} (BRT) — legacy_max vs order_additive\n")
            for acc in accounts:
                listing_ids = (
                    await db.execute(
                        select(Listing.id).where(Listing.ml_account_id == acc.id)
                    )
                ).scalars().all()
                if not listing_ids:
                    continue
                legacy = await _mode(db, listing_ids, dia, "legacy_max")
                additive = await _mode(db, listing_ids, dia, "order_additive")
                diff = {
                    campo: round(additive[campo] - legacy[campo], 2)
                    for campo in ("vendas", "pedidos", "receita_total", "vendas_concluidas")
                }
                mudou = any(v != 0 for v in diff.values())
                if mudou:
                    piores += 1
                print(f"[{acc.nickname} / {acc.ml_user_id}]")
                print(f"  legacy_max     : vendas={legacy['vendas']} pedidos={legacy['pedidos']} receita={legacy['receita_total']:.2f}")
                print(f"  order_additive : vendas={additive['vendas']} pedidos={additive['pedidos']} receita={additive['receita_total']:.2f}")
                print(f"  DIFF (add-leg) : {diff}  {'<-- DIVERGE' if mudou else '(igual)'}")
                # linha estruturada p/ agregação em log/arquivo
                print("  " + json.dumps({
                    "shadow_diff": True, "day": str(dia), "account": acc.ml_user_id,
                    "nickname": acc.nickname, **{f"diff_{k}": v for k, v in diff.items()},
                }, ensure_ascii=False))
                print()
            print(f"Contas com diferença: {piores}/{len(accounts)}. "
                  f"Virar a chave (E52) só quando todas estiverem em 0 ou explicadas.")
    finally:
        settings.metrics_source = original


if __name__ == "__main__":
    asyncio.run(main())
