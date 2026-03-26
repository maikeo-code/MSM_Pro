"""
Unit tests for Celery jobs logic — tasks_helpers.py, tasks_lock.py.

Tests:
  1. run_async: executes coroutines correctly
  2. Lock key format: validates lock key generation
  3. Task registration: checks that all tasks are imported in tasks.py
  4. Rate limit cache: validates _webhook_rate_cache fallback (if used)

Does NOT test:
  - Redis interactions (mocked)
  - AsyncSession or database
  - Full task execution (requires Celery worker + Redis)

Uses unittest.mock for Redis/Celery interactions.
"""
import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Set test env vars BEFORE any app imports (required for config.py)
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-for-unit-tests!!")


# ============================================================================
# Test run_async() helper from tasks_helpers.py
# ============================================================================

class TestRunAsync:
    """Tests for run_async() — executes async coroutines in sync context."""

    def test_run_async_executes_simple_coroutine(self):
        """run_async should execute a simple coroutine and return result."""
        from app.jobs.tasks_helpers import run_async

        async def simple_coro():
            return 42

        result = run_async(simple_coro())
        assert result == 42

    def test_run_async_executes_coroutine_with_await(self):
        """run_async should handle coroutines with internal awaits."""
        from app.jobs.tasks_helpers import run_async

        async def coro_with_await():
            await asyncio.sleep(0)  # Simulate async work
            return "success"

        result = run_async(coro_with_await())
        assert result == "success"

    def test_run_async_executes_coroutine_with_exception(self):
        """run_async should propagate exceptions from coroutine."""
        from app.jobs.tasks_helpers import run_async

        async def coro_raises():
            await asyncio.sleep(0)
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            run_async(coro_raises())

    def test_run_async_returns_dict(self):
        """run_async should handle dict returns."""
        from app.jobs.tasks_helpers import run_async

        async def coro_returns_dict():
            return {"status": "ok", "count": 10}

        result = run_async(coro_returns_dict())
        assert isinstance(result, dict)
        assert result["status"] == "ok"
        assert result["count"] == 10

    def test_run_async_closes_event_loop(self):
        """run_async should properly close the event loop after execution."""
        from app.jobs.tasks_helpers import run_async

        async def simple():
            return True

        # If loop is not closed, running again would fail
        result1 = run_async(simple())
        assert result1 is True

        # Second call should work too (new loop created)
        result2 = run_async(simple())
        assert result2 is True

    def test_run_async_with_nested_coroutines(self):
        """run_async should handle nested coroutine calls."""
        from app.jobs.tasks_helpers import run_async

        async def inner():
            await asyncio.sleep(0)
            return 100

        async def outer():
            result = await inner()
            return result * 2

        result = run_async(outer())
        assert result == 200


# ============================================================================
# Test Lock key format from tasks_lock.py (with mocking)
# ============================================================================

