"""
Testes unitários e de integração para o módulo de publicidade (Ads).

Cobrem: listar campanhas, detalhes com ROAS/ACOS, dashboard agregado,
isolamento multi-tenant (IDOR), fallback quando API ML não expõe dados.

Testes unitários: cálculos de ROAS, ACOS, CPC, CTR (funções puras).
Testes de integração: SQLite in-memory com fixtures realistas em BRL.
"""
import os
import pytest
import pytest_asyncio
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from uuid import uuid4

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.database import Base


# ─────────────────────────────────────────────────────────────────────────────
# Engine SQLite in-memory — compartilhado no módulo
# ─────────────────────────────────────────────────────────────────────────────

_ads_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
_ads_session_factory = async_sessionmaker(
    bind=_ads_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="function")
async def db():
    """Sessão SQLite in-memory com todas as tabelas criadas e limpas por teste."""
    async with _ads_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with _ads_session_factory() as session:
        yield session
    async with _ads_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def user_ads(db):
    """Usuário principal de teste."""
    from app.auth.models import User
    user = User(
        id=uuid4(),
        email=f"ads_{uuid4().hex[:8]}@test.com",
        hashed_password="hashed_password",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    return user


@pytest_asyncio.fixture
async def user_outro(db):
    """Segundo usuário — para testes de isolamento IDOR."""
    from app.auth.models import User
    user = User(
        id=uuid4(),
        email=f"outro_{uuid4().hex[:8]}@test.com",
        hashed_password="hashed_password",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    return user


@pytest_asyncio.fixture
async def ml_account_ads(db, user_ads):
    """Conta ML do usuário principal."""
    from app.auth.models import MLAccount
    account = MLAccount(
        id=uuid4(),
        user_id=user_ads.id,
        ml_user_id="55443322",
        nickname="AdsAccount",
        access_token="tok_ads_test",
        refresh_token="ref_ads_test",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=6),
    )
    db.add(account)
    await db.commit()
    return account


@pytest_asyncio.fixture
async def ml_account_outro(db, user_outro):
    """Conta ML do segundo usuário — para testes de IDOR."""
    from app.auth.models import MLAccount
    account = MLAccount(
        id=uuid4(),
        user_id=user_outro.id,
        ml_user_id="99887766",
        nickname="OutroAccount",
        access_token="tok_outro_ads",
        refresh_token="ref_outro_ads",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=6),
    )
    db.add(account)
    await db.commit()
    return account


@pytest_asyncio.fixture
async def campanha_ativa(db, ml_account_ads):
    """Campanha ativa com orçamento R$50/dia."""
    from app.ads.models import AdCampaign
    campaign = AdCampaign(
        id=uuid4(),
        ml_account_id=ml_account_ads.id,
        campaign_id="CAMP-TEST-001",
        name="Campanha Ativa Teste",
        status="active",
        daily_budget=Decimal("50.00"),
        roas_target=Decimal("4.00"),
    )
    db.add(campaign)
    await db.commit()
    return campaign


@pytest_asyncio.fixture
async def campanha_pausada(db, ml_account_ads):
    """Campanha pausada com orçamento R$30/dia."""
    from app.ads.models import AdCampaign
    campaign = AdCampaign(
        id=uuid4(),
        ml_account_id=ml_account_ads.id,
        campaign_id="CAMP-TEST-002",
        name="Campanha Pausada",
        status="paused",
        daily_budget=Decimal("30.00"),
        roas_target=None,
    )
    db.add(campaign)
    await db.commit()
    return campaign


@pytest_asyncio.fixture
async def campanha_outro_usuario(db, ml_account_outro):
    """Campanha pertencente a OUTRO usuário (para teste de IDOR)."""
    from app.ads.models import AdCampaign
    campaign = AdCampaign(
        id=uuid4(),
        ml_account_id=ml_account_outro.id,
        campaign_id="CAMP-OTHER-001",
        name="Campanha Outro Usuário",
        status="active",
        daily_budget=Decimal("100.00"),
    )
    db.add(campaign)
    await db.commit()
    return campaign


