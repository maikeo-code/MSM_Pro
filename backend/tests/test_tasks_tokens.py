"""
Testes unitários para tasks_tokens.py — renovação de tokens OAuth ML.

Cobre:
  - refresh_expired_tokens renova tokens próximos de expirar
  - Campos tracking atualizados no sucesso (last_token_refresh_at, failures=0, needs_reauth=False)
  - Campos tracking atualizados na falha (failures incrementa, needs_reauth=True após 5 falhas)
  - Lock distribuído previne race condition
  - Backfill automático dispara quando token ficou offline >24h
  - Backfill usa old_expires_at (não o novo) para calcular gap
  - Notificação criada quando token expira e refresh falha
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-for-unit-tests!!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


# ============================================================================
# Helpers compartilhados
# ============================================================================


def _make_account(
    account_id="account-uuid-1",
    nickname="MSM_PRIME",
    user_id="user-uuid-1",
    ml_user_id="2050442871",
    access_token="old_access_token",
    refresh_token="old_refresh_token",
    token_expires_at=None,
    token_refresh_failures=0,
    needs_reauth=False,
    is_active=True,
):
    """Cria um mock de MLAccount com os campos de tracking."""
    account = MagicMock()
    account.id = account_id
    account.nickname = nickname
    account.user_id = user_id
    account.ml_user_id = ml_user_id
    account.access_token = access_token
    account.refresh_token = refresh_token
    # Expira daqui a 1h (dentro da janela de renovação de 3h)
    account.token_expires_at = token_expires_at or (
        datetime.now(timezone.utc) + timedelta(hours=1)
    )
    account.token_refresh_failures = token_refresh_failures
    account.needs_reauth = needs_reauth
    account.last_token_refresh_at = None
    account.is_active = is_active
    return account


def _make_db_session_with_accounts(accounts):
    """Cria mock de AsyncSession que retorna os accounts fornecidos."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = accounts
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    return mock_db


# ============================================================================
# Teste 13: refresh_expired_tokens renova tokens próximos de expirar
# ============================================================================


class TestRefreshExpiredTokens:
    """Testa o fluxo principal de renovação de tokens."""

    @pytest.mark.asyncio
    async def test_renovacao_bem_sucedida_retorna_refreshed_1(self):
        """refresh_expired_tokens deve reportar 1 conta renovada com sucesso."""
        from app.jobs.tasks_tokens import _refresh_expired_tokens_async

        account = _make_account()
        mock_db = _make_db_session_with_accounts([account])

        token_data = {
            "access_token": "new_access_token_xyz",
            "refresh_token": "new_refresh_token",
            "expires_in": 21600,
        }

        with patch("app.jobs.tasks_tokens.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_tokens.refresh_ml_token", new_callable=AsyncMock, return_value=token_data), \
             patch("app.jobs.tasks_tokens._acquire_token_refresh_lock", new_callable=AsyncMock, return_value=True), \
             patch("app.jobs.tasks_tokens._release_token_refresh_lock", new_callable=AsyncMock), \
             patch("app.jobs.tasks.sync_all_snapshots") as mock_sync:
            mock_sync.apply_async = MagicMock()
            result = await _refresh_expired_tokens_async()

        assert result["refreshed"] == 1
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_sem_contas_para_renovar_retorna_zero(self):
        """Quando não há contas com token expirando, retorna refreshed=0."""
        from app.jobs.tasks_tokens import _refresh_expired_tokens_async

        mock_db = _make_db_session_with_accounts([])

        with patch("app.jobs.tasks_tokens.AsyncSessionLocal", return_value=mock_db):
            result = await _refresh_expired_tokens_async()

        assert result["refreshed"] == 0
        assert result["errors"] == 0
        assert result["skipped"] == 0


# ============================================================================
# Teste 14: Campos tracking atualizados no sucesso
# ============================================================================