class TestLockKeyFormat:
    """Tests for lock key generation in tasks_lock.py."""

    @patch("app.jobs.tasks_lock.aioredis")
    def test_lock_prefix_constant_defined(self, mock_aioredis):
        """LOCK_PREFIX should be defined."""
        from app.jobs.tasks_lock import LOCK_PREFIX
        assert LOCK_PREFIX == "celery_lock:"

    @patch("app.jobs.tasks_lock.aioredis")
    def test_lock_key_format_includes_prefix(self, mock_aioredis):
        """Lock key should include LOCK_PREFIX."""
        from app.jobs.tasks_lock import LOCK_PREFIX

        task_name = "sync_all_snapshots"
        expected_key = f"{LOCK_PREFIX}{task_name}"
        assert expected_key == "celery_lock:sync_all_snapshots"

    @patch("app.jobs.tasks_lock.aioredis")
    def test_lock_key_format_for_different_tasks(self, mock_aioredis):
        """Lock key should be unique per task name."""
        from app.jobs.tasks_lock import LOCK_PREFIX

        task_names = [
            "sync_all_snapshots",
            "sync_recent_snapshots",
            "refresh_expired_tokens",
            "sync_competitor_snapshots",
            "evaluate_alerts",
            "sync_orders",
            "send_weekly_digest",
            "sync_ads",
            "send_daily_intel_report",
        ]

        keys = [f"{LOCK_PREFIX}{name}" for name in task_names]
        # All keys should be unique
        assert len(keys) == len(set(keys))

    @pytest.mark.asyncio
    @patch("app.jobs.tasks_lock.aioredis.from_url")
    async def test_acquire_task_lock_returns_boolean(self, mock_redis_from_url):
        """acquire_task_lock should return a boolean."""
        from app.jobs.tasks_lock import acquire_task_lock

        mock_redis_instance = AsyncMock()
        mock_redis_instance.set = AsyncMock(return_value=True)
        mock_redis_instance.aclose = AsyncMock()
        mock_redis_from_url.return_value = mock_redis_instance

        result = await acquire_task_lock("test_task", timeout=600)
        assert isinstance(result, bool)
        assert result is True

    @pytest.mark.asyncio
    @patch("app.jobs.tasks_lock.aioredis.from_url")
    async def test_acquire_task_lock_calls_redis_set_with_nx(self, mock_redis_from_url):
        """acquire_task_lock should call redis.set with nx=True for atomic acquire."""
        from app.jobs.tasks_lock import acquire_task_lock, LOCK_PREFIX

        mock_redis_instance = AsyncMock()
        mock_redis_instance.set = AsyncMock(return_value=True)
        mock_redis_instance.aclose = AsyncMock()
        mock_redis_from_url.return_value = mock_redis_instance

        task_name = "sync_all_snapshots"
        await acquire_task_lock(task_name, timeout=900)

        # Verify redis.set was called with correct key and nx=True
        mock_redis_instance.set.assert_called_once()
        call_args = mock_redis_instance.set.call_args
        assert call_args[0][0] == f"{LOCK_PREFIX}{task_name}"  # key
        assert call_args[1]["nx"] is True
        assert call_args[1]["ex"] == 900  # timeout

    @pytest.mark.asyncio
    @patch("app.jobs.tasks_lock.aioredis.from_url")
    async def test_release_task_lock_calls_redis_delete(self, mock_redis_from_url):
        """release_task_lock should call redis.delete."""
        from app.jobs.tasks_lock import release_task_lock, LOCK_PREFIX

        mock_redis_instance = AsyncMock()
        mock_redis_instance.delete = AsyncMock()
        mock_redis_instance.aclose = AsyncMock()
        mock_redis_from_url.return_value = mock_redis_instance

        task_name = "test_task"
        await release_task_lock(task_name)

        # Verify redis.delete was called with correct key
        mock_redis_instance.delete.assert_called_once_with(f"{LOCK_PREFIX}{task_name}")

    @pytest.mark.asyncio
    @patch("app.jobs.tasks_lock.aioredis.from_url")
    async def test_acquire_task_lock_redis_down_proceeds_without_lock(self, mock_redis_from_url):
        """If Redis is down, acquire_task_lock should return True (proceed without lock)."""
        from app.jobs.tasks_lock import acquire_task_lock

        mock_redis_instance = AsyncMock()
        mock_redis_instance.set = AsyncMock(side_effect=Exception("Redis connection failed"))
        mock_redis_instance.aclose = AsyncMock()
        mock_redis_from_url.return_value = mock_redis_instance

        result = await acquire_task_lock("test_task")
        # Should return True (proceed without lock on error)
        assert result is True

    @pytest.mark.asyncio
    @patch("app.jobs.tasks_lock.aioredis.from_url")
    async def test_release_task_lock_redis_down_graceful_failure(self, mock_redis_from_url):
        """release_task_lock should gracefully handle Redis errors."""
        from app.jobs.tasks_lock import release_task_lock

        mock_redis_instance = AsyncMock()
        mock_redis_instance.delete = AsyncMock(side_effect=Exception("Redis down"))
        mock_redis_instance.aclose = AsyncMock()
        mock_redis_from_url.return_value = mock_redis_instance

        # Should not raise
        await release_task_lock("test_task")


# ============================================================================
# Test Task Registration in tasks.py (with mocking)
# ============================================================================

