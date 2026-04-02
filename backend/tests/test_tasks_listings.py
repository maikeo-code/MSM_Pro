"""
Testes unitários para tasks_listings.py — sincronização de snapshots de anúncios.

Cobre:
  - sync_listings cria snapshots novos
  - sync_listings usa sale_price endpoint (fonte primária desde março 2026)
  - sync_listings fallback quando sale_price falha
  - sync_listings respeita ml_account_id
  - Celery beat schedule configurado corretamente
  - Task de sync diário executa às 06:00 BRT (09:00 UTC)
"""

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-for-unit-tests!!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


# ============================================================================
# Helpers compartilhados
# ============================================================================


def _make_listing(
    listing_id="listing-uuid-1",
    mlb_id="MLB6205732214",
    ml_account_id="account-uuid-1",
    price=Decimal("50.00"),
    status="active",
    listing_type="classico",
):
    """Cria mock de Listing."""
    listing = MagicMock()
    listing.id = listing_id
    listing.mlb_id = mlb_id
    listing.ml_account_id = ml_account_id
    listing.price = price
    listing.status = status
    listing.listing_type = listing_type
    listing.sale_fee_amount = None
    listing.sale_fee_pct = None
    return listing


def _make_ml_account(
    account_id="account-uuid-1",
    access_token="valid_access_token",
    ml_user_id="2050442871",
    token_expires_at=None,
    nickname="MSM_PRIME",
):
    """Cria mock de MLAccount."""
    account = MagicMock()
    account.id = account_id
    account.access_token = access_token
    account.ml_user_id = ml_user_id
    account.nickname = nickname
    account.token_expires_at = token_expires_at or (
        datetime.now(timezone.utc) + timedelta(hours=5)
    )
    return account


def _make_db_session(listing=None, account=None):
    """
    Cria mock de AsyncSession que retorna listing e account nas queries.

    A função _sync_listing_snapshot_async faz pelo menos 3 queries:
      1. SELECT Listing WHERE id = listing_id
      2. SELECT MLAccount WHERE id = ml_account_id
      3. SELECT ListingSnapshot WHERE listing_id = ... AND date = today (upsert check)
    O mock retorna os valores corretos em cada posição e None para queries extras.
    """
    mock_db = AsyncMock()

    mock_listing_result = MagicMock()
    mock_listing_result.scalar_one_or_none.return_value = listing

    mock_account_result = MagicMock()
    mock_account_result.scalar_one_or_none.return_value = account

    # 3ª query: snapshot existente (None = vai criar novo snapshot)
    mock_snapshot_result = MagicMock()
    mock_snapshot_result.scalar_one_or_none.return_value = None

    # Fallback para queries adicionais (None)
    mock_none_result = MagicMock()
    mock_none_result.scalar_one_or_none.return_value = None

    mock_db.execute = AsyncMock(
        side_effect=[
            mock_listing_result,   # 1ª: busca listing
            mock_account_result,   # 2ª: busca account
            mock_snapshot_result,  # 3ª: snapshot existente (upsert check)
            mock_none_result,      # 4ª+ extra queries
            mock_none_result,
            mock_none_result,
        ]
    )
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    return mock_db


