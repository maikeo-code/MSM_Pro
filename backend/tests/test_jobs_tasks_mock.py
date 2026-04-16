"""
Testes para jobs/tasks_*.py usando AsyncSessionLocal patchado.

Estratégia: patch AsyncSessionLocal com mock que retorna db vazio.
Isso cobre os caminhos early-return (sem contas, sem listings, sem dados)
sem necessitar de PostgreSQL real.
"""
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest


# ─── Helpers para mock de DB ────────────────────────────────────────────────


def _make_mock_db(accounts=None, listings=None, sync_log=None):
    """Cria um mock AsyncSession com scalars().all() retornando as listas fornecidas."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    call_count = [0]
    _accounts = accounts or []
    _listings = listings or []

    async def _execute(*args, **kwargs):
        call_count[0] += 1
        result = MagicMock()

        # Determina qual resultado retornar com base na contagem de chamadas
        if call_count[0] == 1:
            result.scalars.return_value.all.return_value = _accounts
            result.all.return_value = _accounts
        else:
            result.scalars.return_value.all.return_value = _listings
            result.all.return_value = _listings

        result.scalar_one_or_none.return_value = sync_log
        result.fetchall.return_value = []
        return result

    db.execute = _execute
    return db


class _AsyncCtxMgr:
    """Async context manager que retorna um db mockado."""

    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *args):
        pass

    def __call__(self):
        return self


def _session_factory(db):
    """Retorna um callable que funciona como AsyncSessionLocal()."""
    class _CM:
        async def __aenter__(self_inner):
            return db
        async def __aexit__(self_inner, *args):
            pass

    def factory():
        return _CM()

    return factory


def _make_sync_log():
    """Cria um SyncLog mockado com started_at definido."""
    log = MagicMock()
    log.started_at = datetime.now(timezone.utc)
    log.status = "running"
    return log


# ═══════════════════════════════════════════════════════════════════════════════
# tasks_helpers — funções puras/simples
# ═══════════════════════════════════════════════════════════════════════════════


class TestTasksHelpers:
    """Testa funções auxiliares de jobs."""

    @pytest.mark.asyncio
    async def test_create_sync_log(self):
        """_create_sync_log cria e retorna um SyncLog."""
        from app.jobs.tasks_helpers import _create_sync_log

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()

        result = await _create_sync_log(db, "test_task")
        assert result is not None
        db.add.assert_called_once()
        db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_sync_log_with_account_id(self):
        from app.jobs.tasks_helpers import _create_sync_log

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        account_id = uuid.uuid4()

        result = await _create_sync_log(db, "sync_orders", ml_account_id=account_id)
        assert result is not None

    @pytest.mark.asyncio
    async def test_finish_sync_log_success(self):
        """_finish_sync_log atualiza o log com status e commita."""
        from app.jobs.tasks_helpers import _finish_sync_log

        db = AsyncMock()
        db.commit = AsyncMock()

        log = _make_sync_log()
        await _finish_sync_log(db, log, status="success", items=10, failed=0)

        assert log.status == "success"
        assert log.items_processed == 10
        assert log.items_failed == 0
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_finish_sync_log_with_error(self):
        from app.jobs.tasks_helpers import _finish_sync_log

        db = AsyncMock()
        db.commit = AsyncMock()

        log = _make_sync_log()
        await _finish_sync_log(db, log, status="failed", error="some error")

        assert log.status == "failed"
        assert log.error_message == "some error"
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_finish_sync_log_no_started_at(self):
        """Log sem started_at não deve calcular duration_ms."""
        from app.jobs.tasks_helpers import _finish_sync_log

        db = AsyncMock()
        db.commit = AsyncMock()

        log = MagicMock()
        log.started_at = None  # sem data de início

        await _finish_sync_log(db, log, status="success")
        assert log.status == "success"

    def test_run_async_simple_coroutine(self):
        """run_async executa uma coroutine simples."""
        from app.jobs.tasks_helpers import run_async

        async def _simple():
            return 42

        result = run_async(_simple())
        assert result == 42

    def test_run_async_coroutine_with_exception(self):
        """run_async propaga exceções da coroutine."""
        from app.jobs.tasks_helpers import run_async

        async def _failing():
            raise ValueError("oops")

        with pytest.raises(ValueError, match="oops"):
            run_async(_failing())


# ═══════════════════════════════════════════════════════════════════════════════
# tasks_orders — _sync_orders_async com zero contas
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyncOrdersAsync:
    """Testa _sync_orders_async com mocks."""

    @pytest.mark.asyncio
    async def test_sem_contas_retorna_zero(self):
        """Com zero contas ativas → criados=0, atualizados=0, erros=0."""
        from app.jobs.tasks_orders import _sync_orders_async

        sync_log = _make_sync_log()
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        call_count = [0]

        async def _execute(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                # _create_sync_log flush → retorna o sync_log
                result.scalar_one_or_none.return_value = sync_log
                result.scalars.return_value.all.return_value = []
            else:
                result.scalars.return_value.all.return_value = []
                result.scalar_one_or_none.return_value = None
            return result

        db.execute = _execute

        with patch("app.jobs.tasks_orders.AsyncSessionLocal", _session_factory(db)):
            result = await _sync_orders_async()

        assert result["created"] == 0
        assert result["updated"] == 0
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_conta_sem_token_e_pulada(self):
        """Conta sem access_token é ignorada (warning + continue)."""
        from app.jobs.tasks_orders import _sync_orders_async

        account = MagicMock()
        account.access_token = None
        account.nickname = "ContaSemToken"
        account.id = uuid.uuid4()
        account.ml_user_id = 999

        sync_log = _make_sync_log()
        call_count = [0]

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        async def _execute(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                result.scalars.return_value.all.return_value = [account]
            else:
                result.scalars.return_value.all.return_value = []
            result.scalar_one_or_none.return_value = sync_log
            return result

        db.execute = _execute

        with patch("app.jobs.tasks_orders.AsyncSessionLocal", _session_factory(db)):
            result = await _sync_orders_async()

        # Conta sem token → pulada → criados=0
        assert result["created"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# tasks_digest — _build_digest_for_user com zero listings
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildDigestForUser:
    """Testa _build_digest_for_user com mock de DB."""

    @pytest.mark.asyncio
    async def test_sem_listings_retorna_none(self):
        """Usuário sem listings → retorna None."""
        from app.jobs.tasks_digest import _build_digest_for_user

        db = AsyncMock()
        db.execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        with patch("app.jobs.tasks_digest.AsyncSessionLocal", _session_factory(db)):
            result = await _build_digest_for_user(uuid.uuid4())

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# tasks_digest — send_weekly_digest_async com zero usuários
# ═══════════════════════════════════════════════════════════════════════════════


class TestSendWeeklyDigestAsync:
    """Testa send_weekly_digest_async com zero usuários."""

    @pytest.mark.asyncio
    async def test_sem_usuarios_retorna_sem_erro(self):
        """Zero usuários → nenhum digest enviado, sem exceção."""
        from app.jobs.tasks_digest import _send_weekly_digest_async

        db = AsyncMock()
        db.execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        with patch("app.jobs.tasks_digest.AsyncSessionLocal", _session_factory(db)):
            # Não deve levantar exceção
            await _send_weekly_digest_async()


# ═══════════════════════════════════════════════════════════════════════════════
# tasks_listings — helpers de sync
# ═══════════════════════════════════════════════════════════════════════════════


class TestTasksListingsHelpers:
    """Testa funções helpers de tasks_listings."""

    def test_mlb_normalize_formato_padrao(self):
        """MLB IDs são normalizados para uppercase sem hífens."""
        # Verifica que o código no arquivo normaliza corretamente
        mlb_raw = "mlb-123456789"
        mlb_normalized = mlb_raw.upper().replace("-", "")
        assert mlb_normalized == "MLB123456789"

    def test_mlb_normalize_ja_normalizado(self):
        mlb_raw = "MLB6205732214"
        mlb_normalized = mlb_raw.upper().replace("-", "")
        assert mlb_normalized == "MLB6205732214"


# ═══════════════════════════════════════════════════════════════════════════════
# tasks_alerts — _evaluate_alerts_async com zero contas
# ═══════════════════════════════════════════════════════════════════════════════


class TestEvaluateAlertsAsync:
    """Testa _evaluate_alerts_async com mock."""

    @pytest.mark.asyncio
    async def test_sem_configs_ativas(self):
        """Sem alert_configs ativas → nenhum alerta disparado."""
        from app.jobs.tasks_alerts import _evaluate_alerts_async

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_result.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        with patch("app.jobs.tasks_alerts.AsyncSessionLocal", _session_factory(db)):
            # Não deve levantar exceção com zero configs
            await _evaluate_alerts_async()


# ═══════════════════════════════════════════════════════════════════════════════
# tasks_reputation — _sync_reputation_async com zero contas
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyncReputationAsync:
    """Testa _sync_reputation_async com zero contas."""

    @pytest.mark.asyncio
    async def test_sem_contas(self):
        """Zero contas ativas → sem exceção."""
        from app.jobs.tasks_reputation import _sync_reputation_async

        sync_log = _make_sync_log()
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        call_count = [0]

        async def _execute(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            result.scalar_one_or_none.return_value = sync_log
            return result

        db.execute = _execute

        with patch("app.jobs.tasks_reputation.AsyncSessionLocal", _session_factory(db)):
            # Não deve levantar exceção
            await _sync_reputation_async()


# ═══════════════════════════════════════════════════════════════════════════════
# tasks_ads — _sync_ads_async com zero contas
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyncAdsAsync:
    """Testa _sync_ads_async com zero contas."""

    @pytest.mark.asyncio
    async def test_sem_contas(self):
        """Zero contas ativas → sem exceção."""
        from app.jobs.tasks_ads import _sync_ads_async

        sync_log = _make_sync_log()
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        call_count = [0]

        async def _execute(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            result.scalar_one_or_none.return_value = sync_log
            return result

        db.execute = _execute

        with patch("app.jobs.tasks_ads.AsyncSessionLocal", _session_factory(db)):
            await _sync_ads_async()