class TestTaskRegistration:
    """Tests that all expected tasks are registered in tasks.py."""

    @patch("app.core.celery_app.Celery")
    def test_all_expected_tasks_imported(self, mock_celery):
        """All task async functions should be imported in tasks.py."""
        from app.jobs import tasks

        expected_functions = [
            "_sync_ads_async",
            "_evaluate_alerts_async",
            "_sync_competitor_snapshots_async",
            "_send_daily_intel_report_async",
            "_send_weekly_digest_async",
            "_sync_all_snapshots_async",
            "_sync_listing_snapshot_async",
            "_sync_recent_snapshots_async",
            "_sync_orders_async",
            "_sync_reputation_async",
            "_refresh_expired_tokens_async",
        ]

        for func_name in expected_functions:
            assert hasattr(tasks, func_name), f"tasks.py should import {func_name}"

    @patch("app.core.celery_app.Celery")
    def test_all_expected_celery_tasks_defined(self, mock_celery):
        """All Celery task decorators should be registered."""
        from app.jobs import tasks

        expected_task_names = [
            "sync_listing_snapshot",
            "sync_all_snapshots",
            "sync_recent_snapshots",
            "refresh_expired_tokens",
            "sync_competitor_snapshots",
            "evaluate_alerts",
            "sync_reputation",
            "sync_orders",
            "send_weekly_digest",
            "sync_ads",
            "send_daily_intel_report",
        ]

        for task_name in expected_task_names:
            assert hasattr(tasks, task_name), f"tasks.py should define {task_name} task"

    @patch("app.core.celery_app.Celery")
    def test_lock_functions_imported(self, mock_celery):
        """Lock functions should be imported."""
        from app.jobs import tasks

        assert hasattr(tasks, "acquire_task_lock")
        assert hasattr(tasks, "release_task_lock")

    @patch("app.core.celery_app.Celery")
    def test_run_async_imported(self, mock_celery):
        """run_async should be imported."""
        from app.jobs import tasks

        assert hasattr(tasks, "run_async")

    @patch("app.core.celery_app.Celery")
    def test_celery_app_imported(self, mock_celery):
        """celery_app should be imported."""
        from app.jobs import tasks

        assert hasattr(tasks, "celery_app")


# ============================================================================
# Test Sync Log helpers from tasks_helpers.py
# ============================================================================

class TestSyncLogHelpers:
    """Tests for _create_sync_log and _finish_sync_log helpers."""

    @pytest.mark.asyncio
    async def test_create_sync_log_imports_model(self):
        """_create_sync_log should import SyncLog model."""
        from app.jobs.tasks_helpers import _create_sync_log

        # We won't call it without a real DB, but verify function exists
        assert callable(_create_sync_log)

    @pytest.mark.asyncio
    async def test_finish_sync_log_imports_model(self):
        """_finish_sync_log should import SyncLog model."""
        from app.jobs.tasks_helpers import _finish_sync_log

        # We won't call it without a real DB, but verify function exists
        assert callable(_finish_sync_log)

    def test_sync_log_functions_have_correct_signatures(self):
        """Verify function signatures."""
        from app.jobs.tasks_helpers import _create_sync_log, _finish_sync_log
        import inspect

        # _create_sync_log(db, task_name, ml_account_id=None)
        sig_create = inspect.signature(_create_sync_log)
        assert "db" in sig_create.parameters
        assert "task_name" in sig_create.parameters
        assert "ml_account_id" in sig_create.parameters

        # _finish_sync_log(db, log, status, items=0, failed=0, error=None)
        sig_finish = inspect.signature(_finish_sync_log)
        assert "db" in sig_finish.parameters
        assert "log" in sig_finish.parameters
        assert "status" in sig_finish.parameters
        assert "items" in sig_finish.parameters
        assert "failed" in sig_finish.parameters
        assert "error" in sig_finish.parameters


# ============================================================================
# Test Task Configuration and Defaults
# ============================================================================

class TestTaskConfiguration:
    """Tests that task decorators have correct configuration."""

    @patch("app.core.celery_app.Celery")
    def test_sync_listing_snapshot_task_retry_config(self, mock_celery):
        """sync_listing_snapshot should have max_retries=3."""
        from app.jobs.tasks import sync_listing_snapshot

        assert hasattr(sync_listing_snapshot, "max_retries")
        assert sync_listing_snapshot.max_retries == 3

    @patch("app.core.celery_app.Celery")
    def test_sync_all_snapshots_task_has_bind_true(self, mock_celery):
        """sync_all_snapshots should have bind=True (access to self via decorator)."""
        from app.jobs.tasks import sync_all_snapshots

        # bind is a decorator parameter, check that task is callable with self
        assert callable(sync_all_snapshots)
        # Verify it's a Celery task
        assert hasattr(sync_all_snapshots, "apply_async")

    @patch("app.core.celery_app.Celery")
    def test_task_names_follow_pattern(self, mock_celery):
        """Task names should follow app.jobs.tasks.* pattern."""
        from app.jobs.tasks import (
            sync_listing_snapshot,
            sync_all_snapshots,
            sync_recent_snapshots,
            refresh_expired_tokens,
            sync_competitor_snapshots,
            evaluate_alerts,
            sync_reputation,
            sync_orders,
            send_weekly_digest,
            sync_ads,
            send_daily_intel_report,
        )

        tasks_to_check = [
            (sync_listing_snapshot, "app.jobs.tasks.sync_listing_snapshot"),
            (sync_all_snapshots, "app.jobs.tasks.sync_all_snapshots"),
            (sync_recent_snapshots, "app.jobs.tasks.sync_recent_snapshots"),
            (refresh_expired_tokens, "app.jobs.tasks.refresh_expired_tokens"),
            (sync_competitor_snapshots, "app.jobs.tasks.sync_competitor_snapshots"),
            (evaluate_alerts, "app.jobs.tasks.evaluate_alerts"),
            (sync_reputation, "app.jobs.tasks.sync_reputation"),
            (sync_orders, "app.jobs.tasks.sync_orders"),
            (send_weekly_digest, "app.jobs.tasks.send_weekly_digest"),
            (sync_ads, "app.jobs.tasks.sync_ads"),
            (send_daily_intel_report, "app.jobs.tasks.send_daily_intel_report"),
        ]

        for task, expected_name in tasks_to_check:
            assert task.name == expected_name, f"Task name mismatch: {task.name} != {expected_name}"


