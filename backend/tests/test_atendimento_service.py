"""
Testes para app/atendimento/service.py e service_templates.py

Ciclo 4 do auto-learning — cobertura alvo:
- service.py: 6% → 45% (funções puras + get_all_atendimentos com mock)
- service_templates.py: 27% → 85% (CRUD real SQLite)
- service_claims.py: 36% → 55% (pure helpers)

Estratégia:
- Funções puras (_parse_dt, _requires_action, _parse_questions, etc.): sem DB
- Templates: CRUD completo com SQLite (queries simples)
- Claims puras: _parse_dt, _extract_buyer, _extract_order_and_item
"""
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest

from app.auth.models import MLAccount, User
from app.atendimento.models import ResponseTemplate


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _uid():
    return uuid.uuid4()


def _make_user(email=None):
    return User(
        id=_uid(),
        email=email or f"u_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="hashed",
        is_active=True,
    )


def _make_ml_account(user_id):
    return MLAccount(
        id=_uid(),
        user_id=user_id,
        ml_user_id="seller_123",
        nickname="Loja Teste",
        is_active=True,
        access_token="valid_token",
    )


def _make_template(user_id, name="Template Teste", text="Olá {nome}, tudo bem?", category="general"):
    return ResponseTemplate(
        id=_uid(),
        user_id=user_id,
        name=name,
        text=text,
        category=category,
        use_count=0,
    )


# ─── Testes: _parse_dt (service.py) ──────────────────────────────────────────


class TestParseDt:
    """Testa _parse_dt — puramente funcional."""

    def test_none_retorna_datetime_min(self):
        from app.atendimento.service import _parse_dt
        result = _parse_dt(None)
        assert result == datetime.min.replace(tzinfo=timezone.utc)

    def test_string_vazia_retorna_datetime_min(self):
        from app.atendimento.service import _parse_dt
        result = _parse_dt("")
        assert result == datetime.min.replace(tzinfo=timezone.utc)

    def test_iso_com_Z_converte_para_utc(self):
        from app.atendimento.service import _parse_dt
        result = _parse_dt("2026-04-10T10:30:00.000Z")
        assert result.year == 2026
        assert result.month == 4
        assert result.day == 10
        assert result.tzinfo is not None

    def test_iso_sem_timezone_adiciona_utc(self):
        from app.atendimento.service import _parse_dt
        result = _parse_dt("2026-04-10T10:30:00")
        assert result.tzinfo is not None

    def test_iso_com_offset(self):
        from app.atendimento.service import _parse_dt
        result = _parse_dt("2026-04-10T10:30:00-03:00")
        assert result.tzinfo is not None

    def test_string_invalida_retorna_datetime_min(self):
        from app.atendimento.service import _parse_dt
        result = _parse_dt("data-invalida")
        assert result == datetime.min.replace(tzinfo=timezone.utc)


# ─── Testes: _requires_action (service.py) ───────────────────────────────────


