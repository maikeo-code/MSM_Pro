import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_health_check():
    """Testa se o endpoint de health check está respondendo corretamente."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/health")
    
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "1.0.0",
        "environment": "development"
    }

@pytest.mark.asyncio
async def test_root_redirect():
    """Testa se a rota raiz responde corretamente."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/")
    
    assert response.status_code == 200
    assert "MSM_Pro API" in response.json()["message"]