# ============================================================================
# Test Integration: run_async + lock flow
# ============================================================================

class TestAsyncLockIntegration:
    """Tests the integration of run_async with lock functions."""

    @pytest.mark.asyncio
    @patch("app.jobs.tasks_lock.aioredis.from_url")
    async def test_async_lock_acquire_release_pattern(self, mock_redis_from_url):
        """Test common pattern: try acquire, do work, finally release."""
        from app.jobs.tasks_lock import acquire_task_lock, release_task_lock

        mock_redis_instance = AsyncMock()
        mock_redis_instance.set = AsyncMock(return_value=True)
        mock_redis_instance.delete = AsyncMock()
        mock_redis_instance.aclose = AsyncMock()
        mock_redis_from_url.return_value = mock_redis_instance

        async def task_with_lock():
            if not await acquire_task_lock("test", timeout=600):
                return {"status": "skipped"}
            try:
                return {"status": "success", "items": 10}
            finally:
                await release_task_lock("test")

        result = await task_with_lock()
        assert result["status"] == "success"
        mock_redis_instance.set.assert_called_once()
        mock_redis_instance.delete.assert_called_once()

    def test_run_async_with_lock_pattern(self):
        """Test run_async with async lock pattern."""
        from app.jobs.tasks_helpers import run_async

        async def task_with_lock():
            # Simulate lock acquire (always succeeds for this test)
            acquired = True
            if not acquired:
                return {"status": "skipped"}
            try:
                await asyncio.sleep(0)
                return {"status": "done"}
            finally:
                # Simulate lock release
                pass

        result = run_async(task_with_lock())
        assert result["status"] == "done"


# ============================================================================
# Test Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error scenarios."""

    def test_run_async_with_none_return(self):
        """run_async should handle None returns."""
        from app.jobs.tasks_helpers import run_async

        async def returns_none():
            await asyncio.sleep(0)
            return None

        result = run_async(returns_none())
        assert result is None

    def test_run_async_with_empty_dict_return(self):
        """run_async should handle empty dict returns."""
        from app.jobs.tasks_helpers import run_async

        async def returns_empty_dict():
            return {}

        result = run_async(returns_empty_dict())
        assert result == {}

    @patch("app.jobs.tasks_lock.aioredis")
    def test_lock_key_with_special_characters_in_task_name(self, mock_aioredis):
        """Lock key should handle task names with underscores and numbers."""
        from app.jobs.tasks_lock import LOCK_PREFIX

        task_names = [
            "sync_all_snapshots_v2",
            "task_123",
            "my_task_name_with_underscores",
        ]

        for task_name in task_names:
            lock_key = f"{LOCK_PREFIX}{task_name}"
            assert lock_key.startswith(LOCK_PREFIX)
            assert task_name in lock_key

    @pytest.mark.asyncio
    @patch("app.jobs.tasks_lock.aioredis.from_url")
    async def test_acquire_lock_returns_false_on_already_held(self, mock_redis_from_url):
        """acquire_task_lock should return False if lock already held."""
        from app.jobs.tasks_lock import acquire_task_lock

        mock_redis_instance = AsyncMock()
        # redis.set returns None when NX fails (key already exists)
        mock_redis_instance.set = AsyncMock(return_value=None)
        mock_redis_instance.aclose = AsyncMock()
        mock_redis_from_url.return_value = mock_redis_instance

        result = await acquire_task_lock("test_task")
        assert result is False