class TestRequiresAction:
    """Testa _requires_action — lógica de negócio pura."""

    def test_pergunta_unanswered_requer_acao(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("pergunta", "UNANSWERED") is True

    def test_pergunta_unanswered_lowercase(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("pergunta", "unanswered") is True

    def test_pergunta_under_review_requer_acao(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("pergunta", "under_review") is True

    def test_pergunta_answered_nao_requer_acao(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("pergunta", "ANSWERED") is False

    def test_reclamacao_open_requer_acao(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("reclamacao", "open") is True

    def test_reclamacao_opened_requer_acao(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("reclamacao", "opened") is True

    def test_reclamacao_claim_open_requer_acao(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("reclamacao", "claim_open") is True

    def test_reclamacao_closed_nao_requer_acao(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("reclamacao", "closed") is False

    def test_devolucao_open_requer_acao(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("devolucao", "open") is True

    def test_mensagem_unread_requer_acao(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("mensagem", "unread") is True

    def test_mensagem_pending_requer_acao(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("mensagem", "pending") is True

    def test_mensagem_read_nao_requer_acao(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("mensagem", "read") is False

    def test_tipo_desconhecido_retorna_false(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("outro_tipo", "open") is False


# ─── Testes: _parse_questions (service.py) ───────────────────────────────────


class TestParseQuestions:
    """Testa _parse_questions com dados simulados."""

    def _fake_account(self):
        acc = MagicMock()
        acc.id = _uid()
        acc.nickname = "Loja Mock"
        return acc

    def test_lista_vazia(self):
        from app.atendimento.service import _parse_questions
        result = _parse_questions([], self._fake_account())
        assert result == []

    def test_pergunta_nao_respondida(self):
        from app.atendimento.service import _parse_questions
        acc = self._fake_account()
        questions = [
            {
                "id": 123,
                "text": "Tem garantia?",
                "status": "UNANSWERED",
                "date_created": "2026-04-10T10:00:00.000Z",
                "from": {"id": 456, "nickname": "comprador_x"},
                "item_id": "MLB999",
            }
        ]
        result = _parse_questions(questions, acc)
        assert len(result) == 1
        item = result[0]
        assert item.id == "123"
        assert item.type == "pergunta"
        assert item.text == "Tem garantia?"
        assert item.status == "unanswered"
        assert item.requires_action is True

    def test_pergunta_respondida_nao_requer_acao(self):
        from app.atendimento.service import _parse_questions
        acc = self._fake_account()
        questions = [{"id": 456, "text": "Ok!", "status": "ANSWERED", "date_created": None, "from": {}}]
        result = _parse_questions(questions, acc)
        assert result[0].requires_action is False

    def test_item_id_como_string(self):
        from app.atendimento.service import _parse_questions
        acc = self._fake_account()
        questions = [{"id": 999, "text": "X", "status": "unanswered", "date_created": None, "item_id": "MLB123", "from": {}}]
        result = _parse_questions(questions, acc)
        assert result[0].item_id == "MLB123"

    def test_account_nickname_propagado(self):
        from app.atendimento.service import _parse_questions
        acc = self._fake_account()
        acc.nickname = "Minha Loja"
        questions = [{"id": 1, "text": "?", "status": "unanswered", "date_created": None, "from": {}}]
        result = _parse_questions(questions, acc)
        assert result[0].account_nickname == "Minha Loja"


# ─── Testes: _parse_claims (service.py) ──────────────────────────────────────


class TestParseClaims:
    """Testa _parse_claims com dados simulados."""

    def _fake_account(self):
        acc = MagicMock()
        acc.id = _uid()
        acc.nickname = "Loja Mock"
        return acc

    def test_lista_vazia(self):
        from app.atendimento.service import _parse_claims
        result = _parse_claims([], "reclamacao", self._fake_account())
        assert result == []

    def test_claim_open_requer_acao(self):
        from app.atendimento.service import _parse_claims
        acc = self._fake_account()
        claims = [
            {
                "id": "CL001",
                "status": "open",
                "date_created": "2026-04-05T09:00:00Z",
                "reason_id": "ITEM_NOT_AS_DESCRIBED",
                "resource": {"order_id": "ORD001", "item_id": "MLB001"},
                "players": [{"role": "complainant", "user_id": 789}],
            }
        ]
        result = _parse_claims(claims, "reclamacao", acc)
        assert len(result) == 1
        assert result[0].type == "reclamacao"
        assert result[0].requires_action is True
        assert result[0].text == "ITEM_NOT_AS_DESCRIBED"

    def test_deduplicacao_mesmo_id(self):
        from app.atendimento.service import _parse_claims
        acc = self._fake_account()
        claims = [
            {"id": "CL_DUP", "status": "open", "date_created": None, "resource": {}},
            {"id": "CL_DUP", "status": "open", "date_created": None, "resource": {}},
        ]
        result = _parse_claims(claims, "reclamacao", acc)
        assert len(result) == 1

    def test_seen_ids_compartilhado(self):
        """seen_ids passado externamente evita duplicação entre chamadas."""
        from app.atendimento.service import _parse_claims
        acc = self._fake_account()
        seen: set[str] = {"CL_ALREADY_SEEN"}
        claims = [
            {"id": "CL_ALREADY_SEEN", "status": "open", "date_created": None, "resource": {}},
            {"id": "CL_NEW", "status": "open", "date_created": None, "resource": {}},
        ]
        result = _parse_claims(claims, "reclamacao", acc, seen_ids=seen)
        assert len(result) == 1
        assert result[0].id == "CL_NEW"

    def test_extract_buyer_from_players(self):
        from app.atendimento.service import _parse_claims
        acc = self._fake_account()
        claims = [
            {
                "id": "CL002",
                "status": "opened",
                "date_created": None,
                "players": [
                    {"role": "complainant", "user_id": 42},
                    {"role": "seller", "user_id": 7},
                ],
                "resource": {},
            }
        ]
        result = _parse_claims(claims, "reclamacao", acc)
        assert result[0].from_user is not None
        assert result[0].from_user.get("id") == 42


# ─── Testes: _parse_message_packs (service.py) ───────────────────────────────


class TestParseMessagePacks:
    """Testa _parse_message_packs com dados simulados."""

    def _fake_account(self):
        acc = MagicMock()
        acc.id = _uid()
        acc.nickname = "Loja Mock"
        return acc

    def test_pack_lido_nao_requer_acao(self):
        from app.atendimento.service import _parse_message_packs
        acc = self._fake_account()
        packs = [
            {
                "id": "PACK001",
                "status": "read",
                "date_created": "2026-04-10T10:00:00Z",
                "last_message": {"text": "Obrigado!"},
                "order_id": "ORD123",
            }
        ]
        result = _parse_message_packs(packs, acc)
        assert len(result) == 1
        assert result[0].type == "mensagem"
        assert result[0].requires_action is False
        assert result[0].text == "Obrigado!"

    def test_pack_unread_requer_acao(self):
        from app.atendimento.service import _parse_message_packs
        acc = self._fake_account()
        packs = [{"id": "PACK002", "status": "unread", "date_created": None, "last_message": {}}]
        result = _parse_message_packs(packs, acc)
        assert result[0].requires_action is True

    def test_sem_texto_usa_default(self):
        from app.atendimento.service import _parse_message_packs
        acc = self._fake_account()
        packs = [{"id": "PACK003", "status": "read", "date_created": None}]
        result = _parse_message_packs(packs, acc)
        assert result[0].text == "Conversa pós-venda"


# ─── Testes: _extract_variables (service_templates.py) ───────────────────────


class TestExtractVariables:
    """Testa extração de variáveis de templates."""

    def test_sem_variaveis(self):
        from app.atendimento.service_templates import _extract_variables
        result = _extract_variables("Texto sem variáveis.")
        assert result == []

    def test_uma_variavel(self):
        from app.atendimento.service_templates import _extract_variables
        result = _extract_variables("Olá {nome}, tudo bem?")
        assert "nome" in result

    def test_multiplas_variaveis(self):
        from app.atendimento.service_templates import _extract_variables
        result = _extract_variables("Olá {nome}, seu pedido {order_id} chegará em {prazo} dias.")
        assert len(result) == 3
        assert "nome" in result
        assert "order_id" in result
        assert "prazo" in result

    def test_variavel_duplicada_retorna_uma_vez(self):
        from app.atendimento.service_templates import _extract_variables
        result = _extract_variables("Olá {nome}, {nome}!")
        assert result.count("nome") == 1


class TestFillTemplate:
    """Testa fill_template."""

    def test_substitui_variavel(self):
        from app.atendimento.service_templates import fill_template
        result = fill_template("Olá {nome}!", {"nome": "João"})
        assert result == "Olá João!"

    def test_substitui_multiplas_variaveis(self):
        from app.atendimento.service_templates import fill_template
        result = fill_template("{nome} pedido {order_id}", {"nome": "Maria", "order_id": "12345"})
        assert result == "Maria pedido 12345"

    def test_variavel_nao_encontrada_permanece(self):
        from app.atendimento.service_templates import fill_template
        result = fill_template("Olá {nome}!", {})
        assert result == "Olá {nome}!"

    def test_texto_sem_variaveis(self):
        from app.atendimento.service_templates import fill_template
        result = fill_template("Texto fixo.", {"nome": "X"})
        assert result == "Texto fixo."


# ─── Testes: CRUD de templates (SQLite real) ─────────────────────────────────


class TestTemplatesCRUD:
    """Testa CRUD completo de templates com SQLite."""

    @pytest.mark.asyncio
    async def test_list_templates_vazio(self, db):
        from app.atendimento.service_templates import list_templates

        user = _make_user()
        db.add(user)
        await db.flush()

        result = await list_templates(db, user)
        assert result == []

    @pytest.mark.asyncio
    async def test_create_template(self, db):
        from app.atendimento.service_templates import create_template
        from app.atendimento.schemas import ResponseTemplateIn

        user = _make_user()
        db.add(user)
        await db.flush()

        data = ResponseTemplateIn(
            name="Resposta Padrão",
            text="Olá {nome}, obrigado pelo contato!",
            category="geral",
        )
        template = await create_template(db, user, data)

        assert template.name == "Resposta Padrão"
        assert "nome" in template.variables
        assert template.use_count == 0

    @pytest.mark.asyncio
    async def test_create_template_nome_duplicado_levanta_erro(self, db):
        from app.atendimento.service_templates import create_template
        from app.atendimento.schemas import ResponseTemplateIn

        user = _make_user()
        db.add(user)
        await db.flush()

        data = ResponseTemplateIn(name="Duplicado", text="Texto", category="geral")
        await create_template(db, user, data)

        with pytest.raises(ValueError, match="already exists"):
            await create_template(db, user, data)

    @pytest.mark.asyncio
    async def test_get_template_existente(self, db):
        from app.atendimento.service_templates import create_template, get_template
        from app.atendimento.schemas import ResponseTemplateIn

        user = _make_user()
        db.add(user)
        await db.flush()

        created = await create_template(
            db, user, ResponseTemplateIn(name="T1", text="Texto", category="geral")
        )
        fetched = await get_template(db, user, created.id)
        assert fetched.id == created.id
        assert fetched.name == "T1"

    @pytest.mark.asyncio
    async def test_get_template_inexistente_levanta_erro(self, db):
        from app.atendimento.service_templates import get_template

        user = _make_user()
        db.add(user)
        await db.flush()

        with pytest.raises(ValueError, match="not found"):
            await get_template(db, user, _uid())

    @pytest.mark.asyncio
    async def test_update_template(self, db):
        from app.atendimento.service_templates import create_template, update_template
        from app.atendimento.schemas import ResponseTemplateIn

        user = _make_user()
        db.add(user)
        await db.flush()

        created = await create_template(
            db, user, ResponseTemplateIn(name="Original", text="Texto antigo", category="geral")
        )
        updated = await update_template(
            db, user, created.id,
            ResponseTemplateIn(name="Atualizado", text="Novo texto com {variavel}", category="pergunta")
        )

        assert updated.name == "Atualizado"
        assert updated.text == "Novo texto com {variavel}"
        assert "variavel" in updated.variables
        assert updated.category == "pergunta"

    @pytest.mark.asyncio
    async def test_delete_template(self, db):
        from sqlalchemy import select as sa_select
        from app.atendimento.service_templates import create_template, delete_template
        from app.atendimento.schemas import ResponseTemplateIn

        user = _make_user()
        db.add(user)
        await db.flush()

        created = await create_template(
            db, user, ResponseTemplateIn(name="Para Deletar", text="Texto", category="geral")
        )
        await delete_template(db, user, created.id)

        result = await db.execute(
            sa_select(ResponseTemplate).where(ResponseTemplate.id == created.id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_template_inexistente_levanta_erro(self, db):
        from app.atendimento.service_templates import delete_template

        user = _make_user()
        db.add(user)
        await db.flush()

        with pytest.raises(ValueError, match="not found"):
            await delete_template(db, user, _uid())

    @pytest.mark.asyncio
    async def test_use_template_incrementa_contador(self, db):
        from app.atendimento.service_templates import create_template, use_template
        from app.atendimento.schemas import ResponseTemplateIn
        from sqlalchemy import select as sa_select

        user = _make_user()
        db.add(user)
        await db.flush()

        created = await create_template(
            db, user, ResponseTemplateIn(name="Contador", text="Texto", category="geral")
        )
        assert created.use_count == 0

        await use_template(db, user, created.id)
        await use_template(db, user, created.id)

        result = await db.execute(
            sa_select(ResponseTemplate).where(ResponseTemplate.id == created.id)
        )
        t = result.scalar_one()
        assert t.use_count == 2

    @pytest.mark.asyncio
    async def test_list_templates_filtro_categoria(self, db):
        from app.atendimento.service_templates import create_template, list_templates
        from app.atendimento.schemas import ResponseTemplateIn

        user = _make_user()
        db.add(user)
        await db.flush()

        await create_template(db, user, ResponseTemplateIn(name="P1", text="T", category="pergunta"))
        await create_template(db, user, ResponseTemplateIn(name="R1", text="T", category="reclamacao"))
        await create_template(db, user, ResponseTemplateIn(name="P2", text="T", category="pergunta"))

        perguntas = await list_templates(db, user, category="pergunta")
        reclamacoes = await list_templates(db, user, category="reclamacao")
        todos = await list_templates(db, user)

        assert len(perguntas) == 2
        assert len(reclamacoes) == 1
        assert len(todos) == 3

    @pytest.mark.asyncio
    async def test_templates_isolados_entre_usuarios(self, db):
        from app.atendimento.service_templates import create_template, list_templates
        from app.atendimento.schemas import ResponseTemplateIn

        user1 = _make_user()
        user2 = _make_user()
        db.add_all([user1, user2])
        await db.flush()

        await create_template(db, user1, ResponseTemplateIn(name="T1", text="T", category="geral"))
        await create_template(db, user2, ResponseTemplateIn(name="T2", text="T", category="geral"))

        t1 = await list_templates(db, user1)
        t2 = await list_templates(db, user2)

        assert len(t1) == 1
        assert t1[0].name == "T1"
        assert len(t2) == 1
        assert t2[0].name == "T2"


# ─── Testes: _extract_buyer e _extract_order_and_item (service_claims.py) ────


class TestServiceClaimsPureHelpers:
    """Testa helpers puros de service_claims."""

    def test_extract_buyer_players(self):
        from app.atendimento.service_claims import _extract_buyer
        payload = {
            "players": [
                {"role": "seller", "user_id": 1},
                {"role": "complainant", "user_id": 999},
            ]
        }
        bid, bnick = _extract_buyer(payload)
        assert bid == 999

    def test_extract_buyer_direto(self):
        from app.atendimento.service_claims import _extract_buyer
        payload = {"buyer": {"id": 42, "nickname": "comprador_x"}}
        bid, bnick = _extract_buyer(payload)
        assert bid == 42
        assert bnick == "comprador_x"

    def test_extract_buyer_sem_dados(self):
        from app.atendimento.service_claims import _extract_buyer
        bid, bnick = _extract_buyer({})
        assert bid is None
        assert bnick is None

    def test_extract_order_and_item(self):
        from app.atendimento.service_claims import _extract_order_and_item
        payload = {"resource": {"order_id": "ORD123", "item_id": "MLB456"}}
        order_id, item_id = _extract_order_and_item(payload)
        assert order_id == "ORD123"
        assert item_id == "MLB456"

    def test_extract_order_and_item_vazio(self):
        from app.atendimento.service_claims import _extract_order_and_item
        order_id, item_id = _extract_order_and_item({})
        assert order_id is None
        assert item_id is None

    def test_parse_dt_claims(self):
        from app.atendimento.service_claims import _parse_dt
        result = _parse_dt("2026-04-10T15:00:00.000Z")
        assert result.year == 2026
        assert result.tzinfo is not None

    def test_parse_dt_claims_none(self):
        from app.atendimento.service_claims import _parse_dt
        result = _parse_dt(None)
        # Retorna datetime.now() para claims (diferente do service.py)
        assert result.tzinfo is not None