class TestTrackingFieldsOnSuccess:
    """Campos de tracking após renovação bem-sucedida."""

    @pytest.mark.asyncio
    async def test_last_token_refresh_at_definido_apos_sucesso(self):
        """last_token_refresh_at deve ser definido após renovação bem-sucedida."""
        from app.jobs.tasks_tokens import _refresh_expired_tokens_async

        account = _make_account()
        mock_db = _make_db_session_with_accounts([account])

        token_data = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh",
            "expires_in": 21600,
        }

        with patch("app.jobs.tasks_tokens.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_tokens.refresh_ml_token", new_callable=AsyncMock, return_value=token_data), \
             patch("app.jobs.tasks_tokens._acquire_token_refresh_lock", new_callable=AsyncMock, return_value=True), \
             patch("app.jobs.tasks_tokens._release_token_refresh_lock", new_callable=AsyncMock), \
             patch("app.jobs.tasks.sync_all_snapshots") as mock_sync:
            mock_sync.apply_async = MagicMock()
            await _refresh_expired_tokens_async()

        assert account.last_token_refresh_at is not None

    @pytest.mark.asyncio
    async def test_failures_zerado_apos_sucesso(self):
        """token_refresh_failures deve ser zerado após renovação bem-sucedida."""
        from app.jobs.tasks_tokens import _refresh_expired_tokens_async

        # Conta com falhas anteriores
        account = _make_account(token_refresh_failures=3, needs_reauth=True)
        mock_db = _make_db_session_with_accounts([account])

        token_data = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh",
            "expires_in": 21600,
        }

        with patch("app.jobs.tasks_tokens.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_tokens.refresh_ml_token", new_callable=AsyncMock, return_value=token_data), \
             patch("app.jobs.tasks_tokens._acquire_token_refresh_lock", new_callable=AsyncMock, return_value=True), \
             patch("app.jobs.tasks_tokens._release_token_refresh_lock", new_callable=AsyncMock), \
             patch("app.jobs.tasks.sync_all_snapshots") as mock_sync:
            mock_sync.apply_async = MagicMock()
            await _refresh_expired_tokens_async()

        assert account.token_refresh_failures == 0
        assert account.needs_reauth is False

    @pytest.mark.asyncio
    async def test_access_token_atualizado_apos_sucesso(self):
        """account.access_token deve ser atualizado com o novo token."""
        from app.jobs.tasks_tokens import _refresh_expired_tokens_async

        account = _make_account(access_token="old_token")
        mock_db = _make_db_session_with_accounts([account])

        token_data = {
            "access_token": "brand_new_token",
            "refresh_token": "brand_new_refresh",
            "expires_in": 21600,
        }

        with patch("app.jobs.tasks_tokens.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_tokens.refresh_ml_token", new_callable=AsyncMock, return_value=token_data), \
             patch("app.jobs.tasks_tokens._acquire_token_refresh_lock", new_callable=AsyncMock, return_value=True), \
             patch("app.jobs.tasks_tokens._release_token_refresh_lock", new_callable=AsyncMock), \
             patch("app.jobs.tasks.sync_all_snapshots") as mock_sync:
            mock_sync.apply_async = MagicMock()
            await _refresh_expired_tokens_async()

        assert account.access_token == "brand_new_token"


# ============================================================================
# Teste 15: Campos tracking atualizados na falha
# ============================================================================


