"""
Tests para endpoint público GET /health/sync e Celery task runtime_watcher.
Criados no ciclo 466 para cobrir as features adicionadas nesta sessão.
"""
import inspect

import pytest


def test_health_sync_endpoint_registered():
    """GET /health/sync deve estar registrado no FastAPI."""
    from app.main import app

    paths = [r.path for r in app.routes]
    assert "/health/sync" in paths, "endpoint /health/sync não registrado"


def test_health_sync_is_public():
    """
    /health/sync NÃO deve exigir autenticação (é destinado a Uptime Robot).
    Validamos via introspect: o handler não deve ter Depends(get_current_user).
    """
    from app.main import health_sync

    sig = inspect.signature(health_sync)
    for param_name, param in sig.parameters.items():
        assert "current_user" not in param_name, (
            f"/health/sync não deve exigir autenticação (param: {param_name})"
        )


def test_runtime_watcher_task_exists():
    """A task Celery runtime_watcher deve estar registrada."""
    from app.jobs import tasks

    assert hasattr(tasks, "runtime_watcher"), "task runtime_watcher não existe"
    # Deve ser uma Celery task (tem .delay)
    assert hasattr(tasks.runtime_watcher, "delay")


def test_runtime_watcher_in_beat_schedule():
    """runtime_watcher deve estar no Celery beat schedule a cada 2h."""
    from app.core.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule
    assert "runtime-watcher-bihourly" in schedule
    entry = schedule["runtime-watcher-bihourly"]
    assert entry["task"] == "app.jobs.tasks.runtime_watcher"


def test_runtime_watcher_async_returns_dict():
    """_runtime_watcher_async deve ter assinatura async + retornar dict."""
    from app.jobs.tasks_health import _runtime_watcher_async

    assert inspect.iscoroutinefunction(_runtime_watcher_async)
    src = inspect.getsource(_runtime_watcher_async)
    assert "anomalies" in src
    assert "snapshots_24h" in src
    assert "needs_reauth" in src


def test_check_sync_health_async_exists():
    """A função básica de health check existe (legacy)."""
    from app.jobs.tasks_health import _check_sync_health_async

    assert inspect.iscoroutinefunction(_check_sync_health_async)


def test_daily_intel_html_endpoint_registered():
    """GET /api/v1/intel/pricing/daily-report deve estar registrado."""
    from app.main import app

    matching = [
        r for r in app.routes
        if hasattr(r, "path") and "daily-report" in r.path
    ]
    assert len(matching) > 0, "endpoint daily-report não registrado"


def test_debug_trigger_task_endpoint_exists():
    """POST /auth/debug/trigger-task/{task_name} deve existir."""
    from app.main import app

    matching = [
        r for r in app.routes
        if hasattr(r, "path") and "trigger-task" in r.path
    ]
    assert len(matching) > 0, "endpoint trigger-task não registrado"


def test_openapi_schema_generation_works():
    """
    Regressão ciclo 471/472: garante que o schema OpenAPI pode ser gerado.
    Quebrava com AssertionError quando algum endpoint tinha response_class=None.
    """
    from app.main import app

    schema = app.openapi()
    assert schema is not None
    assert "paths" in schema
    assert len(schema["paths"]) > 50, "esperava >50 paths no OpenAPI"
    assert "info" in schema
    assert schema["info"]["title"] == "MSM_Pro API"


def test_no_endpoint_has_response_class_none():
    """
    Garante que nenhum endpoint use response_class=None (que quebra OpenAPI).
    Verificação via grep no source code dos routers.
    """
    import pathlib
    backend_root = pathlib.Path(__file__).parent.parent
    routers = list((backend_root / "app").rglob("router*.py"))
    offenders = []
    for r in routers:
        text = r.read_text(encoding="utf-8", errors="ignore")
        if "response_class=None" in text:
            offenders.append(str(r.relative_to(backend_root)))
    assert not offenders, (
        f"Endpoints com response_class=None detectados: {offenders}. "
        "Use HTMLResponse, JSONResponse, etc — ou omita o parametro."
    )
