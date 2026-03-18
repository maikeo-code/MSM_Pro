"""Tests for supervisord configuration validity."""
import os
import pytest
import configparser

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

SUPERVISORD_PATH = os.path.join(
    os.path.dirname(__file__), "..", "supervisord.conf"
)


@pytest.fixture
def supervisor_config():
    if not os.path.exists(SUPERVISORD_PATH):
        pytest.skip("supervisord.conf not found")
    config = configparser.RawConfigParser()
    config.read(SUPERVISORD_PATH)
    return config


def test_supervisord_has_uvicorn(supervisor_config):
    assert "program:uvicorn" in supervisor_config.sections()


def test_supervisord_has_celery_worker(supervisor_config):
    assert "program:celery-worker" in supervisor_config.sections()


def test_supervisord_has_celery_beat(supervisor_config):
    assert "program:celery-beat" in supervisor_config.sections()


def test_supervisord_all_autostart(supervisor_config):
    for section in supervisor_config.sections():
        if section.startswith("program:"):
            assert supervisor_config[section].get("autostart") == "true"


def test_supervisord_all_autorestart(supervisor_config):
    for section in supervisor_config.sections():
        if section.startswith("program:"):
            assert supervisor_config[section].get("autorestart") == "true"


def test_supervisord_uvicorn_uses_port_env(supervisor_config):
    cmd = supervisor_config["program:uvicorn"]["command"]
    assert "%(ENV_PORT)s" in cmd or "PORT" in cmd