class TestTrackingFieldsOnFailure:
    """Campos de tracking após falha na renovação."""

    @pytest.mark.asyncio
    async def test_failures_incrementa_apos_falha(self):
        """token_refresh_failures deve incrementar após falha permanente."""
        from app.jobs.tasks_tokens import _refresh_expired_tokens_async

        account = _make_account(token_refresh_failures=2)
        mock_db = _make_db_session_with_accounts([account])

        with patch("app.jobs.tasks_tokens.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_tokens.refresh_ml_token", new_callable=AsyncMock, side_effect=Exception("refresh falhou")), \
             patch("app.jobs.tasks_tokens._acquire_token_refresh_lock", new_callable=AsyncMock, return_value=True), \
             patch("app.jobs.tasks_tokens._release_token_refresh_lock", new_callable=AsyncMock), \
             patch("app.jobs.tasks_tokens.create_notification", new_callable=AsyncMock), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            result = await _refresh_expired_tokens_async()

        assert result["errors"] == 1
        assert account.token_refresh_failures == 3  # 2 + 1

    @pytest.mark.asyncio
    async def test_needs_reauth_true_apos_5_falhas(self):
        """needs_reauth deve ser True quando failures atinge 5."""
        from app.jobs.tasks_tokens import _refresh_expired_tokens_async

        # 4 falhas acumuladas, a próxima vai para 5 e dispara needs_reauth
        account = _make_account(token_refresh_failures=4)
        mock_db = _make_db_session_with_accounts([account])

        with patch("app.jobs.tasks_tokens.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_tokens.refresh_ml_token", new_callable=AsyncMock, side_effect=Exception("falhou")), \
             patch("app.jobs.tasks_tokens._acquire_token_refresh_lock", new_callable=AsyncMock, return_value=True), \
             patch("app.jobs.tasks_tokens._release_token_refresh_lock", new_callable=AsyncMock), \
             patch("app.jobs.tasks_tokens.create_notification", new_callable=AsyncMock), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            await _refresh_expired_tokens_async()

        assert account.token_refresh_failures == 5
        assert account.needs_reauth is True

    @pytest.mark.asyncio
    async def test_needs_reauth_false_abaixo_de_5_falhas(self):
        """needs_reauth deve permanecer False quando failures < 5."""
        from app.jobs.tasks_tokens import _refresh_expired_tokens_async

        account = _make_account(token_refresh_failures=1)
        mock_db = _make_db_session_with_accounts([account])

        with patch("app.jobs.tasks_tokens.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_tokens.refresh_ml_token", new_callable=AsyncMock, side_effect=Exception("falhou")), \
             patch("app.jobs.tasks_tokens._acquire_token_refresh_lock", new_callable=AsyncMock, return_value=True), \
             patch("app.jobs.tasks_tokens._release_token_refresh_lock", new_callable=AsyncMock), \
             patch("app.jobs.tasks_tokens.create_notification", new_callable=AsyncMock), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            await _refresh_expired_tokens_async()

        # failures vai de 1 para 2, ainda abaixo de 5
        assert account.needs_reauth is False


# ============================================================================
# Teste 16: Lock distribuído previne race condition
# ============================================================================


class TestDistributedLock:
    """Testa que o lock distribuído previne race condition."""

    @pytest.mark.asyncio
    async def test_lock_nao_adquirido_pula_conta(self):
        """Quando lock já está adquirido por outro worker, conta é pulada."""
        from app.jobs.tasks_tokens import _refresh_expired_tokens_async

        account = _make_account()
        mock_db = _make_db_session_with_accounts([account])

        with patch("app.jobs.tasks_tokens.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_tokens._acquire_token_refresh_lock", new_callable=AsyncMock, return_value=False):
            result = await _refresh_expired_tokens_async()

        assert result["skipped"] == 1
        assert result["refreshed"] == 0

    @pytest.mark.asyncio
    async def test_lock_liberado_mesmo_com_erro(self):
        """Lock deve ser liberado mesmo quando ocorre erro no refresh (finally block)."""
        from app.jobs.tasks_tokens import _refresh_expired_tokens_async

        account = _make_account()
        mock_db = _make_db_session_with_accounts([account])

        mock_release = AsyncMock()

        with patch("app.jobs.tasks_tokens.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_tokens.refresh_ml_token", new_callable=AsyncMock, side_effect=Exception("erro")), \
             patch("app.jobs.tasks_tokens._acquire_token_refresh_lock", new_callable=AsyncMock, return_value=True), \
             patch("app.jobs.tasks_tokens._release_token_refresh_lock", mock_release), \
             patch("app.jobs.tasks_tokens.create_notification", new_callable=AsyncMock), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            await _refresh_expired_tokens_async()

        # Lock deve ter sido liberado (finally block)
        mock_release.assert_called_once()

    @pytest.mark.asyncio
    async def test_acquire_lock_redis_falha_fail_closed(self):
        """Se Redis falhar, _acquire_token_refresh_lock retorna False (fail-closed)."""
        from app.jobs.tasks_tokens import _acquire_token_refresh_lock

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(side_effect=Exception("Redis down"))

        with patch("app.jobs.tasks_tokens.get_redis_client", return_value=mock_redis):
            result = await _acquire_token_refresh_lock("test-account-id")

        # Fail-closed: retorna False quando Redis está fora
        assert result is False


# ============================================================================
# Teste 17: Backfill automático dispara quando token ficou offline >24h
# ============================================================================