@pytest_asyncio.fixture
async def snapshot_campanha(db, campanha_ativa):
    """
    Snapshot com métricas realistas:
    gasto R$150, receita R$600 → ROAS=4.0, ACOS=25%.
    """
    from app.ads.models import AdSnapshot
    snap = AdSnapshot(
        id=uuid4(),
        campaign_id=campanha_ativa.id,
        date=date.today() - timedelta(days=1),
        impressions=10000,
        clicks=200,
        spend=Decimal("150.00"),
        attributed_sales=12,
        attributed_revenue=Decimal("600.00"),
        organic_sales=5,
        roas=Decimal("4.00"),
        acos=Decimal("25.00"),
        cpc=Decimal("0.75"),
        ctr=Decimal("2.00"),
    )
    db.add(snap)
    await db.commit()
    return snap


# ─────────────────────────────────────────────────────────────────────────────
# TESTES: list_campaigns
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_lista_campanhas_da_conta_ml(db, ml_account_ads, campanha_ativa, campanha_pausada):
    """list_campaigns deve retornar todas as campanhas da conta ML."""
    from app.ads.service import list_campaigns
    campaigns = await list_campaigns(db, ml_account_ads.id)
    assert len(campaigns) == 2


@pytest.mark.asyncio
async def test_lista_campanhas_conta_sem_campanhas(db, ml_account_ads):
    """list_campaigns de conta sem campanhas deve retornar lista vazia."""
    from app.ads.service import list_campaigns
    campaigns = await list_campaigns(db, ml_account_ads.id)
    assert campaigns == []


@pytest.mark.asyncio
async def test_lista_campanhas_ordenada_por_nome(db, ml_account_ads, campanha_ativa, campanha_pausada):
    """list_campaigns deve retornar campanhas ordenadas por nome (alfabético)."""
    from app.ads.service import list_campaigns
    campaigns = await list_campaigns(db, ml_account_ads.id)
    nomes = [c.name for c in campaigns]
    assert nomes == sorted(nomes)


@pytest.mark.asyncio
async def test_lista_campanhas_filtro_por_ml_account_isola_contas(
    db, ml_account_ads, ml_account_outro, campanha_ativa, campanha_outro_usuario
):
    """list_campaigns sem user_id filtra corretamente por ml_account_id."""
    from app.ads.service import list_campaigns

    camps_conta1 = await list_campaigns(db, ml_account_ads.id)
    camps_conta2 = await list_campaigns(db, ml_account_outro.id)

    # Cada conta deve ter apenas suas campanhas
    assert all(str(c.ml_account_id) == str(ml_account_ads.id) for c in camps_conta1)
    assert all(str(c.ml_account_id) == str(ml_account_outro.id) for c in camps_conta2)


