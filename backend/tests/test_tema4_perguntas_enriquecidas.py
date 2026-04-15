"""
Tema 4 — Perguntas Q&A enriquecidas com thumbnail/permalink do Listing.

Valida:
1. Schema QuestionDB aceita item_thumbnail e item_permalink
2. list_questions_from_db retorna dicts enriquecidos via JOIN com Listing
3. get_questions_by_listing tambem retorna dicts enriquecidos
4. Se nao ha Listing correspondente, fields ficam None (outer join)
"""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.perguntas.schemas import QuestionDB


# ─── Schema ─────────────────────────────────────────────────────────────────

def test_schema_aceita_thumbnail_e_permalink():
    """QuestionDB deve aceitar os novos campos item_thumbnail e item_permalink."""
    data = {
        "id": uuid4(),
        "ml_question_id": 1234567890,
        "ml_account_id": uuid4(),
        "mlb_id": "MLB1234567890",
        "item_title": "Fone Bluetooth",
        "item_thumbnail": "https://http2.mlstatic.com/thumb.jpg",
        "item_permalink": "https://produto.mercadolivre.com.br/MLB-1234",
        "text": "Tem disponivel?",
        "status": "UNANSWERED",
        "date_created": datetime.now(timezone.utc),
        "synced_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    q = QuestionDB(**data)
    assert q.item_thumbnail == "https://http2.mlstatic.com/thumb.jpg"
    assert q.item_permalink == "https://produto.mercadolivre.com.br/MLB-1234"
    assert q.item_title == "Fone Bluetooth"


def test_schema_thumbnail_e_permalink_podem_ser_none():
    """Quando nao ha Listing, thumbnail/permalink sao None (outer join)."""
    data = {
        "id": uuid4(),
        "ml_question_id": 1,
        "ml_account_id": uuid4(),
        "mlb_id": "MLB1",
        "text": "Tem?",
        "status": "UNANSWERED",
        "date_created": datetime.now(timezone.utc),
        "synced_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    q = QuestionDB(**data)
    assert q.item_thumbnail is None
    assert q.item_permalink is None


# ─── Integracao com list_questions_from_db ─────────────────────────────────

@pytest.mark.asyncio
async def test_list_questions_sem_listing_retorna_thumbnail_none(db):
    """
    Pergunta existe mas nao ha Listing com o mesmo mlb_id — campos
    item_thumbnail/item_permalink devem ser None (outer join).
    """
    from app.auth.models import MLAccount, User
    from app.perguntas.models import Question
    from app.perguntas.service import list_questions_from_db

    u = User(id=uuid4(), email=f"u{uuid4().hex[:8]}@t.com", hashed_password="x")
    db.add(u)
    acc = MLAccount(
        id=uuid4(), user_id=u.id, ml_user_id="1",
        nickname="T", access_token="x", refresh_token="y",
    )
    db.add(acc)
    await db.flush()

    q = Question(
        id=uuid4(),
        ml_question_id=1,
        ml_account_id=acc.id,
        mlb_id="MLB-SEM-LISTING",  # nenhum Listing tem esse mlb_id
        text="Pergunta teste",
        status="UNANSWERED",
        date_created=datetime.now(timezone.utc),
    )
    db.add(q)
    await db.commit()

    items, total = await list_questions_from_db(db, u.id)
    assert total == 1
    assert len(items) == 1
    assert items[0]["mlb_id"] == "MLB-SEM-LISTING"
    assert items[0]["item_thumbnail"] is None
    assert items[0]["item_permalink"] is None


@pytest.mark.asyncio
async def test_list_questions_com_listing_retorna_thumbnail(db):
    """
    Quando existe um Listing com mesmo mlb_id, o join traz thumbnail
    e permalink para a pergunta.
    """
    from app.auth.models import MLAccount, User
    from app.perguntas.models import Question
    from app.perguntas.service import list_questions_from_db
    from app.vendas.models import Listing

    u = User(id=uuid4(), email=f"u{uuid4().hex[:8]}@t.com", hashed_password="x")
    db.add(u)
    acc = MLAccount(
        id=uuid4(), user_id=u.id, ml_user_id="1",
        nickname="T", access_token="x", refresh_token="y",
    )
    db.add(acc)
    await db.flush()

    # Cria Listing correspondente
    listing = Listing(
        id=uuid4(),
        user_id=u.id,
        ml_account_id=acc.id,
        mlb_id="MLB-COM-LISTING",
        title="Produto Teste",
        price=Decimal("99.90"),
        status="active",
        thumbnail="https://http2.mlstatic.com/thumb.jpg",
        permalink="https://produto.mercadolivre.com.br/MLB-COM-LISTING",
    )
    db.add(listing)

    q = Question(
        id=uuid4(),
        ml_question_id=2,
        ml_account_id=acc.id,
        mlb_id="MLB-COM-LISTING",
        text="Pergunta teste",
        status="UNANSWERED",
        date_created=datetime.now(timezone.utc),
    )
    db.add(q)
    await db.commit()

    items, total = await list_questions_from_db(db, u.id)
    assert total == 1
    assert items[0]["item_thumbnail"] == "https://http2.mlstatic.com/thumb.jpg"
    assert items[0]["item_permalink"] == "https://produto.mercadolivre.com.br/MLB-COM-LISTING"
    # item_title vem do listing quando Question.item_title e None
    assert items[0]["item_title"] == "Produto Teste"


@pytest.mark.asyncio
async def test_list_questions_filtros_preservados(db):
    """Apos a refatoracao, os filtros de listagem continuam funcionando."""
    from app.auth.models import MLAccount, User
    from app.perguntas.models import Question
    from app.perguntas.service import list_questions_from_db

    u = User(id=uuid4(), email=f"u{uuid4().hex[:8]}@t.com", hashed_password="x")
    db.add(u)
    acc = MLAccount(
        id=uuid4(), user_id=u.id, ml_user_id="1",
        nickname="T", access_token="x", refresh_token="y",
    )
    db.add(acc)
    await db.flush()

    # 3 perguntas, 2 unanswered, 1 answered
    for i, s in enumerate(["UNANSWERED", "UNANSWERED", "ANSWERED"]):
        db.add(Question(
            id=uuid4(),
            ml_question_id=100 + i,
            ml_account_id=acc.id,
            mlb_id=f"MLB-{i}",
            text=f"Pergunta {i}",
            status=s,
            date_created=datetime.now(timezone.utc),
        ))
    await db.commit()

    # Filtro por status
    items, total = await list_questions_from_db(db, u.id, status="UNANSWERED")
    assert total == 2

    items, total = await list_questions_from_db(db, u.id, status="ANSWERED")
    assert total == 1


@pytest.mark.asyncio
async def test_list_questions_retorna_dicts_compativeis_com_schema(db):
    """O dict retornado deve passar no construtor de QuestionDB."""
    from app.auth.models import MLAccount, User
    from app.perguntas.models import Question
    from app.perguntas.service import list_questions_from_db

    u = User(id=uuid4(), email=f"u{uuid4().hex[:8]}@t.com", hashed_password="x")
    db.add(u)
    acc = MLAccount(
        id=uuid4(), user_id=u.id, ml_user_id="1",
        nickname="T", access_token="x", refresh_token="y",
    )
    db.add(acc)
    await db.flush()

    q = Question(
        id=uuid4(),
        ml_question_id=555,
        ml_account_id=acc.id,
        mlb_id="MLB-555",
        text="Test",
        status="UNANSWERED",
        date_created=datetime.now(timezone.utc),
    )
    db.add(q)
    await db.commit()

    items, _ = await list_questions_from_db(db, u.id)
    assert len(items) == 1
    # Deve conseguir construir QuestionDB com esses dados
    dto = QuestionDB(**items[0])
    assert dto.mlb_id == "MLB-555"
    assert dto.item_thumbnail is None


@pytest.mark.asyncio
async def test_get_questions_by_listing_retorna_dicts(db):
    """get_questions_by_listing tambem retorna dicts enriquecidos."""
    from app.auth.models import MLAccount, User
    from app.perguntas.models import Question
    from app.perguntas.service import get_questions_by_listing

    u = User(id=uuid4(), email=f"u{uuid4().hex[:8]}@t.com", hashed_password="x")
    db.add(u)
    acc = MLAccount(
        id=uuid4(), user_id=u.id, ml_user_id="1",
        nickname="T", access_token="x", refresh_token="y",
    )
    db.add(acc)
    await db.flush()

    q = Question(
        id=uuid4(),
        ml_question_id=999,
        ml_account_id=acc.id,
        mlb_id="MLB-999",
        text="Q",
        status="UNANSWERED",
        date_created=datetime.now(timezone.utc),
    )
    db.add(q)
    await db.commit()

    items = await get_questions_by_listing(db, u.id, "MLB-999")
    assert len(items) == 1
    assert isinstance(items[0], dict)
    assert items[0]["mlb_id"] == "MLB-999"
    assert "item_thumbnail" in items[0]
    assert "item_permalink" in items[0]
