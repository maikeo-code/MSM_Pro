"""
Testes para perguntas/service.py usando mocks de DB.

Cobre:
- list_questions_from_db: total=0 (empty)
- get_question_stats: zeros
- get_questions_by_listing: empty
"""
import os
import uuid
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest


def _mock_db_scalar_zero():
    """DB que retorna 0 para scalar e [] para all/fetchall."""
    db = AsyncMock()
    call_count = [0]

    async def _execute(*args, **kwargs):
        call_count[0] += 1
        result = MagicMock()
        result.scalar.return_value = 0
        result.scalar_one_or_none.return_value = None
        result.scalars.return_value.all.return_value = []
        result.all.return_value = []
        result.fetchall.return_value = []
        return result

    db.execute = _execute
    return db


# ═══════════════════════════════════════════════════════════════════════════════
# list_questions_from_db — empty
# ═══════════════════════════════════════════════════════════════════════════════


class TestListQuestionsFromDb:
    @pytest.mark.asyncio
    async def test_sem_perguntas_retorna_vazio(self):
        """DB vazio → retorna ([], 0)."""
        from app.perguntas.service import list_questions_from_db

        db = _mock_db_scalar_zero()
        user_id = uuid.uuid4()

        result_items, total = await list_questions_from_db(db=db, user_id=user_id)

        assert result_items == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_com_filtro_status(self):
        """Filtro de status funciona sem exceção."""
        from app.perguntas.service import list_questions_from_db

        db = _mock_db_scalar_zero()

        result_items, total = await list_questions_from_db(
            db=db,
            user_id=uuid.uuid4(),
            status="UNANSWERED",
        )

        assert total == 0

    @pytest.mark.asyncio
    async def test_com_filtro_ml_account_id(self):
        """Filtro de ml_account_id funciona sem exceção."""
        from app.perguntas.service import list_questions_from_db

        db = _mock_db_scalar_zero()

        result_items, total = await list_questions_from_db(
            db=db,
            user_id=uuid.uuid4(),
            ml_account_id=uuid.uuid4(),
        )

        assert total == 0

    @pytest.mark.asyncio
    async def test_com_filtro_mlb_id(self):
        """Filtro de mlb_id funciona sem exceção."""
        from app.perguntas.service import list_questions_from_db

        db = _mock_db_scalar_zero()

        result_items, total = await list_questions_from_db(
            db=db,
            user_id=uuid.uuid4(),
            mlb_id="MLB123456",
        )

        assert total == 0

    @pytest.mark.asyncio
    async def test_com_filtro_search(self):
        """Filtro de busca funciona sem exceção."""
        from app.perguntas.service import list_questions_from_db

        db = _mock_db_scalar_zero()

        result_items, total = await list_questions_from_db(
            db=db,
            user_id=uuid.uuid4(),
            search="garantia",
        )

        assert total == 0


# ═══════════════════════════════════════════════════════════════════════════════
# get_question_stats
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetQuestionStats:
    @pytest.mark.asyncio
    async def test_sem_perguntas_retorna_zeros(self):
        """DB vazio → stats com zeros."""
        from app.perguntas.service import get_question_stats

        db = _mock_db_scalar_zero()

        result = await get_question_stats(db=db, user_id=uuid.uuid4())

        assert result["total"] == 0
        assert result["unanswered"] == 0
        assert result["answered"] == 0

    @pytest.mark.asyncio
    async def test_com_ml_account_id(self):
        """ml_account_id passado → sem exceção."""
        from app.perguntas.service import get_question_stats

        db = _mock_db_scalar_zero()

        result = await get_question_stats(
            db=db,
            user_id=uuid.uuid4(),
            ml_account_id=uuid.uuid4(),
        )

        assert result["unanswered"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# get_questions_by_listing
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetQuestionsByListing:
    @pytest.mark.asyncio
    async def test_sem_perguntas_retorna_vazio(self):
        """DB vazio → retorna []."""
        from app.perguntas.service import get_questions_by_listing

        db = _mock_db_scalar_zero()

        result = await get_questions_by_listing(
            db=db,
            user_id=uuid.uuid4(),
            mlb_id="MLB123456",
        )

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_mlb_id_diferente(self):
        """Diferentes mlb_ids → sem exceção."""
        from app.perguntas.service import get_questions_by_listing

        db = _mock_db_scalar_zero()

        result = await get_questions_by_listing(
            db=db,
            user_id=uuid.uuid4(),
            mlb_id="MLB999999",
        )

        assert isinstance(result, list)
