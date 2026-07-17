#!/usr/bin/env python
"""Backfill de Order.status_event_date (Plano Definitivo — líquido fiel, liq-3).

Para os pedidos cancelled/refunded ANTIGOS (anteriores à captura no sync, liq-2),
busca cada pedido na API do ML e extrai a data do evento de pós-venda de
`payments[].date_last_modified` (mesmo campo/regra do sync). Popula
`status_event_date`. Escreve dado INERTE (nada lê essa coluna até liq-4, e só no
modo order_additive).

Uso (de dentro de backend/):
    DATABASE_URL="<dsn>" PYTHONPATH=. python scripts/backfill_status_event_date.py
    ... --dry-run     # só conta, não escreve
    ... --limit 5     # processa só N (teste)

Rate limit (1 req/seg) é do próprio MLClient. ~98 pedidos ≈ 2 min.
"""
import asyncio
import os
import sys

from sqlalchemy import select

# registra todos os mappers (relationships cruzam módulos)
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
from app.core.database import AsyncSessionLocal
from app.jobs.tasks_orders import _extract_status_event_date
from app.mercadolivre.client import MLClient, MLClientError
from app.vendas.models import Order

# Este script roda em UM processo (sem Redis local). O rate limiter distribuído via
# Redis (SETNX) é desnecessário aqui — substitui por um sleep local de 1s/req.
async def _local_rate_limit(self):
    await asyncio.sleep(1.0)

MLClient._rate_limit = _local_rate_limit


async def main():
    dry = "--dry-run" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    async with AsyncSessionLocal() as db:
        q = (
            select(Order)
            .where(
                Order.payment_status.in_(["cancelled", "refunded"]),
                Order.status_event_date.is_(None),
            )
            .order_by(Order.order_date.desc())
        )
        if limit:
            q = q.limit(limit)
        orders = (await db.execute(q)).scalars().all()
        print(f"Pedidos a backfillar (cancelled/refunded sem event_date): {len(orders)}")
        if dry:
            print("--dry-run: nada escrito.")
            return

        # cache de client por conta
        clients: dict = {}
        async def client_for(acc_id):
            if acc_id not in clients:
                acc = (
                    await db.execute(select(MLAccount).where(MLAccount.id == acc_id))
                ).scalar_one()
                clients[acc_id] = MLClient(acc.access_token, ml_account_id=str(acc.id))
            return clients[acc_id]

        found = notfound = errors = 0
        for i, o in enumerate(orders, 1):
            try:
                client = await client_for(o.ml_account_id)
                raw = await client._request("GET", f"/orders/{o.ml_order_id}")
                payments = raw.get("payments", []) or []
                evt = _extract_status_event_date(payments, o.payment_status)
                if evt is not None:
                    o.status_event_date = evt
                    found += 1
                else:
                    notfound += 1
                if i % 20 == 0:
                    await db.commit()
                    print(f"  [{i}/{len(orders)}] parcial: found={found} sem_data={notfound} erros={errors}")
            except (MLClientError, Exception) as e:
                errors += 1
                print(f"  ! {o.ml_order_id}: {type(e).__name__} {str(e)[:80]}")
        await db.commit()
        print(f"\nOK. atualizados={found}  sem_data_no_ML={notfound}  erros={errors}  total={len(orders)}")


if __name__ == "__main__":
    asyncio.run(main())
