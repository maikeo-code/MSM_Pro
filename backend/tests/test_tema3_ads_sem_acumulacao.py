"""
Tema 3 — Ads dashboard nao deve mais acumular dados duplicados.

Problema original: a API ML de Product Ads v2 retorna metricas ja
agregadas por periodo. Cada chamada de sync salva um AdSnapshot com
date=hoje contendo totais de 30 dias. Codigo antigo somava TODOS os
snapshots dos ultimos N dias, multiplicando valores (se havia 7 syncs
na semana, o spend aparecia 7x maior).

Correcao: usar o snapshot MAIS RECENTE por campanha.
"""
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.database import Base


_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
_factory = async_sessionmaker(bind=_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="function")
async def db():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with _factory() as session:
        yield session
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def setup_user_and_account(db):
    from app.auth.models import MLAccount, User
    user = User(
        id=uuid4(),
        email=f"ads_t3_{uuid4().hex[:8]}@test.com",
        hashed_password="x",
        is_active=True,
    )
    db.add(user)
    account = MLAccount(
        id=uuid4(),
        user_id=user.id,
        ml_user_id="1234567",
        nickname="T3",
        access_token="t", refresh_token="r",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=6),
    )
    db.add(account)
    await db.commit()
    return user, account


@pytest_asyncio.fixture
async def campanha(db, setup_user_and_account):
    from app.ads.models import AdCampaign
    _, account = setup_user_and_account
    c = AdCampaign(
        id=uuid4(),
        ml_account_id=account.id,
        campaign_id="CAMP-T3",
        name="Campanha Tema 3",
        status="active",
        daily_budget=Decimal("50.00"),
    )
    db.add(c)
    await db.commit()
    return c


# ─── Bug regression: multiplos snapshots do mesmo periodo ───────────────────

@pytest.mark.asyncio
async def test_dashboard_nao_duplica_snapshots_diarios_do_mesmo_periodo(
    db, setup_user_and_account, campanha
):
    """
    Simula o cenario real: varios snapshots salvos em dias consecutivos,
    cada um com dados ACUMULADOS. O dashboard nao pode somar todos.
    """
    from app.ads.models import AdSnapshot
    from app.ads.service import get_ads_dashboard

    user, account = setup_user_and_account

    # 7 snapshots — um por dia, cada um com o mesmo valor acumulado
    # (simulando que a cada sync diario a API ML retornou os mesmos 30d)
    hoje = date.today()
    for offset in range(7):
        db.add(AdSnapshot(
            id=uuid4(),
            campaign_id=campanha.id,
            date=hoje - timedelta(days=offset),
            impressions=10000,
            clicks=200,
            spend=Decimal("150.00"),
            attributed_sales=12,
            attributed_revenue=Decimal("600.00"),
            organic_sales=5,
        ))
    await db.commit()

    result = await get_ads_dashboard(db, account.id, period=30, user_id=user.id)

    # Correcao: valores nao devem multiplicar por 7
    # Valor esperado do snapshot mais recente = spend 150, revenue 600
    assert result.total_spend == Decimal("150.00"), (
        f"Bug: dashboard somou 7 snapshots acumulados (valor={result.total_spend})"
    )
    assert result.total_revenue == Decimal("600.00")
    assert result.total_clicks == 200
    assert result.total_impressions == 10000


@pytest.mark.asyncio
async def test_dashboard_usa_snapshot_mais_recente(
    db, setup_user_and_account, campanha
):
    """Quando ha varios snapshots, usa o mais recente (date maior)."""
    from app.ads.models import AdSnapshot
    from app.ads.service import get_ads_dashboard

    user, account = setup_user_and_account

    # Snapshot antigo com valores baixos
    db.add(AdSnapshot(
        id=uuid4(),
        campaign_id=campanha.id,
        date=date.today() - timedelta(days=5),
        impressions=1000,
        clicks=10,
        spend=Decimal("20.00"),
        attributed_sales=1,
        attributed_revenue=Decimal("50.00"),
        organic_sales=0,
    ))
    # Snapshot mais recente com valores atualizados
    db.add(AdSnapshot(
        id=uuid4(),
        campaign_id=campanha.id,
        date=date.today(),
        impressions=15000,
        clicks=300,
        spend=Decimal("250.00"),
        attributed_sales=25,
        attributed_revenue=Decimal("1200.00"),
        organic_sales=3,
    ))
    await db.commit()

    result = await get_ads_dashboard(db, account.id, period=30, user_id=user.id)

    # Deve usar o snapshot mais recente, nao somar
    assert result.total_spend == Decimal("250.00")
    assert result.total_revenue == Decimal("1200.00")
    assert result.total_clicks == 300
    assert result.total_impressions == 15000


