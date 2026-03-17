"""
Redis-based distributed lock for preventing duplicate Celery task execution.

Uses Redis SET NX with TTL — simple and reliable.
The lock auto-expires after `timeout` seconds, so if a worker crashes
the lock is automatically released.

Usage:
    if not await acquire_task_lock("sync_all_snapshots", timeout=600):
        return {"status": "skipped"}
    try:
        # do work
    finally:
        await release_task_lock("sync_all_snapshots")
"""
import logging

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

LOCK_PREFIX = "celery_lock:"


async def acquire_task_lock(task_name: str, timeout: int = 600) -> bool:
    """Try to acquire a distributed lock. Returns True if acquired."""
    lock_key = f"{LOCK_PREFIX}{task_name}"
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        acquired = await r.set(lock_key, "1", nx=True, ex=timeout)
        if not acquired:
            logger.warning(f"Task {task_name} already running (lock held), skipping")
        return bool(acquired)
    except Exception as e:
        logger.warning(f"Redis lock error for {task_name}: {e}, proceeding without lock")
        return True  # If Redis is down, proceed without lock
    finally:
        await r.aclose()


async def release_task_lock(task_name: str) -> None:
    """Release a distributed lock."""
    lock_key = f"{LOCK_PREFIX}{task_name}"
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await r.delete(lock_key)
    except Exception:
        pass  # Lock will auto-expire via TTL
    finally:
        await r.aclose()