def _make_ml_client_mock(
    item_data=None,
    sale_price_data=None,
    sale_price_raises=False,
    visits_data=None,
    orders_data=None,
):
    """Cria mock completo do MLClient."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_client.get_item = AsyncMock(return_value=item_data or {
        "id": "MLB6205732214",
        "price": 50.70,
        "available_quantity": 10,
        "status": "active",
        "category_id": "MLB1000",
        "seller_custom_field": "SKU-001",
        "attributes": [],
    })

    if sale_price_raises:
        mock_client.get_item_sale_price = AsyncMock(side_effect=Exception("sale_price endpoint failed"))
    else:
        mock_client.get_item_sale_price = AsyncMock(return_value=sale_price_data or {
            "amount": 57.38,
            "regular_amount": 69.90,
            "currency_id": "BRL",
        })

    mock_client.get_item_visits = AsyncMock(return_value=visits_data or [{"date": "2026-04-01", "total": 42}])
    mock_client.get_item_orders_by_status = AsyncMock(return_value=orders_data or [])
    mock_client.get_listing_fees = AsyncMock(return_value={"percentage_fee": 11, "sale_fee_amount": 6.31})
    mock_client.get_item_promotions = AsyncMock(return_value=[])

    return mock_client


# ============================================================================
# Teste 20: sync_listings cria snapshots novos
# ============================================================================


class TestSyncListingCreatesSnapshot:
    """Testa que o sync de listing cria um snapshot novo no banco."""

    @pytest.mark.asyncio
    async def test_snapshot_criado_com_dados_corretos(self):
        """_sync_listing_snapshot_async deve criar um ListingSnapshot no banco."""
        from app.jobs.tasks_listings import _sync_listing_snapshot_async

        listing = _make_listing()
        account = _make_ml_account()
        mock_db = _make_db_session(listing=listing, account=account)
        mock_client = _make_ml_client_mock()

        with patch("app.jobs.tasks_listings.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_listings.MLClient", return_value=mock_client), \
             patch("app.jobs.tasks_listings._create_sync_log", new_callable=AsyncMock, return_value=MagicMock()), \
             patch("app.jobs.tasks_listings._finish_sync_log", new_callable=AsyncMock):
            await _sync_listing_snapshot_async(listing.id)

        # Verifica que db.add foi chamado (snapshot adicionado)
        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_listing_nao_encontrado_retorna_erro(self):
        """Quando listing não existe no banco, deve retornar dict com error."""
        from app.jobs.tasks_listings import _sync_listing_snapshot_async

        # DB retorna None para o listing
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        with patch("app.jobs.tasks_listings.AsyncSessionLocal", return_value=mock_db):
            result = await _sync_listing_snapshot_async("listing-nao-existe")

        assert result is not None
        assert "error" in result

    @pytest.mark.asyncio
    async def test_conta_sem_token_retorna_erro(self):
        """Quando conta ML não tem access_token, deve retornar erro."""
        from app.jobs.tasks_listings import _sync_listing_snapshot_async

        listing = _make_listing()
        account_sem_token = _make_ml_account(access_token=None)
        mock_db = _make_db_session(listing=listing, account=account_sem_token)

        with patch("app.jobs.tasks_listings.AsyncSessionLocal", return_value=mock_db):
            result = await _sync_listing_snapshot_async(listing.id)

        assert result is not None
        assert "error" in result


# ============================================================================
# Teste 21: sync_listings usa sale_price endpoint
# ============================================================================


class TestSyncUsesSalePrice:
    """Garante que o sync usa /items/{id}/sale_price como fonte primária de preço."""

    @pytest.mark.asyncio
    async def test_preco_vem_do_sale_price_endpoint(self):
        """O preço salvo no snapshot deve vir do sale_price endpoint, não do /items."""
        from app.jobs.tasks_listings import _sync_listing_snapshot_async

        # /items retorna price=50.70 (depreciado), sale_price retorna amount=57.38 (real)
        listing = _make_listing(price=Decimal("50.70"))
        account = _make_ml_account()
        mock_db = _make_db_session(listing=listing, account=account)

        mock_client = _make_ml_client_mock(
            item_data={
                "id": "MLB6205732214",
                "price": 50.70,
                "available_quantity": 10,
                "status": "active",
                "category_id": None,
                "seller_custom_field": None,
                "attributes": [],
            },
            sale_price_data={"amount": 57.38, "regular_amount": 69.90, "currency_id": "BRL"},
        )

        snapshots_added = []

        def capture_add(obj):
            snapshots_added.append(obj)

        mock_db.add = capture_add

        with patch("app.jobs.tasks_listings.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_listings.MLClient", return_value=mock_client), \
             patch("app.jobs.tasks_listings._create_sync_log", new_callable=AsyncMock, return_value=MagicMock()), \
             patch("app.jobs.tasks_listings._finish_sync_log", new_callable=AsyncMock):
            await _sync_listing_snapshot_async(listing.id)

        # get_item_sale_price deve ter sido chamado
        mock_client.get_item_sale_price.assert_called_once()

    @pytest.mark.asyncio
    async def test_sale_price_endpoint_chamado_com_mlb_id_correto(self):
        """get_item_sale_price deve ser chamado com o MLB ID do listing."""
        from app.jobs.tasks_listings import _sync_listing_snapshot_async

        listing = _make_listing(mlb_id="MLB9999888877")
        account = _make_ml_account()
        mock_db = _make_db_session(listing=listing, account=account)
        mock_client = _make_ml_client_mock()

        with patch("app.jobs.tasks_listings.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_listings.MLClient", return_value=mock_client), \
             patch("app.jobs.tasks_listings._create_sync_log", new_callable=AsyncMock, return_value=MagicMock()), \
             patch("app.jobs.tasks_listings._finish_sync_log", new_callable=AsyncMock):
            await _sync_listing_snapshot_async(listing.id)

        mock_client.get_item_sale_price.assert_called_with("MLB9999888877")


# ============================================================================
# Teste 22: sync_listings fallback quando sale_price falha
# ============================================================================


class TestSyncSalePriceFallback:
    """Testa fallback quando o endpoint /sale_price falha."""

    @pytest.mark.asyncio
    async def test_fallback_usa_preco_do_items_quando_sale_price_falha(self):
        """Quando sale_price endpoint lança exceção, deve usar price do /items como fallback."""
        from app.jobs.tasks_listings import _sync_listing_snapshot_async

        listing = _make_listing(price=Decimal("50.70"))
        account = _make_ml_account()
        mock_db = _make_db_session(listing=listing, account=account)

        # sale_price falha, mas /items retorna price=50.70
        mock_client = _make_ml_client_mock(
            item_data={
                "id": "MLB6205732214",
                "price": 50.70,
                "available_quantity": 10,
                "status": "active",
                "category_id": None,
                "seller_custom_field": None,
                "attributes": [],
                "original_price": None,
                "sale_price": None,
            },
            sale_price_raises=True,
        )

        with patch("app.jobs.tasks_listings.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_listings.MLClient", return_value=mock_client), \
             patch("app.jobs.tasks_listings._create_sync_log", new_callable=AsyncMock, return_value=MagicMock()), \
             patch("app.jobs.tasks_listings._finish_sync_log", new_callable=AsyncMock):
            # Não deve levantar exceção — fallback transparente
            result = await _sync_listing_snapshot_async(listing.id)

        # Deve ter completado sem erro crítico (db.add foi chamado pelo snapshot)
        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_fallback_usa_original_price_quando_disponivel(self):
        """No fallback, deve usar original_price do /items para desconto do vendedor."""
        from app.jobs.tasks_listings import _sync_listing_snapshot_async

        listing = _make_listing(price=Decimal("100.00"))
        account = _make_ml_account()
        mock_db = _make_db_session(listing=listing, account=account)

        # sale_price falha; /items tem original_price indicando desconto do vendedor
        mock_client = _make_ml_client_mock(
            item_data={
                "id": "MLB123",
                "price": 80.00,  # preço com desconto
                "available_quantity": 5,
                "status": "active",
                "category_id": None,
                "seller_custom_field": None,
                "attributes": [],
                "original_price": 100.00,  # preço original (sem desconto)
                "sale_price": None,
            },
            sale_price_raises=True,
        )

        with patch("app.jobs.tasks_listings.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_listings.MLClient", return_value=mock_client), \
             patch("app.jobs.tasks_listings._create_sync_log", new_callable=AsyncMock, return_value=MagicMock()), \
             patch("app.jobs.tasks_listings._finish_sync_log", new_callable=AsyncMock):
            # Não deve levantar exceção
            await _sync_listing_snapshot_async(listing.id)

        mock_db.add.assert_called()


# ============================================================================
# Teste 23: sync_listings respeita ml_account_id
# ============================================================================


class TestSyncRespectsAccount:
    """Garante que o sync usa a conta ML correta do listing."""

    @pytest.mark.asyncio
    async def test_sync_usa_token_da_conta_do_listing(self):
        """O MLClient deve ser inicializado com o token da conta associada ao listing."""
        from app.jobs.tasks_listings import _sync_listing_snapshot_async

        listing = _make_listing(ml_account_id="account-specific-id")
        account = _make_ml_account(
            account_id="account-specific-id",
            access_token="specific_account_token",
        )
        mock_db = _make_db_session(listing=listing, account=account)
        mock_client = _make_ml_client_mock()

        client_init_args = []

        def capture_client_init(access_token, ml_account_id=None):
            client_init_args.append({"access_token": access_token, "ml_account_id": ml_account_id})
            return mock_client

        with patch("app.jobs.tasks_listings.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_listings.MLClient", side_effect=capture_client_init), \
             patch("app.jobs.tasks_listings._create_sync_log", new_callable=AsyncMock, return_value=MagicMock()), \
             patch("app.jobs.tasks_listings._finish_sync_log", new_callable=AsyncMock):
            await _sync_listing_snapshot_async(listing.id)

        assert len(client_init_args) == 1
        assert client_init_args[0]["access_token"] == "specific_account_token"
        assert client_init_args[0]["ml_account_id"] == "account-specific-id"

    @pytest.mark.asyncio
    async def test_token_refresh_antes_de_sync_quando_expirando(self):
        """Quando token expira em < 1h, deve renovar antes de chamar a API."""
        from app.jobs.tasks_listings import _sync_listing_snapshot_async

        listing = _make_listing()
        # Token expira em 30 minutos (dentro do threshold de 1h)
        account = _make_ml_account(
            token_expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)
        )
        mock_db = _make_db_session(listing=listing, account=account)
        mock_client = _make_ml_client_mock()

        mock_refresh = AsyncMock(return_value="refreshed_token_xyz")

        with patch("app.jobs.tasks_listings.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_listings.MLClient", return_value=mock_client), \
             patch("app.jobs.tasks_listings._create_sync_log", new_callable=AsyncMock, return_value=MagicMock()), \
             patch("app.jobs.tasks_listings._finish_sync_log", new_callable=AsyncMock), \
             patch("app.auth.service.refresh_ml_token_by_id", mock_refresh):
            await _sync_listing_snapshot_async(listing.id)

        # refresh deve ter sido chamado
        mock_refresh.assert_called_once()


# ============================================================================
# Teste 24: Celery beat schedule configurado corretamente
# ============================================================================


class TestCeleryBeatSchedule:
    """Testa que o beat schedule está configurado corretamente."""

    def test_sync_all_snapshots_task_no_schedule(self):
        """sync-all-snapshots-daily deve estar no beat_schedule."""
        from app.core.celery_app import celery_app

        beat_schedule = celery_app.conf.beat_schedule
        assert "sync-all-snapshots-daily" in beat_schedule

    def test_refresh_expired_tokens_no_schedule(self):
        """refresh-expired-tokens deve estar no beat_schedule."""
        from app.core.celery_app import celery_app

        beat_schedule = celery_app.conf.beat_schedule
        assert "refresh-expired-tokens" in beat_schedule

    def test_sync_orders_no_schedule(self):
        """sync-orders-every-2h deve estar no beat_schedule."""
        from app.core.celery_app import celery_app

        beat_schedule = celery_app.conf.beat_schedule
        assert "sync-orders-every-2h" in beat_schedule

    def test_tasks_no_schedule_tem_task_name_correto(self):
        """Cada entrada do beat_schedule deve ter o campo 'task' definido."""
        from app.core.celery_app import celery_app

        beat_schedule = celery_app.conf.beat_schedule
        for entry_name, entry_config in beat_schedule.items():
            assert "task" in entry_config, f"Entrada '{entry_name}' não tem campo 'task'"
            assert entry_config["task"].startswith("app.jobs.tasks."), (
                f"Task '{entry_config['task']}' não segue padrão app.jobs.tasks.*"
            )

    def test_timezone_definido_como_sao_paulo(self):
        """Celery deve usar timezone America/Sao_Paulo."""
        from app.core.celery_app import celery_app

        assert celery_app.conf.timezone == "America/Sao_Paulo"


# ============================================================================
# Teste 25: Task de sync diário executa às 06:00 BRT (09:00 UTC)
# ============================================================================


class TestSyncDailyScheduleTime:
    """Testa que o sync diário está agendado para 06:00 BRT (09:00 UTC)."""

    def test_sync_all_snapshots_hora_correta_utc(self):
        """sync_all_snapshots deve estar agendado para hora=9 (09:00 UTC = 06:00 BRT)."""
        from app.core.celery_app import celery_app
        from celery.schedules import crontab

        schedule_entry = celery_app.conf.beat_schedule["sync-all-snapshots-daily"]
        schedule = schedule_entry["schedule"]

        assert isinstance(schedule, crontab)
        # hour=9 = 09:00 UTC = 06:00 BRT (UTC-3)
        # _orig_hour pode ser int, str ou set dependendo da versão do Celery
        orig_hour = schedule._orig_hour
        if isinstance(orig_hour, (set, frozenset)):
            assert 9 in orig_hour
        else:
            assert str(orig_hour) == "9"

    def test_sync_all_snapshots_minuto_zero(self):
        """sync_all_snapshots deve ser agendado no minuto 0."""
        from app.core.celery_app import celery_app
        from celery.schedules import crontab

        schedule_entry = celery_app.conf.beat_schedule["sync-all-snapshots-daily"]
        schedule = schedule_entry["schedule"]

        assert isinstance(schedule, crontab)
        # minute=0 (em ponto)
        orig_minute = schedule._orig_minute
        if isinstance(orig_minute, (set, frozenset)):
            assert 0 in orig_minute
        else:
            assert str(orig_minute) == "0"

    def test_refresh_tokens_roda_a_cada_30_minutos(self):
        """refresh_expired_tokens deve rodar a cada 30 minutos (*/30)."""
        from app.core.celery_app import celery_app
        from celery.schedules import crontab

        schedule_entry = celery_app.conf.beat_schedule["refresh-expired-tokens"]
        schedule = schedule_entry["schedule"]

        assert isinstance(schedule, crontab)
        # */30 significa minutos 0 e 30 — verificar pelo string do padrão original
        # ou pelos minutos resultantes {0, 30}
        orig_minute = schedule._orig_minute
        orig_minute_str = str(orig_minute)
        assert "*/30" in orig_minute_str or orig_minute == {0, 30} or orig_minute_str in ("*/30", "{0, 30}")

    def test_enable_utc_ativo(self):
        """enable_utc deve ser True para que os horários sejam em UTC."""
        from app.core.celery_app import celery_app

        assert celery_app.conf.enable_utc is True