@pytest.mark.asyncio
async def test_dashboard_varias_campanhas_cada_uma_seu_mais_recente(
    db, setup_user_and_account
):
    """
    Com N campanhas, o dashboard usa o mais recente de CADA uma,
    e soma entre campanhas (mas nao dentro da mesma campanha).
    """
    from app.ads.models import AdCampaign, AdSnapshot
    from app.ads.service import get_ads_dashboard

    user, account = setup_user_and_account

    # 2 campanhas, cada uma com 3 snapshots
    campanhas = []
    for i in range(2):
        c = AdCampaign(
            id=uuid4(),
            ml_account_id=account.id,
            campaign_id=f"CAMP-{i}",
            name=f"Camp {i}",
            status="active",
            daily_budget=Decimal("30.00"),
        )
        db.add(c)
        campanhas.append(c)
    await db.flush()

    for c in campanhas:
        for offset in range(3):
            db.add(AdSnapshot(
                id=uuid4(),
                campaign_id=c.id,
                date=date.today() - timedelta(days=offset),
                impressions=1000,
                clicks=20,
                spend=Decimal("100.00"),  # valor acumulado por campanha
                attributed_sales=2,
                attributed_revenue=Decimal("400.00"),
                organic_sales=0,
            ))
    await db.commit()

    result = await get_ads_dashboard(db, account.id, period=30, user_id=user.id)

    # 2 campanhas x 100 (mais recente de cada) = 200
    # NAO 2 x 3 x 100 = 600 (bug antigo)
    assert result.total_spend == Decimal("200.00"), (
        f"Esperava soma de 2 campanhas (200), recebeu {result.total_spend}"
    )
    assert result.total_revenue == Decimal("800.00")
    assert result.total_clicks == 40  # 20 + 20
    assert result.total_impressions == 2000


@pytest.mark.asyncio
async def test_dashboard_retorna_period_days_no_schema(
    db, setup_user_and_account, campanha
):
    """O dashboard deve expor o periodo consultado (nao confundir usuario)."""
    from app.ads.service import get_ads_dashboard

    user, account = setup_user_and_account
    result = await get_ads_dashboard(db, account.id, period=15, user_id=user.id)
    assert result.period_days == 15

    result2 = await get_ads_dashboard(db, account.id, period=7, user_id=user.id)
    assert result2.period_days == 7


@pytest.mark.asyncio
async def test_detail_summary_usa_snapshot_mais_recente(
    db, setup_user_and_account, campanha
):
    """get_campaign_detail.summary tambem deve usar o snapshot mais recente."""
    from app.ads.models import AdSnapshot
    from app.ads.service import get_campaign_detail

    for offset in range(5):
        db.add(AdSnapshot(
            id=uuid4(),
            campaign_id=campanha.id,
            date=date.today() - timedelta(days=offset),
            impressions=5000 + offset * 100,
            clicks=100,
            spend=Decimal("80.00"),
            attributed_sales=10,
            attributed_revenue=Decimal("400.00"),
            organic_sales=0,
        ))
    await db.commit()

    result = await get_campaign_detail(db, campanha.id, days=30)
    assert result is not None

    # Summary usa o ultimo (mais recente) snapshot, nao soma dos 5
    assert result.summary["total_spend"] == 80.0  # nao 400.0
    assert result.summary["total_revenue"] == 400.0  # nao 2000.0
    assert "latest_snapshot_date" in result.summary


@pytest.mark.asyncio
async def test_dashboard_sem_campanhas_retorna_period_days(
    db, setup_user_and_account
):
    """Dashboard sem campanhas ainda retorna period_days coerente."""
    from app.ads.service import get_ads_dashboard
    user, account = setup_user_and_account
    result = await get_ads_dashboard(db, account.id, period=30, user_id=user.id)
    assert result.period_days == 30
    assert result.total_spend == Decimal("0")
