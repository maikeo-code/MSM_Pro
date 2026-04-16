"""
Testes para atendimento/service.py usando mocks de DB e MLClient.

Cobre:
- get_all_atendimentos: caminho com zero contas ativas
- get_atendimento_stats: chama get_all_atendimentos, então mock indireto
- respond_to_item: conta não encontrada → ValueError, tipo inválido → ValueError
"""
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest


# ─── Helpers ────────────────────────────────────────────────────────────────


def _make_user(user_id=None):
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.email = "test@example.com"
    return user


def _mock_db_no_accounts():
    """DB que retorna lista vazia na primeira execução (nenhuma conta ML)."""
    db = AsyncMock()

    async def _execute(*args, **kwargs):
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        result.all.return_value = []
        result.scalar_one_or_none.return_value = None
        result.fetchall.return_value = []
        return result

    db.execute = _execute
    return db


def _mock_db_with_account(account):
    """DB que retorna uma conta na query de contas, None nas demais."""
    db = AsyncMock()
    call_count = [0]

    async def _execute(*args, **kwargs):
        call_count[0] += 1
        result = MagicMock()
        if call_count[0] == 1:
            result.scalars.return_value.all.return_value = [account]
            result.scalar_one_or_none.return_value = account
        else:
            result.scalars.return_value.all.return_value = []
            result.scalar_one_or_none.return_value = None
        result.all.return_value = []
        result.fetchall.return_value = []
        return result

    db.execute = _execute
    return db