class TestBackfillAutomatic:
    """Testa disparo automático de backfill para contas desconectadas."""

    @pytest.mark.asyncio
    async def test_backfill_disparado_quando_desconectado_mais_de_24h(self):
        """Quando token ficou expirado por >24h, backfill deve ser agendado."""
        from app.jobs.tasks_tokens import _refresh_expired_tokens_async

        # Token expirou há 2 dias (48h)
        account = _make_account(
            token_expires_at=datetime.now(timezone.utc) - timedelta(hours=48)
        )
        mock_db = _make_db_session_with_accounts([account])

        token_data = {
            "access_token": "new_token",
            "refresh_token": "new_refresh",
            "expires_in": 21600,
        }

        mock_backfill = MagicMock()
        mock_backfill.apply_async = MagicMock()

        mock_sync = MagicMock()
        mock_sync.apply_async = MagicMock()

        with patch("app.jobs.tasks_tokens.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_tokens.refresh_ml_token", new_callable=AsyncMock, return_value=token_data), \
             patch("app.jobs.tasks_tokens._acquire_token_refresh_lock", new_callable=AsyncMock, return_value=True), \
             patch("app.jobs.tasks_tokens._release_token_refresh_lock", new_callable=AsyncMock), \
             patch("app.jobs.tasks.sync_all_snapshots", mock_sync), \
             patch("app.jobs.tasks.backfill_orders_after_reconnect", mock_backfill):
            result = await _refresh_expired_tokens_async()

        assert result["backfill_triggered"] == 1
        mock_backfill.apply_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_backfill_nao_disparado_quando_expirado_menos_de_24h(self):
        """Quando token expirou há menos de 24h, backfill NÃO deve ser agendado."""
        from app.jobs.tasks_tokens import _refresh_expired_tokens_async

        # Token expirou há apenas 2h (dentro das 24h)
        account = _make_account(
            token_expires_at=datetime.now(timezone.utc) - timedelta(hours=2)
        )
        mock_db = _make_db_session_with_accounts([account])

        token_data = {
            "access_token": "new_token",
            "refresh_token": "new_refresh",
            "expires_in": 21600,
        }

        mock_sync = MagicMock()
        mock_sync.apply_async = MagicMock()

        with patch("app.jobs.tasks_tokens.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_tokens.refresh_ml_token", new_callable=AsyncMock, return_value=token_data), \
             patch("app.jobs.tasks_tokens._acquire_token_refresh_lock", new_callable=AsyncMock, return_value=True), \
             patch("app.jobs.tasks_tokens._release_token_refresh_lock", new_callable=AsyncMock), \
             patch("app.jobs.tasks.sync_all_snapshots", mock_sync):
            result = await _refresh_expired_tokens_async()

        assert result["backfill_triggered"] == 0


# ============================================================================
# Teste 18: Backfill usa old_expires_at (não o novo) para calcular gap
# ============================================================================


