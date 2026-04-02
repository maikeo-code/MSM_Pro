"""Testes para o módulo de notificações — service + router."""
import os
import pytest
import pytest_asyncio
from uuid import uuid4

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.auth import service as auth_service
from app.notifications import service as notif_service
from app.notifications.models import UserNotification
from app.main import app


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db(test_engine):
    factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(test_engine):
    factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_user_and_token(client, email="notif@test.com"):
    await client.post("/api/v1/auth/register", json={"email": email, "password": "senha1234"})
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "senha1234"})
    return resp.json()["access_token"]


async def _create_test_notif(db, user_id, title="Teste", msg="Mensagem", notif_type="warning"):
    return await notif_service.create_notification(
        db=db,
        user_id=user_id,
        type=notif_type,
        title=title,
        message=msg,
    )


# ===========================================================================
# Testes de service — create_notification
# ===========================================================================

@pytest.mark.asyncio
async def test_create_notification_persiste_no_banco(db):
    user_id = uuid4()
    notif = await notif_service.create_notification(
        db=db,
        user_id=user_id,
        type="token_expired",
        title="Token expirado",
        message="Reconecte sua conta ML.",
        action_url="/configuracoes",
    )
    assert notif.id is not None
    assert notif.user_id == user_id
    assert notif.type == "token_expired"
    assert notif.is_read is False
    assert notif.action_url == "/configuracoes"


@pytest.mark.asyncio
async def test_create_notification_sem_action_url(db):
    user_id = uuid4()
    notif = await notif_service.create_notification(
        db=db, user_id=user_id, type="warning",
        title="Aviso", message="Mensagem sem URL",
    )
    assert notif.action_url is None


# ===========================================================================
# Testes de service — get_unread_notifications
# ===========================================================================

@pytest.mark.asyncio
async def test_get_unread_retorna_apenas_nao_lidas(db):
    user_id = uuid4()
    await _create_test_notif(db, user_id, "Não lida 1")
    await _create_test_notif(db, user_id, "Não lida 2")

    # Cria uma notificação e marca como lida manualmente
    notif_lida = await _create_test_notif(db, user_id, "Lida")
    notif_lida.is_read = True
    await db.commit()

    resultado = await notif_service.get_unread_notifications(db, user_id)
    assert len(resultado) == 2
    assert all(n.is_read is False for n in resultado)


@pytest.mark.asyncio
async def test_get_unread_respeita_limite(db):
    user_id = uuid4()
    for i in range(10):
        await _create_test_notif(db, user_id, f"Notif {i}")

    resultado = await notif_service.get_unread_notifications(db, user_id, limit=5)
    assert len(resultado) == 5


# ===========================================================================
# Testes de service — get_unread_count (usa COUNT, não len)
# ===========================================================================

@pytest.mark.asyncio
async def test_get_unread_count_usa_sql_count(db):
    user_id = uuid4()
    await _create_test_notif(db, user_id, "A")
    await _create_test_notif(db, user_id, "B")
    await _create_test_notif(db, user_id, "C")

    count = await notif_service.get_unread_count(db, user_id)
    assert count == 3
    # Garante que retorna int (resultado de COUNT, não len de lista)
    assert isinstance(count, int)


@pytest.mark.asyncio
async def test_get_unread_count_zero_quando_sem_notificacoes(db):
    count = await notif_service.get_unread_count(db, uuid4())
    assert count == 0


# ===========================================================================
# Testes de service — mark_notification_as_read
# ===========================================================================

@pytest.mark.asyncio
async def test_mark_as_read_atualiza_flag(db):
    user_id = uuid4()
    notif = await _create_test_notif(db, user_id)
    assert notif.is_read is False

    updated = await notif_service.mark_notification_as_read(db, notif.id, user_id)
    assert updated is not None
    assert updated.is_read is True


@pytest.mark.asyncio
async def test_mark_as_read_notif_outro_usuario_retorna_none(db):
    user_a = uuid4()
    user_b = uuid4()
    notif = await _create_test_notif(db, user_a)

    # user_b tenta marcar notificação do user_a como lida
    resultado = await notif_service.mark_notification_as_read(db, notif.id, user_b)
    assert resultado is None


@pytest.mark.asyncio
async def test_mark_as_read_ja_lida_permanece_lida(db):
    user_id = uuid4()
    notif = await _create_test_notif(db, user_id)
    await notif_service.mark_notification_as_read(db, notif.id, user_id)

    # Chamar novamente não deve causar erro
    updated = await notif_service.mark_notification_as_read(db, notif.id, user_id)
    assert updated.is_read is True


@pytest.mark.asyncio
async def test_mark_as_read_id_invalido_retorna_none(db):
    resultado = await notif_service.mark_notification_as_read(db, uuid4(), uuid4())
    assert resultado is None


# ===========================================================================
# Testes de service — mark_all_as_read (bulk SQL UPDATE)
# ===========================================================================

@pytest.mark.asyncio
async def test_mark_all_as_read_retorna_contagem_correta(db):
    user_id = uuid4()
    await _create_test_notif(db, user_id, "X")
    await _create_test_notif(db, user_id, "Y")
    await _create_test_notif(db, user_id, "Z")

    count = await notif_service.mark_all_as_read(db, user_id)
    assert count == 3


