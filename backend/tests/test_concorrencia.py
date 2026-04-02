"""
Testes de integração para o módulo concorrencia.

Usa SQLite in-memory para isolar completamente o banco de dados.
Testa service.py diretamente (sem HTTP), cobrindo CRUD, ownership e lógica de negócio.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Sobrescreve DATABASE_URL antes de importar qualquer módulo da app
# (database.py cria o engine na importação com parâmetros PostgreSQL-only)
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

# --- importações de modelos (todos precisam estar registrados no metadata antes de
#     create_all — SQLAlchemy resolve relacionamentos lazy por nome de classe) ---
from app.core.database import Base
from app.auth.models import User, MLAccount, UserPreference  # noqa: F401
from app.core.models import SyncLog  # noqa: F401
from app.produtos.models import Product  # noqa: F401
from app.vendas.models import Listing, ListingSnapshot, Order, PriceChangeLog, RepricingRule  # noqa: F401
from app.concorrencia.models import Competitor, CompetitorSnapshot  # noqa: F401
from app.alertas.models import AlertConfig, AlertEvent  # noqa: F401
from app.atendimento.models import ResponseTemplate  # noqa: F401
from app.ads.models import AdCampaign, AdSnapshot  # noqa: F401
from app.financeiro.models import TaxConfig  # noqa: F401
from app.intel.models import PriceRecommendation, DailyReportLog  # noqa: F401
from app.notifications.models import UserNotification  # noqa: F401
from app.perguntas.models import Question, QuestionAnswer, QASuggestionLog  # noqa: F401
from app.reputacao.models import ReputationSnapshot  # noqa: F401

from app.concorrencia import service as svc
from app.concorrencia.schemas import CompetitorCreate


# ============================================================
# Fixtures de banco de dados in-memory
# ============================================================


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Cria um banco SQLite in-memory por teste e retorna a sessão."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ============================================================
# Helpers para criar registros de teste
# ============================================================


async def _create_user(session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="$2b$12$fakehash",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _create_ml_account(session: AsyncSession, user_id: uuid.UUID) -> MLAccount:
    account = MLAccount(
        id=uuid.uuid4(),
        user_id=user_id,
        ml_user_id="2050442871",
        nickname="MSM_PRIME",
        access_token="APP_USR-fake-access-token",
        refresh_token="TG-fake-refresh",
        is_active=True,
    )
    session.add(account)
    await session.flush()
    return account


async def _create_listing(
    session: AsyncSession,
    user_id: uuid.UUID,
    ml_account_id: uuid.UUID,
    mlb_id: str = "MLB12345678",
) -> Listing:
    listing = Listing(
        id=uuid.uuid4(),
        user_id=user_id,
        ml_account_id=ml_account_id,
        mlb_id=mlb_id,
        title="Produto de teste",
        listing_type="classico",
        price=Decimal("99.90"),
        status="active",
    )
    session.add(listing)
    await session.flush()
    return listing


async def _create_competitor(
    session: AsyncSession,
    listing_id: uuid.UUID,
    mlb_id: str = "MLB99999999",
) -> Competitor:
    comp = Competitor(
        id=uuid.uuid4(),
        listing_id=listing_id,
        mlb_id=mlb_id,
        title="Produto do Concorrente",
        seller_nickname="CONCORRENTE_STORE",
        thumbnail="https://example.com/thumb.jpg",
        is_active=True,
    )
    session.add(comp)
    await session.flush()
    return comp


async def _create_snapshot(
    session: AsyncSession,
    competitor_id: uuid.UUID,
    price: Decimal = Decimal("89.90"),
    sold_quantity: int = 100,
    sales_delta: int = 5,
    captured_at: datetime | None = None,
) -> CompetitorSnapshot:
    snap = CompetitorSnapshot(
        id=uuid.uuid4(),
        competitor_id=competitor_id,
        price=price,
        visits=50,
        sales_delta=sales_delta,
        sold_quantity=sold_quantity,
        captured_at=captured_at or datetime.now(timezone.utc),
    )
    session.add(snap)
    await session.flush()
    return snap


# ============================================================
# TESTE 1: Criar concorrente vinculado a um listing
# ============================================================


@pytest.mark.asyncio
async def test_criar_concorrente_vinculado_listing(db_session):
    """Service add_competitor cria Competitor associado ao listing correto."""
    user = await _create_user(db_session)
    account = await _create_ml_account(db_session, user.id)
    listing = await _create_listing(db_session, user.id, account.id, mlb_id="MLB11111111")

    competitor = await svc.add_competitor(
        db=db_session,
        user_id=user.id,
        listing_id=listing.id,
        competitor_mlb_id="MLB99999999",
    )

    assert competitor.id is not None
    assert competitor.listing_id == listing.id
    assert competitor.mlb_id == "MLB99999999"
    assert competitor.is_active is True


# ============================================================
# TESTE 2: Listar concorrentes de um listing
# ============================================================


@pytest.mark.asyncio
async def test_listar_concorrentes_por_listing(db_session):
    """get_competitors_by_listing retorna apenas concorrentes do listing informado."""
    user = await _create_user(db_session)
    account = await _create_ml_account(db_session, user.id)
    listing_a = await _create_listing(db_session, user.id, account.id, mlb_id="MLB10000001")
    listing_b = await _create_listing(db_session, user.id, account.id, mlb_id="MLB10000002")

    await _create_competitor(db_session, listing_a.id, mlb_id="MLB90000001")
    await _create_competitor(db_session, listing_a.id, mlb_id="MLB90000002")
    await _create_competitor(db_session, listing_b.id, mlb_id="MLB90000003")

    result = await svc.get_competitors_by_listing(
        db=db_session,
        user_id=user.id,
        listing_id=listing_a.id,
    )

    assert len(result) == 2
    mlb_ids = {c.mlb_id for c in result}
    assert "MLB90000001" in mlb_ids
    assert "MLB90000002" in mlb_ids
    assert "MLB90000003" not in mlb_ids


# ============================================================
# TESTE 3: Deletar concorrente (soft-delete)
# ============================================================


@pytest.mark.asyncio
async def test_deletar_concorrente_soft_delete(db_session):
    """remove_competitor marca is_active=False sem apagar o registro."""
    user = await _create_user(db_session)
    account = await _create_ml_account(db_session, user.id)
    listing = await _create_listing(db_session, user.id, account.id)
    comp = await _create_competitor(db_session, listing.id)

    await svc.remove_competitor(
        db=db_session,
        user_id=user.id,
        competitor_id=comp.id,
    )

    # Após remoção, listar não deve retornar o concorrente inativo
    result = await svc.get_competitors_by_listing(
        db=db_session,
        user_id=user.id,
        listing_id=listing.id,
    )
    assert len(result) == 0

    # Mas o objeto em memória ainda existe (soft-delete)
    assert comp.is_active is False


# ============================================================
# TESTE 4: Histórico de preço do concorrente
# ============================================================


@pytest.mark.asyncio
async def test_historico_preco_concorrente(db_session):
    """get_competitor_history retorna snapshots ordenados por data."""
    user = await _create_user(db_session)
    account = await _create_ml_account(db_session, user.id)
    listing = await _create_listing(db_session, user.id, account.id)
    comp = await _create_competitor(db_session, listing.id)

    now = datetime.now(timezone.utc)
    await _create_snapshot(db_session, comp.id, price=Decimal("100.00"), captured_at=now - timedelta(days=2))
    await _create_snapshot(db_session, comp.id, price=Decimal("95.00"), captured_at=now - timedelta(days=1))
    await _create_snapshot(db_session, comp.id, price=Decimal("90.00"), captured_at=now)

    history_out = await svc.get_competitor_history(
        db=db_session,
        user_id=user.id,
        competitor_id=comp.id,
        days=30,
    )

    assert history_out.competitor_id == comp.id
    assert history_out.mlb_id == comp.mlb_id
    assert len(history_out.history) == 3
    # Deve estar ordenado do mais antigo para o mais recente
    prices = [item.price for item in history_out.history]
    assert prices == [Decimal("100.00"), Decimal("95.00"), Decimal("90.00")]


# ============================================================
# TESTE 5: sold_quantity tracking — delta de vendas
# ============================================================


@pytest.mark.asyncio
async def test_sold_quantity_tracking_delta(db_session):
    """CompetitorSnapshot armazena sold_quantity acumulado e sales_delta corretamente."""
    user = await _create_user(db_session)
    account = await _create_ml_account(db_session, user.id)
    listing = await _create_listing(db_session, user.id, account.id)
    comp = await _create_competitor(db_session, listing.id)

    now = datetime.now(timezone.utc)
    snap1 = await _create_snapshot(
        db_session, comp.id,
        sold_quantity=100, sales_delta=0,
        captured_at=now - timedelta(days=1),
    )
    snap2 = await _create_snapshot(
        db_session, comp.id,
        sold_quantity=115, sales_delta=15,
        captured_at=now,
    )

    history = await svc.get_competitor_history(
        db=db_session,
        user_id=user.id,
        competitor_id=comp.id,
        days=7,
    )

    assert len(history.history) == 2
    assert history.history[0].sold_quantity == 100
    assert history.history[0].sales_delta == 0
    assert history.history[1].sold_quantity == 115
    assert history.history[1].sales_delta == 15


# ============================================================
# TESTE 6: Concorrente de outro usuário não acessível
# ============================================================


@pytest.mark.asyncio
async def test_concorrente_outro_usuario_nao_acessivel(db_session):
    """Usuário B não pode ver nem deletar concorrente do usuário A."""
    user_a = await _create_user(db_session)
    user_b = await _create_user(db_session)
    account_a = await _create_ml_account(db_session, user_a.id)
    listing_a = await _create_listing(db_session, user_a.id, account_a.id, mlb_id="MLB20000001")
    comp = await _create_competitor(db_session, listing_a.id, mlb_id="MLB80000001")

    # Usuário B tenta listar concorrentes do listing de A
    with pytest.raises(HTTPException) as exc_info:
        await svc.get_competitors_by_listing(
            db=db_session,
            user_id=user_b.id,
            listing_id=listing_a.id,
        )
    assert exc_info.value.status_code == 404

    # Usuário B tenta deletar o concorrente de A
    with pytest.raises(HTTPException) as exc_info:
        await svc.remove_competitor(
            db=db_session,
            user_id=user_b.id,
            competitor_id=comp.id,
        )
    assert exc_info.value.status_code == 404


# ============================================================
# TESTE 7: Normalização de MLB ID (com traço)
# ============================================================


@pytest.mark.asyncio
async def test_normalizacao_mlb_id_com_traco(db_session):
    """add_competitor normaliza 'MLB-99999999' para 'MLB99999999'."""
    user = await _create_user(db_session)
    account = await _create_ml_account(db_session, user.id)
    listing = await _create_listing(db_session, user.id, account.id)

    comp = await svc.add_competitor(
        db=db_session,
        user_id=user.id,
        listing_id=listing.id,
        competitor_mlb_id="MLB-12345678",
    )

    assert comp.mlb_id == "MLB12345678"


# ============================================================
# TESTE 8: Vincular MLB externo válido (prefixo MLB adicionado)
# ============================================================


@pytest.mark.asyncio
async def test_vincular_mlb_sem_prefixo_adiciona_prefixo(db_session):
    """add_competitor adiciona prefixo 'MLB' quando não fornecido."""
    user = await _create_user(db_session)
    account = await _create_ml_account(db_session, user.id)
    listing = await _create_listing(db_session, user.id, account.id)

    comp = await svc.add_competitor(
        db=db_session,
        user_id=user.id,
        listing_id=listing.id,
        competitor_mlb_id="12345678",
    )

    assert comp.mlb_id.startswith("MLB")


# ============================================================
# TESTE 9: Concorrente duplicado retorna 409
# ============================================================


@pytest.mark.asyncio
async def test_concorrente_duplicado_retorna_409(db_session):
    """Adicionar o mesmo MLB duas vezes ao mesmo listing retorna HTTP 409."""
    user = await _create_user(db_session)
    account = await _create_ml_account(db_session, user.id)
    listing = await _create_listing(db_session, user.id, account.id)

    await svc.add_competitor(
        db=db_session,
        user_id=user.id,
        listing_id=listing.id,
        competitor_mlb_id="MLB77777777",
    )

    with pytest.raises(HTTPException) as exc_info:
        await svc.add_competitor(
            db=db_session,
            user_id=user.id,
            listing_id=listing.id,
            competitor_mlb_id="MLB77777777",
        )
    assert exc_info.value.status_code == 409


# ============================================================
# TESTE 10: Listing não encontrado ao adicionar concorrente
# ============================================================


@pytest.mark.asyncio
async def test_listing_inexistente_retorna_404(db_session):
    """Tentar vincular concorrente a listing inexistente retorna HTTP 404."""
    user = await _create_user(db_session)
    fake_listing_id = uuid.uuid4()

    with pytest.raises(HTTPException) as exc_info:
        await svc.add_competitor(
            db=db_session,
            user_id=user.id,
            listing_id=fake_listing_id,
            competitor_mlb_id="MLB55555555",
        )
    assert exc_info.value.status_code == 404


# ============================================================
# TESTE 11: Concorrente com preço zerado é armazenado
# ============================================================


@pytest.mark.asyncio
async def test_snapshot_com_preco_zerado(db_session):
    """CompetitorSnapshot aceita preço zero sem erro."""
    user = await _create_user(db_session)
    account = await _create_ml_account(db_session, user.id)
    listing = await _create_listing(db_session, user.id, account.id)
    comp = await _create_competitor(db_session, listing.id)

    snap = await _create_snapshot(
        db_session, comp.id,
        price=Decimal("0.00"),
        sold_quantity=0,
        sales_delta=0,
    )

    assert snap.price == Decimal("0.00")
    assert snap.sold_quantity == 0


# ============================================================
# TESTE 12: Comparativo meu preço vs concorrente (via histórico)
# ============================================================


@pytest.mark.asyncio
async def test_comparativo_preco_meu_vs_concorrente(db_session):
    """Histórico do concorrente permite comparar preços ao longo do tempo."""
    user = await _create_user(db_session)
    account = await _create_ml_account(db_session, user.id)
    # Meu listing com preço R$100
    listing = await _create_listing(db_session, user.id, account.id)
    listing.price = Decimal("100.00")
    await db_session.flush()

    comp = await _create_competitor(db_session, listing.id, mlb_id="MLB66666666")

    now = datetime.now(timezone.utc)
    await _create_snapshot(db_session, comp.id, price=Decimal("85.00"), captured_at=now - timedelta(days=1))
    await _create_snapshot(db_session, comp.id, price=Decimal("82.00"), captured_at=now)

    history = await svc.get_competitor_history(
        db=db_session,
        user_id=user.id,
        competitor_id=comp.id,
        days=7,
    )

    assert len(history.history) == 2
    # Concorrente está abaixo do meu preço em ambos os snapshots
    for item in history.history:
        assert item.price < listing.price


# ============================================================
# TESTE 13: Histórico limitado por janela de dias
# ============================================================


@pytest.mark.asyncio
async def test_historico_limitado_por_janela_dias(db_session):
    """get_competitor_history com days=7 exclui snapshots mais antigos."""
    user = await _create_user(db_session)
    account = await _create_ml_account(db_session, user.id)
    listing = await _create_listing(db_session, user.id, account.id)
    comp = await _create_competitor(db_session, listing.id)

    now = datetime.now(timezone.utc)
    # Snapshot de 30 dias atrás — deve ser excluído
    await _create_snapshot(db_session, comp.id, price=Decimal("120.00"), captured_at=now - timedelta(days=30))
    # Snapshots recentes — devem aparecer
    await _create_snapshot(db_session, comp.id, price=Decimal("100.00"), captured_at=now - timedelta(days=5))
    await _create_snapshot(db_session, comp.id, price=Decimal("95.00"), captured_at=now - timedelta(days=1))

    history = await svc.get_competitor_history(
        db=db_session,
        user_id=user.id,
        competitor_id=comp.id,
        days=7,
    )

    assert len(history.history) == 2
    prices = {item.price for item in history.history}
    assert Decimal("120.00") not in prices


# ============================================================
# TESTE 14: get_all_competitors lista apenas concorrentes ativos do usuário
# ============================================================


@pytest.mark.asyncio
async def test_get_all_competitors_filtra_por_usuario(db_session):
    """get_all_competitors não retorna concorrentes de outros usuários."""
    user_a = await _create_user(db_session)
    user_b = await _create_user(db_session)
    account_a = await _create_ml_account(db_session, user_a.id)
    account_b = await _create_ml_account(db_session, user_b.id)
    listing_a = await _create_listing(db_session, user_a.id, account_a.id, mlb_id="MLB30000001")
    listing_b = await _create_listing(db_session, user_b.id, account_b.id, mlb_id="MLB30000002")

    await _create_competitor(db_session, listing_a.id, mlb_id="MLB40000001")
    await _create_competitor(db_session, listing_b.id, mlb_id="MLB40000002")

    result_a = await svc.get_all_competitors(db=db_session, user_id=user_a.id)
    result_b = await svc.get_all_competitors(db=db_session, user_id=user_b.id)

    assert len(result_a) == 1
    assert result_a[0].mlb_id == "MLB40000001"
    assert len(result_b) == 1
    assert result_b[0].mlb_id == "MLB40000002"
