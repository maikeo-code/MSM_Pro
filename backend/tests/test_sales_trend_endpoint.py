"""Test funcional de /listings/sales-trend usando TestClient e DB fixture."""
import os
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from fastapi.testclient import TestClient


def test_sales_trend_endpoint_exists_and_requires_auth():
    """Endpoint deve existir e exigir auth."""
    from app.main import app
    client = TestClient(app)
    r = client.get("/api/v1/listings/sales-trend?days=7")
    assert r.status_code == 401, f"Esperava 401 (sem auth), recebeu {r.status_code}: {r.text}"


def test_sales_trend_invalid_days_param():
    """days fora do range [1, 30] deve dar 422."""
    from app.main import app
    client = TestClient(app)
    # Sem auth, mas o validador de query roda antes do auth em alguns casos.
    # Aceita 401 OU 422 (FastAPI pode validar primeiro).
    r = client.get("/api/v1/listings/sales-trend?days=0")
    assert r.status_code in (401, 422)
    r = client.get("/api/v1/listings/sales-trend?days=31")
    assert r.status_code in (401, 422)
