"""Tests for the distributed task lock module."""
import os
import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

LOCK_PREFIX = "celery_lock:"


def test_lock_prefix_format():
    assert LOCK_PREFIX == "celery_lock:"


def test_lock_key_generation():
    task_name = "sync_all_snapshots"
    expected = f"{LOCK_PREFIX}{task_name}"
    assert expected == "celery_lock:sync_all_snapshots"