class TestBackfillUsesOldExpiry:
    """Garante que o cálculo do gap usa o timestamp ANTERIOR ao refresh."""

    @pytest.mark.asyncio
    async def test_backfill_usa_old_expires_at(self):
        """
        O gap de desconexão deve ser calculado com base no token_expires_at ANTES
        da renovação, não o novo (que seria sempre futuro e não dispararia backfill).
        """
        from app.jobs.tasks_tokens import _refresh_expired_tokens_async

        # Token expirou há 3 dias — old_expires está no passado
        old_expiry = datetime.now(timezone.utc) - timedelta(days=3)
        account = _make_account(token_expires_at=old_expiry)
        mock_db = _make_db_session_with_accounts([account])

        # Simula refresh que atualiza token_expires_at para o FUTURO
        # O código deve capturar old_expires ANTES de chamar refresh_ml_token
        refreshed = {"called_with_old_expiry": False}

        async def mock_refresh(acc):
            # Neste ponto, token_expires_at ainda é o antigo (no passado)
            refreshed["called_with_old_expiry"] = acc.token_expires_at < datetime.now(timezone.utc)
            # Simula update do token_expires_at PELO CÓDIGO DA FUNÇÃO (não aqui)
            return {
                "access_token": "new_token",
                "refresh_token": "new_refresh",
                "expires_in": 21600,
            }

        mock_sync = MagicMock()
        mock_sync.apply_async = MagicMock()
        mock_backfill = MagicMock()
        mock_backfill.apply_async = MagicMock()

        with patch("app.jobs.tasks_tokens.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_tokens.refresh_ml_token", side_effect=mock_refresh), \
             patch("app.jobs.tasks_tokens._acquire_token_refresh_lock", new_callable=AsyncMock, return_value=True), \
             patch("app.jobs.tasks_tokens._release_token_refresh_lock", new_callable=AsyncMock), \
             patch("app.jobs.tasks.sync_all_snapshots", mock_sync), \
             patch("app.jobs.tasks.backfill_orders_after_reconnect", mock_backfill):
            result = await _refresh_expired_tokens_async()

        # Backfill deve ter sido disparado (token estava expirado há 3 dias)
        assert result["backfill_triggered"] == 1

    @pytest.mark.asyncio
    async def test_backfill_dias_calculados_corretamente(self):
        """O número de dias para backfill deve ser calculado a partir do gap real."""
        from app.jobs.tasks_tokens import _refresh_expired_tokens_async

        # Token expirou há 5 dias
        old_expiry = datetime.now(timezone.utc) - timedelta(days=5)
        account = _make_account(token_expires_at=old_expiry)
        mock_db = _make_db_session_with_accounts([account])

        token_data = {
            "access_token": "new_token",
            "refresh_token": "new_refresh",
            "expires_in": 21600,
        }

        backfill_calls = []
        mock_backfill = MagicMock()

        def capture_apply_async(args=None, countdown=None, **kwargs):
            backfill_calls.append({"args": args, "countdown": countdown})

        mock_backfill.apply_async = capture_apply_async
        mock_sync = MagicMock()
        mock_sync.apply_async = MagicMock()

        with patch("app.jobs.tasks_tokens.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_tokens.refresh_ml_token", new_callable=AsyncMock, return_value=token_data), \
             patch("app.jobs.tasks_tokens._acquire_token_refresh_lock", new_callable=AsyncMock, return_value=True), \
             patch("app.jobs.tasks_tokens._release_token_refresh_lock", new_callable=AsyncMock), \
             patch("app.jobs.tasks.sync_all_snapshots", mock_sync), \
             patch("app.jobs.tasks.backfill_orders_after_reconnect", mock_backfill):
            await _refresh_expired_tokens_async()

        assert len(backfill_calls) == 1
        days_to_backfill = backfill_calls[0]["args"][1]
        # 5 dias de desconexão -> backfill de 5 dias (max 30)
        assert days_to_backfill == 5


# ============================================================================
# Teste 19: Notificação criada quando token falha
# ============================================================================


class TestNotificationOnFailure:
    """Notificação in-app deve ser criada quando refresh falha permanentemente."""

    @pytest.mark.asyncio
    async def test_notificacao_criada_quando_refresh_falha(self):
        """create_notification deve ser chamado quando todas as tentativas falham."""
        from app.jobs.tasks_tokens import _refresh_expired_tokens_async

        account = _make_account(token_refresh_failures=0)
        mock_db = _make_db_session_with_accounts([account])

        mock_notify = AsyncMock()

        with patch("app.jobs.tasks_tokens.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_tokens.refresh_ml_token", new_callable=AsyncMock, side_effect=Exception("erro permanente")), \
             patch("app.jobs.tasks_tokens._acquire_token_refresh_lock", new_callable=AsyncMock, return_value=True), \
             patch("app.jobs.tasks_tokens._release_token_refresh_lock", new_callable=AsyncMock), \
             patch("app.jobs.tasks_tokens.create_notification", mock_notify), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            await _refresh_expired_tokens_async()

        mock_notify.assert_called_once()
        call_kwargs = mock_notify.call_args[1]
        assert call_kwargs["type"] == "token_expired"
        assert account.nickname in call_kwargs["title"]

    @pytest.mark.asyncio
    async def test_notificacao_action_url_aponta_para_configuracoes(self):
        """A URL de ação da notificação deve apontar para /configuracoes."""
        from app.jobs.tasks_tokens import _refresh_expired_tokens_async

        account = _make_account()
        mock_db = _make_db_session_with_accounts([account])

        mock_notify = AsyncMock()

        with patch("app.jobs.tasks_tokens.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_tokens.refresh_ml_token", new_callable=AsyncMock, side_effect=Exception("erro")), \
             patch("app.jobs.tasks_tokens._acquire_token_refresh_lock", new_callable=AsyncMock, return_value=True), \
             patch("app.jobs.tasks_tokens._release_token_refresh_lock", new_callable=AsyncMock), \
             patch("app.jobs.tasks_tokens.create_notification", mock_notify), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            await _refresh_expired_tokens_async()

        call_kwargs = mock_notify.call_args[1]
        assert call_kwargs["action_url"] == "/configuracoes"
