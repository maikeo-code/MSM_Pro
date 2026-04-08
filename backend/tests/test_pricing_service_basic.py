"""
Smoke tests para intel/pricing/service.py — era 0% coverage.
Criado no ciclo 485.
"""
import pytest
from app.intel.pricing.service import _simple_reasoning


def test_simple_reasoning_increase():
    rec = {"action": "increase", "price_change_pct": 5.0}
    txt = _simple_reasoning(rec)
    assert "aumento" in txt.lower()
    assert "5.0%" in txt


def test_simple_reasoning_decrease():
    rec = {"action": "decrease", "price_change_pct": -3.5}
    txt = _simple_reasoning(rec)
    assert "redu" in txt.lower()
    assert "3.5%" in txt


def test_simple_reasoning_hold():
    rec = {"action": "hold", "price_change_pct": 0}
    txt = _simple_reasoning(rec)
    assert "manter" in txt.lower() or "estav" in txt.lower()


def test_simple_reasoning_default_action():
    rec = {}  # nenhum action -> hold
    txt = _simple_reasoning(rec)
    assert isinstance(txt, str)
    assert len(txt) > 0


@pytest.mark.asyncio
async def test_generate_price_recommendations_no_data(db):
    """Sem listings, generate_price_recommendations retorna 0."""
    from uuid import uuid4
    from app.auth.models import User
    from app.intel.pricing.service import generate_price_recommendations

    user = User(id=uuid4(), email="px@t.com", hashed_password="x")
    db.add(user)
    await db.commit()

    result = await generate_price_recommendations(db, user.id)
    assert result == 0
