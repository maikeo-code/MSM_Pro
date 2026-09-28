"""
sync_all_listings — descoberta automática de anúncios novos.

Incidente de 25/09/2026: sync_listings_from_ml (que importa anúncios novos e atualiza
active/paused) só rodava pelo botão POST /listings/sync. O último registro era de 19/07;
anúncios criados depois nunca entraram no cadastro (4 MLB7… que ranqueavam no top 30 da busca
não existiam no MSM_Pro). A task passa a rodar sozinha, todo dia, antes do sync de snapshots.
"""
import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-for-unit-tests!!")

from app.core.celery_app import celery_app  # noqa: E402
from app.jobs import tasks as tasks_module  # noqa: E402
from app.jobs import tasks_listings  # noqa: E402


def test_task_registrada():
    assert "app.jobs.tasks.sync_all_listings" in celery_app.tasks


def test_agendada_no_beat_antes_dos_snapshots():
    agenda = {v["task"]: v["schedule"] for v in celery_app.conf.beat_schedule.values()}
    assert "app.jobs.tasks.sync_all_listings" in agenda
    h_list = min(agenda["app.jobs.tasks.sync_all_listings"].hour)
    h_snap = min(agenda["app.jobs.tasks.sync_all_snapshots"].hour)
    assert h_list < h_snap  # cadastro atualizado antes das métricas do dia


def test_limite_de_tempo_maior_que_o_padrao():
    t = celery_app.tasks["app.jobs.tasks.sync_all_listings"]
    assert (t.soft_time_limit or 0) >= 1200  # ~150 anúncios × 2-3 chamadas ao ML


@pytest.mark.asyncio
async def test_falha_de_um_usuario_nao_derruba_os_outros():
    u1, u2 = uuid4(), uuid4()
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(all=lambda: [(u1,), (u2,)]))
    db.rollback = AsyncMock()
    sessao = MagicMock()
    sessao.__aenter__ = AsyncMock(return_value=db)
    sessao.__aexit__ = AsyncMock(return_value=False)

    chamados = []

    async def fake_sync(_db, uid):
        chamados.append(uid)
        if uid == u1:
            raise RuntimeError("ML fora")
        return {"created": 3, "updated": 10, "errors": []}

    with patch.object(tasks_listings, "AsyncSessionLocal", return_value=sessao), \
         patch.object(tasks_listings, "_create_sync_log", AsyncMock(return_value=MagicMock())), \
         patch.object(tasks_listings, "_finish_sync_log", AsyncMock()) as fim, \
         patch("app.vendas.service_sync.sync_listings_from_ml", side_effect=fake_sync):
        r = await tasks_listings._sync_all_listings_async()

    assert chamados == [u1, u2]
    assert (r["users"], r["created"], r["updated"], r["errors"]) == (2, 3, 10, 1)
    assert r["success"] is False
    db.rollback.assert_awaited_once()
    assert fim.await_args.kwargs["failed"] == 1


def test_disponivel_no_gatilho_manual():
    import inspect

    from app.auth import router

    assert '"sync_all_listings"' in inspect.getsource(router.trigger_celery_task)
    assert hasattr(tasks_module, "sync_all_listings")
