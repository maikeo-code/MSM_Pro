"""
Testes para perguntas/context_collector.py.

Cobre:
- collect_context: caminho principal com mocks
- _get_historical_qa: DB retorna vazio
- _get_item_info: ML API sucesso, ML API falha
"""
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest


# ─── Helpers ────────────────────────────────────────────────────────────────


def _make_question(mlb_id="MLB123456", item_title="Produto Teste", question_id=None):
    q = MagicMock()
    q.id = question_id or uuid.uuid4()
    q.mlb_id = mlb_id
    q.item_title = item_title
    q.text = "Tem em estoque?"
    q.status = "UNANSWERED"
    return q


def _mock_db_empty():
    db = AsyncMock()

    async def _execute(*args, **kwargs):
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        result.all.return_value = []
        return result

    db.execute = _execute
    return db


def _make_ml_client(item_data=None, description_data=None):
    """Cria MLClient mockado."""
    client = AsyncMock()
    client.get_item = AsyncMock(return_value=item_data or {
        "title": "Produto Incrível",
        "attributes": [
            {"name": "Cor", "value_name": "Azul"},
            {"name": "Material", "value_name": "Algodão"},
        ],
    })
    client._request = AsyncMock(return_value=description_data or {
        "plain_text": "Descrição completa do produto.",
        "text": "",
    })
    return client


# ═══════════════════════════════════════════════════════════════════════════════
# _get_historical_qa
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetHistoricalQA:
    """Testa _get_historical_qa."""

    @pytest.mark.asyncio
    async def test_sem_perguntas_anteriores_retorna_vazio(self):
        """DB vazio → retorna []."""
        from app.perguntas.context_collector import _get_historical_qa

        db = _mock_db_empty()
        question = _make_question()

        result = await _get_historical_qa(db, question)
        assert result == []

    @pytest.mark.asyncio
    async def test_com_perguntas_respondidas(self):
        """DB com perguntas respondidas → retorna lista de dicts."""
        from app.perguntas.context_collector import _get_historical_qa

        answered_q = MagicMock()
        answered_q.text = "O produto é resistente?"
        answered_q.answer_text = "Sim, é muito resistente."

        db = AsyncMock()

        async def _execute(*args, **kwargs):
            result = MagicMock()
            result.scalars.return_value.all.return_value = [answered_q]
            return result

        db.execute = _execute
        question = _make_question()

        result = await _get_historical_qa(db, question)

        assert len(result) == 1
        assert result[0]["pergunta"] == "O produto é resistente?"
        assert result[0]["resposta"] == "Sim, é muito resistente."


# ═══════════════════════════════════════════════════════════════════════════════
# _get_item_info
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetItemInfo:
    """Testa _get_item_info."""

    @pytest.mark.asyncio
    async def test_sucesso_retorna_info_completa(self):
        """API ML retorna dados → dict com título, descrição, atributos."""
        from app.perguntas.context_collector import _get_item_info

        client = _make_ml_client()

        result = await _get_item_info(client, "MLB123456", "fallback title")

        assert result["title"] == "Produto Incrível"
        assert result["description"] == "Descrição completa do produto."
        assert "Cor: Azul" in result["attributes"]
        assert "Material: Algodão" in result["attributes"]

    @pytest.mark.asyncio
    async def test_item_sem_titulo_usa_fallback(self):
        """Item sem title → usa title_fallback."""
        from app.perguntas.context_collector import _get_item_info

        client = AsyncMock()
        client.get_item = AsyncMock(return_value={
            "title": "",  # vazio
            "attributes": [],
        })
        client._request = AsyncMock(return_value={"plain_text": "", "text": ""})

        result = await _get_item_info(client, "MLB000", "Fallback Title")
        assert result["title"] == "Fallback Title"

    @pytest.mark.asyncio
    async def test_descricao_via_texto_alternativo(self):
        """Quando plain_text vazio, usa text."""
        from app.perguntas.context_collector import _get_item_info

        client = AsyncMock()
        client.get_item = AsyncMock(return_value={"title": "Item X", "attributes": []})
        client._request = AsyncMock(return_value={"plain_text": "", "text": "Texto aqui."})

        result = await _get_item_info(client, "MLB111", "")
        assert result["description"] == "Texto aqui."

    @pytest.mark.asyncio
    async def test_descricao_request_falha_retorna_vazio(self):
        """Falha ao buscar descrição → description='', sem exceção."""
        from app.perguntas.context_collector import _get_item_info

        client = AsyncMock()
        client.get_item = AsyncMock(return_value={"title": "Item Y", "attributes": []})
        client._request = AsyncMock(side_effect=Exception("API error"))

        result = await _get_item_info(client, "MLB222", "")
        assert result["description"] == ""
        assert result["title"] == "Item Y"

    @pytest.mark.asyncio
    async def test_get_item_falha_retorna_fallback(self):
        """get_item falha → retorna dict com fallback title."""
        from app.perguntas.context_collector import _get_item_info

        client = AsyncMock()
        client.get_item = AsyncMock(side_effect=Exception("network error"))

        result = await _get_item_info(client, "MLB333", "Produto X")
        assert result["title"] == "Produto X"
        assert result["description"] == ""
        assert result["attributes"] == []

    @pytest.mark.asyncio
    async def test_atributos_sem_nome_ou_valor_ignorados(self):
        """Atributos sem name ou value_name são ignorados."""
        from app.perguntas.context_collector import _get_item_info

        client = AsyncMock()
        client.get_item = AsyncMock(return_value={
            "title": "Item Z",
            "attributes": [
                {"name": "Cor", "value_name": ""},   # value_name vazio → ignorado
                {"name": "", "value_name": "Azul"},  # name vazio → ignorado
                {"name": "Tamanho", "value_name": "M"},  # válido
            ],
        })
        client._request = AsyncMock(return_value={"plain_text": "", "text": ""})

        result = await _get_item_info(client, "MLB444", "")
        assert result["attributes"] == ["Tamanho: M"]


# ═══════════════════════════════════════════════════════════════════════════════
# collect_context — integração
# ═══════════════════════════════════════════════════════════════════════════════


class TestCollectContext:
    """Testa collect_context (usa gather em paralelo)."""

    @pytest.mark.asyncio
    async def test_retorna_estrutura_correta(self):
        """collect_context retorna dict com as 4 chaves esperadas."""
        from app.perguntas.context_collector import collect_context

        db = _mock_db_empty()
        client = _make_ml_client()
        question = _make_question()

        result = await collect_context(db=db, question=question, client=client)

        assert "historical_qa" in result
        assert "item_description" in result
        assert "item_attributes" in result
        assert "item_title" in result

    @pytest.mark.asyncio
    async def test_com_excecao_em_gather_usa_fallback(self):
        """Se um dos gather lançar exceção, usa fallback ([] ou {})."""
        from app.perguntas.context_collector import collect_context

        db = _mock_db_empty()
        client = AsyncMock()
        client.get_item = AsyncMock(side_effect=Exception("API down"))
        question = _make_question()

        result = await collect_context(db=db, question=question, client=client)

        # Deve retornar o fallback, não propagar exceção
        assert result["item_description"] == ""
        assert result["item_attributes"] == []
