"""POST /listings/backfill-snapshots não pode usar /visits/items (bulk).

O bulk do ML ignora date_from/date_to e devolve visitas LIFETIME (2 anos). Passado como
visits_override, gravava o acumulado como "visitas do dia". Cada task deve buscar o dia
exato via time_window (get_item_visits_on_day), o que só acontece com visits_override=None.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.vendas.router import backfill_snapshots


@pytest.mark.asyncio
async def test_backfill_snapshots_nao_usa_visitas_bulk():
    conta = uuid4()
    rows = [
        SimpleNamespace(id=uuid4(), mlb_id="MLB5188690977", ml_account_id=conta),
        SimpleNamespace(id=uuid4(), mlb_id="4577022961", ml_account_id=conta),
    ]
    result = MagicMock()
    result.fetchall.return_value = rows
    result.scalar_one_or_none.return_value = SimpleNamespace(
        id=conta, nickname="MSMPRIME", access_token="tok"
    )
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    client = MagicMock()
    client.get_items_visits_bulk = AsyncMock(return_value={"MLB5188690977": 90000})
    client_cm = MagicMock()
    client_cm.__aenter__ = AsyncMock(return_value=client)
    client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.mercadolivre.client.MLClient", return_value=client_cm), patch(
        "app.jobs.tasks.sync_listing_snapshot"
    ) as task:
        out = await backfill_snapshots(
            current_user=SimpleNamespace(id=uuid4()), db=db, date_iso="2026-09-14"
        )

    client.get_items_visits_bulk.assert_not_called()
    assert task.delay.call_count == 2
    for call in task.delay.call_args_list:
        assert call.kwargs.get("visits_override") is None
        assert call.kwargs["snapshot_date_iso"] == "2026-09-14"
    assert out["dispatched"] == 2


@pytest.mark.asyncio
async def test_backfill_snapshots_data_invalida():
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        await backfill_snapshots(
            current_user=SimpleNamespace(id=uuid4()), db=MagicMock(), date_iso="14/09/2026"
        )