def _mock_db_no_ml_account():
    """DB que retorna None para scalar_one_or_none (conta não encontrada)."""
    db = AsyncMock()

    async def _execute(*args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        result.scalars.return_value.all.return_value = []
        result.all.return_value = []
        return result

    db.execute = _execute
    return db


def _mock_db_with_ml_account_no_token():
    """DB que retorna uma conta sem access_token."""
    account = MagicMock()
    account.access_token = None
    account.id = uuid.uuid4()

    db = AsyncMock()

    async def _execute(*args, **kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = account
        result.scalars.return_value.all.return_value = []
        result.all.return_value = []
        return result

    db.execute = _execute
    return db


# ═══════════════════════════════════════════════════════════════════════════════
# get_all_atendimentos — zero contas ativas
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetAllAtendimentosZeroContas:
    """Testa get_all_atendimentos quando não há contas ML ativas."""

    @pytest.mark.asyncio
    async def test_sem_contas_retorna_lista_vazia(self):
        """Zero contas ML → lista vazia com contadores zerados."""
        from app.atendimento.service import get_all_atendimentos

        user = _make_user()
        db = _mock_db_no_accounts()

        result = await get_all_atendimentos(db=db, user=user)

        assert result.total == 0
        assert result.items == []
        assert result.by_type["perguntas"] == 0
        assert result.by_type["reclamacoes"] == 0
        assert result.by_type["mensagens"] == 0
        assert result.by_type["devolucoes"] == 0

    @pytest.mark.asyncio
    async def test_sem_contas_com_type_filter(self):
        """type_filter='pergunta' com zero contas → lista vazia."""
        from app.atendimento.service import get_all_atendimentos

        user = _make_user()
        db = _mock_db_no_accounts()

        result = await get_all_atendimentos(
            db=db, user=user, type_filter="pergunta"
        )

        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_sem_contas_com_status_filter(self):
        """status_filter='open' com zero contas → lista vazia."""
        from app.atendimento.service import get_all_atendimentos

        user = _make_user()
        db = _mock_db_no_accounts()

        result = await get_all_atendimentos(
            db=db, user=user, status_filter="open"
        )

        assert result.total == 0

    @pytest.mark.asyncio
    async def test_sem_contas_paginacao_offset(self):
        """Offset/limit com zero contas não quebra."""
        from app.atendimento.service import get_all_atendimentos

        user = _make_user()
        db = _mock_db_no_accounts()

        result = await get_all_atendimentos(
            db=db, user=user, offset=10, limit=5
        )

        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_sem_contas_type_mensagem(self):
        """type_filter='mensagem' com zero contas → lista vazia."""
        from app.atendimento.service import get_all_atendimentos

        user = _make_user()
        db = _mock_db_no_accounts()

        result = await get_all_atendimentos(
            db=db, user=user, type_filter="mensagem"
        )

        assert result.total == 0

    @pytest.mark.asyncio
    async def test_sem_contas_type_reclamacao(self):
        """type_filter='reclamacao' com zero contas → lista vazia."""
        from app.atendimento.service import get_all_atendimentos

        user = _make_user()
        db = _mock_db_no_accounts()

        result = await get_all_atendimentos(
            db=db, user=user, type_filter="reclamacao"
        )

        assert result.total == 0

    @pytest.mark.asyncio
    async def test_sem_contas_type_devolucao(self):
        """type_filter='devolucao' com zero contas → lista vazia."""
        from app.atendimento.service import get_all_atendimentos

        user = _make_user()
        db = _mock_db_no_accounts()

        result = await get_all_atendimentos(
            db=db, user=user, type_filter="devolucao"
        )

        assert result.total == 0

    @pytest.mark.asyncio
    async def test_conta_sem_token_e_ignorada(self):
        """Conta ativa mas sem access_token é ignorada (continue)."""
        from app.atendimento.service import get_all_atendimentos

        account_no_token = MagicMock()
        account_no_token.access_token = None
        account_no_token.id = uuid.uuid4()
        account_no_token.ml_user_id = 12345

        db = _mock_db_with_account(account_no_token)

        user = _make_user()
        result = await get_all_atendimentos(db=db, user=user)

        # Conta sem token → ignorada → lista vazia
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_conta_com_token_excecao_api_ml(self):
        """Conta com token mas API ML lança exceção → erro capturado, lista vazia."""
        from app.atendimento.service import get_all_atendimentos

        account = MagicMock()
        account.access_token = "fake-token-123"
        account.id = uuid.uuid4()
        account.ml_user_id = 12345
        account.nickname = "TestAccount"

        db = _mock_db_with_account(account)

        user = _make_user()

        # Mock MLClient — get_received_questions lança exceção
        mock_ml = AsyncMock()
        mock_ml.get_received_questions = AsyncMock(side_effect=Exception("ML API offline"))
        mock_ml.get_claims = AsyncMock(side_effect=Exception("ML offline"))
        mock_ml.get_returns = AsyncMock(side_effect=Exception("ML offline"))
        mock_ml.get_message_packs = AsyncMock(side_effect=Exception("ML offline"))

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ml)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.atendimento.service.MLClient", return_value=mock_ctx):
            result = await get_all_atendimentos(db=db, user=user)

        # Exceções capturadas → lista vazia (não deve propagar)
        assert result.total == 0


# ═══════════════════════════════════════════════════════════════════════════════
# get_atendimento_stats
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetAtendimentoStats:
    """Testa get_atendimento_stats com zero contas."""

    @pytest.mark.asyncio
    async def test_sem_contas_retorna_zeros(self):
        """Zero contas → stats com tudo zerado."""
        from app.atendimento.service import get_atendimento_stats

        user = _make_user()
        db = _mock_db_no_accounts()

        result = await get_atendimento_stats(db=db, user=user)

        assert result.total == 0
        assert result.requires_action == 0
        assert result.by_type["perguntas"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# respond_to_item
# ═══════════════════════════════════════════════════════════════════════════════


class TestRespondToItem:
    """Testa respond_to_item."""

    @pytest.mark.asyncio
    async def test_conta_nao_encontrada_levanta_valueerror(self):
        """Conta ML não encontrada → ValueError."""
        from app.atendimento.service import respond_to_item

        user = _make_user()
        db = _mock_db_no_ml_account()

        with pytest.raises(ValueError, match="Conta ML não encontrada"):
            await respond_to_item(
                db=db,
                user=user,
                item_type="pergunta",
                item_id="12345",
                text="Resposta aqui",
                account_id=uuid.uuid4(),
            )

    @pytest.mark.asyncio
    async def test_conta_sem_token_levanta_valueerror(self):
        """Conta sem access_token → ValueError."""
        from app.atendimento.service import respond_to_item

        user = _make_user()
        db = _mock_db_with_ml_account_no_token()

        with pytest.raises(ValueError, match="Conta ML não encontrada"):
            await respond_to_item(
                db=db,
                user=user,
                item_type="pergunta",
                item_id="12345",
                text="Resposta aqui",
                account_id=uuid.uuid4(),
            )

    @pytest.mark.asyncio
    async def test_tipo_invalido_levanta_valueerror(self):
        """Tipo de item inválido → ValueError."""
        from app.atendimento.service import respond_to_item

        user = _make_user()

        account = MagicMock()
        account.access_token = "valid-token"
        account.id = uuid.uuid4()
        account.ml_user_id = 12345

        db = AsyncMock()

        async def _execute(*args, **kwargs):
            result = MagicMock()
            result.scalar_one_or_none.return_value = account
            return result

        db.execute = _execute

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.atendimento.service.MLClient", return_value=mock_client):
            with pytest.raises(ValueError, match="Tipo de item inválido"):
                await respond_to_item(
                    db=db,
                    user=user,
                    item_type="tipo_invalido",
                    item_id="12345",
                    text="Resposta aqui",
                    account_id=uuid.uuid4(),
                )

    @pytest.mark.asyncio
    async def test_responder_pergunta_sucesso(self):
        """Tipo='pergunta' → chama answer_question, retorna success=True."""
        from app.atendimento.service import respond_to_item

        user = _make_user()

        account = MagicMock()
        account.access_token = "valid-token"
        account.id = uuid.uuid4()
        account.ml_user_id = 12345

        db = AsyncMock()

        async def _execute(*args, **kwargs):
            result = MagicMock()
            result.scalar_one_or_none.return_value = account
            return result

        db.execute = _execute

        mock_ml = AsyncMock()
        mock_ml.answer_question = AsyncMock(return_value={"status": "ok"})

        mock_client_ctx = AsyncMock()
        mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_ml)
        mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.atendimento.service.MLClient", return_value=mock_client_ctx):
            result = await respond_to_item(
                db=db,
                user=user,
                item_type="pergunta",
                item_id="99999",
                text="Sim, temos em estoque.",
                account_id=uuid.uuid4(),
            )

        assert result["success"] is True
        mock_ml.answer_question.assert_called_once_with(99999, "Sim, temos em estoque.")

    @pytest.mark.asyncio
    async def test_responder_reclamacao_sucesso(self):
        """Tipo='reclamacao' → chama send_claim_message."""
        from app.atendimento.service import respond_to_item

        user = _make_user()

        account = MagicMock()
        account.access_token = "valid-token"
        account.id = uuid.uuid4()
        account.ml_user_id = 12345

        db = AsyncMock()

        async def _execute(*args, **kwargs):
            result = MagicMock()
            result.scalar_one_or_none.return_value = account
            return result

        db.execute = _execute

        mock_ml = AsyncMock()
        mock_ml.send_claim_message = AsyncMock(return_value={"status": "ok"})

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ml)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.atendimento.service.MLClient", return_value=mock_ctx):
            result = await respond_to_item(
                db=db,
                user=user,
                item_type="reclamacao",
                item_id="77777",
                text="Estamos resolvendo.",
                account_id=uuid.uuid4(),
            )

        assert result["success"] is True
        mock_ml.send_claim_message.assert_called_once_with(77777, "Estamos resolvendo.")

    @pytest.mark.asyncio
    async def test_responder_devolucao_sucesso(self):
        """Tipo='devolucao' → chama send_claim_message (mesmo que reclamacao)."""
        from app.atendimento.service import respond_to_item

        user = _make_user()

        account = MagicMock()
        account.access_token = "valid-token"
        account.id = uuid.uuid4()
        account.ml_user_id = 12345

        db = AsyncMock()

        async def _execute(*args, **kwargs):
            result = MagicMock()
            result.scalar_one_or_none.return_value = account
            return result

        db.execute = _execute

        mock_ml = AsyncMock()
        mock_ml.send_claim_message = AsyncMock(return_value={"status": "ok"})

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ml)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.atendimento.service.MLClient", return_value=mock_ctx):
            result = await respond_to_item(
                db=db,
                user=user,
                item_type="devolucao",
                item_id="55555",
                text="Aprovamos a devolução.",
                account_id=uuid.uuid4(),
            )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_responder_mensagem_sucesso(self):
        """Tipo='mensagem' → chama send_message com seller_id."""
        from app.atendimento.service import respond_to_item

        user = _make_user()

        account = MagicMock()
        account.access_token = "valid-token"
        account.id = uuid.uuid4()
        account.ml_user_id = 99888

        db = AsyncMock()

        async def _execute(*args, **kwargs):
            result = MagicMock()
            result.scalar_one_or_none.return_value = account
            return result

        db.execute = _execute

        mock_ml = AsyncMock()
        mock_ml.send_message = AsyncMock(return_value={"status": "ok"})

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ml)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.atendimento.service.MLClient", return_value=mock_ctx):
            result = await respond_to_item(
                db=db,
                user=user,
                item_type="mensagem",
                item_id="PACK-123",
                text="Enviado com sucesso.",
                account_id=uuid.uuid4(),
            )

        assert result["success"] is True
        mock_ml.send_message.assert_called_once_with(
            pack_id="PACK-123",
            text="Enviado com sucesso.",
            seller_id="99888",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Funções puras do módulo atendimento/service.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestAtendimentoPureFunctions:
    """Testa funções puras de atendimento/service.py."""

    def test_parse_dt_none(self):
        """None → datetime.min UTC."""
        from app.atendimento.service import _parse_dt
        result = _parse_dt(None)
        assert result.tzinfo is not None

    def test_parse_dt_iso_com_z(self):
        """ISO com Z → datetime aware."""
        from app.atendimento.service import _parse_dt
        result = _parse_dt("2026-04-01T12:00:00Z")
        assert result.year == 2026
        assert result.month == 4
        assert result.tzinfo is not None

    def test_parse_dt_iso_com_offset(self):
        """ISO com +00:00 → datetime aware."""
        from app.atendimento.service import _parse_dt
        result = _parse_dt("2026-04-01T12:00:00+00:00")
        assert result.year == 2026

    def test_parse_dt_invalido(self):
        """String inválida → datetime.min UTC."""
        from app.atendimento.service import _parse_dt
        result = _parse_dt("not-a-date")
        from datetime import datetime
        assert result == datetime.min.replace(tzinfo=result.tzinfo)

    def test_requires_action_pergunta_unanswered(self):
        """Pergunta sem resposta → requires_action = True."""
        from app.atendimento.service import _requires_action
        assert _requires_action("pergunta", "unanswered") is True

    def test_requires_action_pergunta_answered(self):
        """Pergunta respondida → requires_action = False."""
        from app.atendimento.service import _requires_action
        assert _requires_action("pergunta", "answered") is False

    def test_requires_action_reclamacao_open(self):
        """Reclamação aberta → requires_action = True."""
        from app.atendimento.service import _requires_action
        assert _requires_action("reclamacao", "open") is True

    def test_requires_action_reclamacao_closed(self):
        """Reclamação fechada → requires_action = False."""
        from app.atendimento.service import _requires_action
        assert _requires_action("reclamacao", "closed") is False

    def test_requires_action_mensagem_unread(self):
        """Mensagem não lida → requires_action = True."""
        from app.atendimento.service import _requires_action
        assert _requires_action("mensagem", "unread") is True

    def test_requires_action_mensagem_read(self):
        """Mensagem lida → requires_action = False."""
        from app.atendimento.service import _requires_action
        assert _requires_action("mensagem", "read") is False

    def test_requires_action_tipo_desconhecido(self):
        """Tipo desconhecido → requires_action = False."""
        from app.atendimento.service import _requires_action
        assert _requires_action("tipo_X", "any_status") is False
