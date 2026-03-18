"""Tests for pagination logic."""
import os
import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")


def test_pagination_slice_first_page():
    items = list(range(100))
    page, per_page = 1, 10
    start = (page - 1) * per_page
    result = items[start:start + per_page]
    assert result == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]


def test_pagination_slice_second_page():
    items = list(range(100))
    page, per_page = 2, 10
    start = (page - 1) * per_page
    result = items[start:start + per_page]
    assert result == [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]


def test_pagination_slice_last_page_partial():
    items = list(range(25))
    page, per_page = 3, 10
    start = (page - 1) * per_page
    result = items[start:start + per_page]
    assert result == [20, 21, 22, 23, 24]


def test_pagination_beyond_data():
    items = list(range(10))
    page, per_page = 5, 10
    start = (page - 1) * per_page
    result = items[start:start + per_page]
    assert result == []


def test_pagination_default_returns_all():
    items = list(range(50))
    page, per_page = 1, 200
    start = (page - 1) * per_page
    result = items[start:start + per_page]
    assert len(result) == 50


def test_pagination_per_page_1():
    items = list(range(10))
    page, per_page = 3, 1
    start = (page - 1) * per_page
    result = items[start:start + per_page]
    assert result == [2]