# ─────────────────────────────────────────────────────────────────────────────
# TESTES: get_campaign_detail — snapshot + ROAS/ACOS
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_detalhe_campanha_nao_encontrada_retorna_none(db):
    """Campanha inexistente deve retornar None."""
    from app.ads.service import get_campaign_detail
    result = await get_campaign_detail(db, uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_detalhe_campanha_sem_snapshots_summary_zerado(db, campanha_ativa):
    """Campanha sem snapshots: summary deve ter totais zerados e ROAS/ACOS None."""
    from app.ads.service import get_campaign_detail
    result = await get_campaign_detail(db, campanha_ativa.id)

    assert result is not None
    assert result.campaign.campaign_id == "CAMP-TEST-001"
    assert result.snapshots == []
    assert result.summary["total_spend"] == 0.0
    assert result.summary["total_revenue"] == 0.0
    assert result.summary["roas_geral"] is None
    assert result.summary["acos_geral"] is None


@pytest.mark.asyncio
async def test_detalhe_campanha_calcula_roas_4_0(db, campanha_ativa, snapshot_campanha):
    """ROAS = attributed_revenue / spend = 600 / 150 = 4.0."""
    from app.ads.service import get_campaign_detail
    result = await get_campaign_detail(db, campanha_ativa.id, days=30)

    assert result is not None
    assert len(result.snapshots) == 1
    assert result.summary["roas_geral"] == pytest.approx(4.0, rel=1e-3)


@pytest.mark.asyncio
async def test_detalhe_campanha_calcula_acos_25_pct(db, campanha_ativa, snapshot_campanha):
    """ACOS = spend / attributed_revenue * 100 = 150 / 600 * 100 = 25%."""
    from app.ads.service import get_campaign_detail
    result = await get_campaign_detail(db, campanha_ativa.id, days=30)

    assert result is not None
    assert result.summary["acos_geral"] == pytest.approx(25.0, rel=1e-3)


@pytest.mark.asyncio
async def test_detalhe_campanha_filtra_snapshots_fora_da_janela(db, campanha_ativa):
    """Snapshots fora da janela de dias não devem aparecer no resultado."""
    from app.ads.models import AdSnapshot
    from app.ads.service import get_campaign_detail

    # Snapshot de 60 dias atrás (fora de uma janela de 30 dias)
    snap_antigo = AdSnapshot(
        id=uuid4(),
        campaign_id=campanha_ativa.id,
        date=date.today() - timedelta(days=60),
        impressions=5000,
        clicks=100,
        spend=Decimal("80.00"),
        attributed_sales=5,
        attributed_revenue=Decimal("400.00"),
        organic_sales=0,
    )
    db.add(snap_antigo)
    await db.commit()

    result = await get_campaign_detail(db, campanha_ativa.id, days=30)

    assert result is not None
    # Snapshot de 60 dias atrás não deve aparecer na janela de 30 dias
    assert len(result.snapshots) == 0


# ─────────────────────────────────────────────────────────────────────────────
# TESTES: get_ads_dashboard
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dashboard_sem_campanhas_retorna_zeros(db, ml_account_ads, user_ads):
    """Dashboard sem campanhas deve retornar todos os totais zerados."""
    from app.ads.service import get_ads_dashboard
    result = await get_ads_dashboard(db, ml_account_ads.id, period=30, user_id=user_ads.id)

    assert result.total_spend == Decimal("0")
    assert result.total_revenue == Decimal("0")
    assert result.total_clicks == 0
    assert result.total_impressions == 0
    assert result.roas_geral is None
    assert result.acos_geral is None
    assert result.campaigns == []


@pytest.mark.asyncio
async def test_dashboard_agrega_spend_revenue_clicks_impressions(
    db, ml_account_ads, user_ads, campanha_ativa, snapshot_campanha
):
    """Dashboard agrega corretamente os totais de todas as campanhas."""
    from app.ads.service import get_ads_dashboard
    result = await get_ads_dashboard(db, ml_account_ads.id, period=30, user_id=user_ads.id)

    assert result.total_spend == Decimal("150.00")
    assert result.total_revenue == Decimal("600.00")
    assert result.total_clicks == 200
    assert result.total_impressions == 10000


@pytest.mark.asyncio
async def test_dashboard_calcula_roas_acos_agregados(
    db, ml_account_ads, user_ads, campanha_ativa, snapshot_campanha
):
    """ROAS e ACOS agregados calculados sobre os totais: ROAS=4.0, ACOS=25%."""
    from app.ads.service import get_ads_dashboard
    result = await get_ads_dashboard(db, ml_account_ads.id, period=30, user_id=user_ads.id)

    assert result.roas_geral is not None
    assert float(result.roas_geral) == pytest.approx(4.0, rel=1e-3)
    assert result.acos_geral is not None
    assert float(result.acos_geral) == pytest.approx(25.0, rel=1e-3)


@pytest.mark.asyncio
async def test_dashboard_inclui_todas_campanhas_da_conta(
    db, ml_account_ads, user_ads, campanha_ativa, campanha_pausada
):
    """Dashboard deve incluir lista completa de campanhas da conta."""
    from app.ads.service import get_ads_dashboard
    result = await get_ads_dashboard(db, ml_account_ads.id, period=30, user_id=user_ads.id)

    assert len(result.campaigns) == 2
    nomes = {c.name for c in result.campaigns}
    assert "Campanha Ativa Teste" in nomes
    assert "Campanha Pausada" in nomes


@pytest.mark.asyncio
async def test_dashboard_spend_zero_roas_none_fallback_gracioso(
    db, ml_account_ads, user_ads, campanha_ativa
):
    """
    Quando spend=0 (API ML não expõe dados de Product Ads),
    ROAS e ACOS devem ser None — sem divisão por zero.
    """
    from app.ads.models import AdSnapshot
    from app.ads.service import get_ads_dashboard

    snap_sem_dados = AdSnapshot(
        id=uuid4(),
        campaign_id=campanha_ativa.id,
        date=date.today() - timedelta(days=1),
        impressions=0,
        clicks=0,
        spend=Decimal("0.00"),
        attributed_sales=0,
        attributed_revenue=Decimal("0.00"),
        organic_sales=0,
    )
    db.add(snap_sem_dados)
    await db.commit()

    result = await get_ads_dashboard(db, ml_account_ads.id, period=30, user_id=user_ads.id)

    assert result.roas_geral is None
    assert result.acos_geral is None


# ─────────────────────────────────────────────────────────────────────────────
# TESTES: Isolamento multi-tenant — IDOR prevention
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_campaigns_user_id_errado_retorna_vazio(
    db, ml_account_outro, user_ads, campanha_outro_usuario
):
    """
    list_campaigns com ml_account de outro usuário + user_id correto
    deve retornar lista vazia (JOIN garante ownership).
    """
    from app.ads.service import list_campaigns

    # user_ads tenta acessar ml_account_outro (que pertence a user_outro)
    campaigns = await list_campaigns(db, ml_account_outro.id, user_id=user_ads.id)
    assert campaigns == []


@pytest.mark.asyncio
async def test_dashboard_user_id_errado_nao_vaza_dados(
    db, ml_account_outro, user_ads, campanha_outro_usuario, snapshot_campanha
):
    """
    get_ads_dashboard com ml_account de outro usuário + user_id incorreto
    deve retornar dashboard vazio — não vaza dados entre usuários.
    """
    from app.ads.service import get_ads_dashboard

    result = await get_ads_dashboard(
        db,
        ml_account_outro.id,
        period=30,
        user_id=user_ads.id,  # user_ads não é dono da ml_account_outro
    )

    assert result.total_spend == Decimal("0")
    assert result.campaigns == []


# ─────────────────────────────────────────────────────────────────────────────
# TESTES UNITÁRIOS: fórmulas de ROAS, ACOS, CPC, CTR (sem DB)
# ─────────────────────────────────────────────────────────────────────────────

def test_roas_formula_basica():
    """ROAS = attributed_revenue / spend."""
    spend = Decimal("200.00")
    revenue = Decimal("800.00")
    roas = revenue / spend
    assert roas == Decimal("4.00")


def test_acos_formula_basica():
    """ACOS = spend / attributed_revenue * 100."""
    spend = Decimal("200.00")
    revenue = Decimal("800.00")
    acos = spend / revenue * 100
    assert acos == Decimal("25.00")


def test_roas_e_acos_inversamente_relacionados():
    """ACOS = 1/ROAS * 100. Para ROAS=4.0, ACOS=25%."""
    roas = Decimal("4.00")
    acos_esperado = (1 / roas * 100).quantize(Decimal("0.01"))
    assert acos_esperado == Decimal("25.00")


def test_roas_spend_zero_retorna_none():
    """Quando spend=0, ROAS não pode ser calculado — lógica do service retorna None."""
    spend = Decimal("0")
    revenue = Decimal("500.00")
    roas = (revenue / spend) if spend > 0 else None
    assert roas is None


def test_acos_revenue_zero_retorna_none():
    """Quando attributed_revenue=0, ACOS não pode ser calculado — retorna None."""
    spend = Decimal("100.00")
    revenue = Decimal("0")
    acos = (spend / revenue * 100) if revenue > 0 else None
    assert acos is None


def test_cpc_formula():
    """CPC = spend / clicks = 150 / 200 = R$0.75."""
    spend = Decimal("150.00")
    clicks = 200
    cpc = spend / clicks
    assert cpc == Decimal("0.75")


def test_ctr_formula():
    """CTR = clicks / impressions * 100 = 200 / 10000 * 100 = 2%."""
    clicks = 200
    impressions = 10000
    ctr = Decimal(clicks) / impressions * 100
    assert ctr == Decimal("2.00")


# ─────────────────────────────────────────────────────────────────────────────
# TESTES: sync_ads_from_ml — fallback quando API ML não expõe dados
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_sem_advertiser_id_retorna_zero_campanhas(db, ml_account_ads):
    """
    Quando get_advertiser_id retorna None (API ML não pública),
    sync deve retornar vazio sem lançar exceção.
    """
    from unittest.mock import AsyncMock
    from app.ads.service import sync_ads_from_ml

    mock_client = AsyncMock()
    mock_client.get_advertiser_id.return_value = None

    result = await sync_ads_from_ml(db, mock_client, ml_account_ads)

    assert result["synced_campaigns"] == 0
    assert result["synced_snapshots"] == 0
    assert result["advertiser_id"] is None


@pytest.mark.asyncio
async def test_sync_lista_campanhas_vazia_da_api(db, ml_account_ads):
    """
    API retorna advertiser_id mas lista de campanhas vazia —
    sync deve processar sem erro (0 campanhas, 0 snapshots).
    """
    from unittest.mock import AsyncMock
    from app.ads.service import sync_ads_from_ml

    mock_client = AsyncMock()
    mock_client.get_advertiser_id.return_value = "ADV-999"
    mock_client.get_product_ads_campaigns.return_value = []

    result = await sync_ads_from_ml(db, mock_client, ml_account_ads)

    assert result["synced_campaigns"] == 0
    assert result["synced_snapshots"] == 0
    assert result["advertiser_id"] == "ADV-999"


@pytest.mark.asyncio
async def test_sync_cria_campanha_nova_no_banco(db, ml_account_ads):
    """Quando API retorna campanha nova, sync deve persistir no banco."""
    from unittest.mock import AsyncMock
    from sqlalchemy import select
    from app.ads.models import AdCampaign
    from app.ads.service import sync_ads_from_ml

    mock_client = AsyncMock()
    mock_client.get_advertiser_id.return_value = "ADV-123"
    mock_client.get_product_ads_campaigns.return_value = [
        {
            "campaign_id": "NEW-CAMP-001",
            "name": "Nova Campanha API",
            "status": "active",
            "daily_budget": 75.0,
            "metrics": {
                "prints": 5000,
                "clicks": 100,
                "cost": 50.0,
                "total_amount": 300.0,
                "units_quantity": 6,
            },
        }
    ]

    result = await sync_ads_from_ml(db, mock_client, ml_account_ads)

    assert result["synced_campaigns"] == 1
    assert result["synced_snapshots"] == 1

    # Verificar que a campanha foi criada no banco
    camp_result = await db.execute(
        select(AdCampaign).where(
            AdCampaign.ml_account_id == ml_account_ads.id,
            AdCampaign.campaign_id == "NEW-CAMP-001",
        )
    )
    campaign = camp_result.scalar_one_or_none()
    assert campaign is not None
    assert campaign.name == "Nova Campanha API"
    assert campaign.daily_budget == Decimal("75")