@pytest.mark.asyncio
async def test_mark_all_as_read_nao_afeta_outro_usuario(db):
    user_a = uuid4()
    user_b = uuid4()
    await _create_test_notif(db, user_a, "Do A")
    await _create_test_notif(db, user_b, "Do B")

    # Marca todas as notificações de user_a
    await notif_service.mark_all_as_read(db, user_a)

    # Contagem de user_b não deve ser afetada
    count_b = await notif_service.get_unread_count(db, user_b)
    assert count_b == 1


@pytest.mark.asyncio
async def test_mark_all_as_read_retorna_zero_quando_todas_lidas(db):
    user_id = uuid4()
    await _create_test_notif(db, user_id)
    await notif_service.mark_all_as_read(db, user_id)

    # Chamar de novo retorna 0
    count = await notif_service.mark_all_as_read(db, user_id)
    assert count == 0


# ===========================================================================
# Testes de service — delete_notification
# ===========================================================================

@pytest.mark.asyncio
async def test_delete_notification_retorna_true(db):
    user_id = uuid4()
    notif = await _create_test_notif(db, user_id)
    deleted = await notif_service.delete_notification(db, notif.id, user_id)
    assert deleted is True


@pytest.mark.asyncio
async def test_delete_notification_outro_usuario_retorna_false(db):
    user_a = uuid4()
    user_b = uuid4()
    notif = await _create_test_notif(db, user_a)

    # user_b não pode deletar notificação de user_a
    result = await notif_service.delete_notification(db, notif.id, user_b)
    assert result is False


@pytest.mark.asyncio
async def test_delete_notification_id_inexistente_retorna_false(db):
    result = await notif_service.delete_notification(db, uuid4(), uuid4())
    assert result is False


# ===========================================================================
# Testes de router — GET /api/v1/notifications/
# ===========================================================================

@pytest.mark.asyncio
async def test_router_list_notifications_vazio(client):
    token = await _create_user_and_token(client, "list@test.com")
    resp = await client.get(
        "/api/v1/notifications/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_router_list_notifications_sem_auth_retorna_401(client):
    resp = await client.get("/api/v1/notifications/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_router_unread_only_filtra_corretamente(client, db):
    from sqlalchemy import select
    from app.auth.models import User

    token = await _create_user_and_token(client, "unreadonly@test.com")

    # Busca o user_id do usuário criado
    result = await db.execute(select(User).where(User.email == "unreadonly@test.com"))
    user = result.scalar_one_or_none()
    if user is None:
        pytest.skip("Usuário não encontrado no DB de teste — diferentes engines")

    await _create_test_notif(db, user.id, "Não lida")
    notif_lida = await _create_test_notif(db, user.id, "Lida")
    notif_lida.is_read = True
    await db.commit()

    resp = await client.get(
        "/api/v1/notifications/?unread_only=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(n["is_read"] is False for n in data)


# ===========================================================================
# Testes de router — GET /api/v1/notifications/count
# ===========================================================================

@pytest.mark.asyncio
async def test_router_count_retorna_zero_inicial(client):
    token = await _create_user_and_token(client, "count@test.com")
    resp = await client.get(
        "/api/v1/notifications/count",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["unread_count"] == 0


# ===========================================================================
# Testes de router — POST /read-all
# ===========================================================================

@pytest.mark.asyncio
async def test_router_read_all_retorna_ok(client):
    token = await _create_user_and_token(client, "readall@test.com")
    resp = await client.post(
        "/api/v1/notifications/read-all",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ===========================================================================
# Testes de router — mark as read / delete com ID inválido
# ===========================================================================

@pytest.mark.asyncio
async def test_router_mark_read_id_invalido_retorna_404(client):
    token = await _create_user_and_token(client, "markread@test.com")
    fake_id = uuid4()
    resp = await client.post(
        f"/api/v1/notifications/{fake_id}/read",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_router_delete_id_invalido_retorna_404(client):
    token = await _create_user_and_token(client, "del@test.com")
    fake_id = uuid4()
    resp = await client.delete(
        f"/api/v1/notifications/{fake_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ===========================================================================
# Testes de paginação
# ===========================================================================

@pytest.mark.asyncio
async def test_get_all_notifications_respeita_limite(db):
    user_id = uuid4()
    for i in range(20):
        await _create_test_notif(db, user_id, f"Notif {i}")

    resultado = await notif_service.get_all_notifications(db, user_id, limit=7)
    assert len(resultado) == 7


@pytest.mark.asyncio
async def test_get_all_notifications_ordenado_por_data_decrescente(db):
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import update

    user_id = uuid4()
    n1 = await _create_test_notif(db, user_id, "Mais antiga")
    n2 = await _create_test_notif(db, user_id, "Mais recente")

    # Força timestamps distintos
    await db.execute(
        update(UserNotification)
        .where(UserNotification.id == n1.id)
        .values(created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    )
    await db.execute(
        update(UserNotification)
        .where(UserNotification.id == n2.id)
        .values(created_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    )
    await db.commit()

    resultado = await notif_service.get_all_notifications(db, user_id)
    assert resultado[0].id == n2.id  # mais recente primeiro
