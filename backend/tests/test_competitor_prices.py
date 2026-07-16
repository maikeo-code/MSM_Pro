"""Testes da feature de coleta de preço de concorrentes (competitor_prices).

Cobre:
  - classificador item vs catálogo (is_catalog_id)
  - lista de alvos achatada e sem duplicatas
  - coleta usa /items para item e /products (buy_box_winner) para catálogo
  - upsert por (id_ml, day)
  - task no beat schedule
"""
import os
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-for-unit-tests!!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


class TestIsCatalogId:
    """Classificação item (10díg) vs catálogo (MLBU ou 8díg)."""

    def test_item_10_digitos_nao_e_catalogo(self):
        from app.concorrencia.competitor_targets import is_catalog_id

        assert is_catalog_id("MLB4185585590") is False
        assert is_catalog_id("MLB3377496529") is False

    def test_catalogo_8_digitos(self):
        from app.concorrencia.competitor_targets import is_catalog_id

        assert is_catalog_id("MLB66736353") is True
        assert is_catalog_id("MLB68602042") is True

    def test_catalogo_mlbu(self):
        from app.concorrencia.competitor_targets import is_catalog_id

        assert is_catalog_id("MLBU3453370601") is True

    def test_case_insensitive_e_trim(self):
        from app.concorrencia.competitor_targets import is_catalog_id

        assert is_catalog_id("  mlbu3453370601 ") is True
        assert is_catalog_id("mlb4185585590") is False


class TestTargetsList:
    """A lista de alvos deve ter os 11 concorrentes, sem duplicatas."""

    def test_11_alvos(self):
        from app.concorrencia.competitor_targets import COMPETITOR_TARGETS

        assert len(COMPETITOR_TARGETS) == 11
        assert len(set(COMPETITOR_TARGETS)) == 11

    def test_contem_ids_conhecidos(self):
        from app.concorrencia.competitor_targets import COMPETITOR_TARGETS

        for cid in ("MLB4185585590", "MLB66736353", "MLBU3453370601", "MLB4130481127"):
            assert cid in COMPETITOR_TARGETS


def _make_db_upsert_miss():
    """DB mock cujo SELECT de competitor_price sempre retorna None (insere novo)."""
    mock_db = AsyncMock()
    miss = MagicMock()
    miss.scalar_one_or_none.return_value = None
    # 1ª execute = SELECT account; depois vários SELECT competitor_price (None)
    account = MagicMock()
    account.access_token = "tok"
    account.id = "acc-1"
    account.is_active = True
    account_result = MagicMock()
    account_result.scalars.return_value.first.return_value = account
    mock_db.execute = AsyncMock(side_effect=[account_result] + [miss] * 20)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    return mock_db


class TestCollectCompetitorPrices:
    @pytest.mark.asyncio
    async def test_item_usa_get_item_e_catalogo_usa_get_product(self):
        from app.jobs.tasks_competitor_prices import _collect_competitor_prices_async

        mock_db = _make_db_upsert_miss()

        mock_client = AsyncMock()

        # Itens de terceiro: via MULTIGET (verbose [{code, body}]).
        async def fake_multiget(ids, attributes=None):
            return [
                {"code": 200, "body": {
                    "id": i, "price": 99.90, "sold_quantity": 12,
                    "available_quantity": 5, "status": "active",
                }}
                for i in ids
            ]
        mock_client.get_items_multiget = AsyncMock(side_effect=fake_multiget)
        mock_client.get_item = AsyncMock()  # NÃO deve ser chamado (item de terceiro = 403)
        # Catálogo: buy_box_winner com price/available_quantity (SEM sold_quantity).
        mock_client.get_product = AsyncMock(return_value={
            "buy_box_winner": {"item_id": "MLBWINNER1", "price": 55.50, "available_quantity": 8},
        })
        mock_client.close = AsyncMock()

        added = []
        mock_db.add = lambda obj: added.append(obj)

        with patch("app.jobs.tasks_competitor_prices.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_competitor_prices.MLClient", return_value=mock_client), \
             patch("app.jobs.tasks_competitor_prices._create_sync_log", new_callable=AsyncMock, return_value=MagicMock()), \
             patch("app.jobs.tasks_competitor_prices._finish_sync_log", new_callable=AsyncMock):
            result = await _collect_competitor_prices_async()

        assert result["success"] is True
        assert result["collected"] == 11
        # 4 catálogo → 4 get_product; 7 itens → 1 multiget (batch); get_item NUNCA.
        assert mock_client.get_product.call_count == 4
        assert mock_client.get_items_multiget.call_count == 1
        assert mock_client.get_item.call_count == 0
        catalog_rows = [r for r in added if r.is_buy_box]
        item_rows = [r for r in added if not r.is_buy_box]
        assert len(catalog_rows) == 4
        assert len(item_rows) == 7
        assert item_rows[0].price == Decimal("99.90")
        assert item_rows[0].sold_quantity == 12
        assert catalog_rows[0].price == Decimal("55.50")
        assert catalog_rows[0].available_quantity == 8       # do buy_box_winner
        assert catalog_rows[0].sold_quantity is None          # inacessível p/ concorrente

    @pytest.mark.asyncio
    async def test_falha_em_um_nao_derruba_os_demais(self):
        from app.jobs.tasks_competitor_prices import _collect_competitor_prices_async

        mock_db = _make_db_upsert_miss()
        mock_db.add = MagicMock()

        mock_client = AsyncMock()
        # Multiget retorna code!=200 para todo item (ex.: 403) → 7 itens falham.
        async def fake_multiget_403(ids, attributes=None):
            return [{"code": 403, "body": {"id": i}} for i in ids]
        mock_client.get_items_multiget = AsyncMock(side_effect=fake_multiget_403)
        mock_client.get_item = AsyncMock()
        mock_client.get_product = AsyncMock(return_value={"buy_box_winner": {"price": 10}})
        mock_client.close = AsyncMock()

        with patch("app.jobs.tasks_competitor_prices.AsyncSessionLocal", return_value=mock_db), \
             patch("app.jobs.tasks_competitor_prices.MLClient", return_value=mock_client), \
             patch("app.jobs.tasks_competitor_prices._create_sync_log", new_callable=AsyncMock, return_value=MagicMock()), \
             patch("app.jobs.tasks_competitor_prices._finish_sync_log", new_callable=AsyncMock):
            result = await _collect_competitor_prices_async()

        # 7 itens falharam (multiget 403), 4 catálogos ok
        assert result["collected"] == 4
        assert result["failed"] == 7


class TestCompetitorPricesSchedule:
    def test_task_no_beat_schedule(self):
        from app.core.celery_app import celery_app

        bs = celery_app.conf.beat_schedule
        assert "collect-competitor-prices-daily" in bs
        assert bs["collect-competitor-prices-daily"]["task"] == "app.jobs.tasks.collect_competitor_prices"
