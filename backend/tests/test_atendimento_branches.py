"""
Testes de branch para atendimento/service.py e atendimento/service_claims.py

Ciclo 14 do auto-learning — cobertura alvo:
- atendimento/service.py: 34.37% → 50%+
  branches: _parse_claims players, _parse_message_packs last_msg str
- atendimento/service_claims.py: 53.96% → 75%+
  branches: _extract_buyer (ValueError, buyer dict), _extract_order_and_item (non-dict resource)

Estratégia: todas as funções alvo são puras (sem DB/HTTP).
"""
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


# ─── Helper: mock de MLAccount ────────────────────────────────────────────────

def _make_account(nickname="TestAccount"):
    account = MagicMock()
    account.id = uuid.uuid4()
    account.nickname = nickname
    account.ml_user_id = "99999"
    account.access_token = "fake-token"
    return account


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 1: atendimento/service.py — _parse_dt
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseDtService:

    def test_none_retorna_min(self):
        from app.atendimento.service import _parse_dt
        result = _parse_dt(None)
        assert result == datetime.min.replace(tzinfo=timezone.utc)

    def test_string_vazia_retorna_min(self):
        from app.atendimento.service import _parse_dt
        result = _parse_dt("")
        assert result == datetime.min.replace(tzinfo=timezone.utc)

    def test_data_valida_iso(self):
        from app.atendimento.service import _parse_dt
        result = _parse_dt("2026-04-15T10:30:00+00:00")
        assert result.year == 2026
        assert result.month == 4

    def test_data_com_Z(self):
        from app.atendimento.service import _parse_dt
        result = _parse_dt("2026-04-15T10:30:00Z")
        assert result.tzinfo is not None

    def test_data_sem_timezone_recebe_utc(self):
        from app.atendimento.service import _parse_dt
        result = _parse_dt("2026-04-15T10:30:00")
        assert result.tzinfo == timezone.utc

    def test_string_invalida_retorna_min(self):
        from app.atendimento.service import _parse_dt
        result = _parse_dt("nao-e-data")
        assert result == datetime.min.replace(tzinfo=timezone.utc)


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 2: atendimento/service.py — _requires_action
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequiresAction:

    def test_pergunta_unanswered(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("pergunta", "unanswered") is True

    def test_pergunta_under_review(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("pergunta", "UNDER_REVIEW") is True

    def test_pergunta_answered(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("pergunta", "answered") is False

    def test_reclamacao_open(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("reclamacao", "open") is True

    def test_reclamacao_opened(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("reclamacao", "OPENED") is True

    def test_reclamacao_claim_open(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("reclamacao", "claim_open") is True

    def test_reclamacao_resolvida(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("reclamacao", "closed") is False

    def test_devolucao_open(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("devolucao", "open") is True

    def test_mensagem_unread(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("mensagem", "unread") is True

    def test_mensagem_pending(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("mensagem", "PENDING") is True

    def test_mensagem_read(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("mensagem", "read") is False

    def test_tipo_desconhecido(self):
        from app.atendimento.service import _requires_action
        assert _requires_action("outro", "open") is False


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 3: atendimento/service.py — _parse_claims (branches)
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseClaims:

    def test_claim_com_complainant_em_players(self):
        """players com role=complainant → buyer extraído."""
        from app.atendimento.service import _parse_claims
        account = _make_account()
        claims = [{
            "id": "CLM001",
            "status": "open",
            "date_created": "2026-04-15T10:00:00Z",
            "reason_id": "produto_nao_recebido",
            "players": [
                {"role": "seller", "user_id": 111},
                {"role": "complainant", "user_id": 222},
            ],
            "resource": {"order_id": "ORD001", "item_id": "MLB001"},
        }]
        result = _parse_claims(claims, "reclamacao", account)
        assert len(result) == 1
        assert result[0].from_user == {"id": 222, "nickname": 222}

    def test_claim_players_sem_complainant_usa_buyer(self):
        """players sem complainant → usa buyer dict direto (linha 142)."""
        from app.atendimento.service import _parse_claims
        account = _make_account()
        claims = [{
            "id": "CLM002",
            "status": "open",
            "date_created": "2026-04-15T10:00:00Z",
            "players": [
                {"role": "seller", "user_id": 111},
            ],
            "buyer": {"id": 333, "nickname": "compradorTeste"},
            "resource": {},
        }]
        result = _parse_claims(claims, "reclamacao", account)
        assert len(result) == 1
        assert result[0].from_user == {"id": 333, "nickname": "compradorTeste"}

    def test_claim_players_nao_lista_usa_buyer(self):
        """players não é lista → branch 134->139."""
        from app.atendimento.service import _parse_claims
        account = _make_account()
        claims = [{
            "id": "CLM003",
            "status": "open",
            "players": "nao-uma-lista",
            "buyer": {"id": 444, "nickname": "buyer444"},
            "resource": {},
        }]
        result = _parse_claims(claims, "reclamacao", account)
        assert len(result) == 1

    def test_claim_loop_players_sem_role_complainant(self):
        """Loop percorre players mas nenhum tem role=complainant → continua loop."""
        from app.atendimento.service import _parse_claims
        account = _make_account()
        claims = [{
            "id": "CLM004",
            "status": "open",
            "players": [
                {"role": "seller", "user_id": 100},
                {"role": "mediator", "user_id": 200},
            ],
            "buyer": {"id": 500, "nickname": "comprador"},
            "resource": {},
        }]
        result = _parse_claims(claims, "reclamacao", account)
        assert result[0].from_user["id"] == 500

    def test_deduplicacao_mesmo_id(self):
        """Claims com mesmo id são deduplicados via seen_ids."""
        from app.atendimento.service import _parse_claims
        account = _make_account()
        claims = [
            {"id": "DUP001", "status": "open", "resource": {}},
            {"id": "DUP001", "status": "open", "resource": {}},  # duplicado
        ]
        result = _parse_claims(claims, "reclamacao", account)
        assert len(result) == 1

    def test_seen_ids_compartilhado(self):
        """seen_ids passado externamente previne duplicação entre chamadas."""
        from app.atendimento.service import _parse_claims
        account = _make_account()
        seen = {"EXIST001"}
        claims = [
            {"id": "EXIST001", "status": "open", "resource": {}},
            {"id": "NEW002", "status": "open", "resource": {}},
        ]
        result = _parse_claims(claims, "reclamacao", account, seen_ids=seen)
        assert len(result) == 1
        assert result[0].id == "NEW002"

    def test_tipo_devolucao(self):
        from app.atendimento.service import _parse_claims
        account = _make_account()
        claims = [{"id": "DEV001", "status": "open", "resource": {}}]
        result = _parse_claims(claims, "devolucao", account)
        assert result[0].type == "devolucao"

    def test_requires_action_open(self):
        from app.atendimento.service import _parse_claims
        account = _make_account()
        claims = [{"id": "CLM005", "status": "open", "resource": {}}]
        result = _parse_claims(claims, "reclamacao", account)
        assert result[0].requires_action is True

    def test_requires_action_closed(self):
        from app.atendimento.service import _parse_claims
        account = _make_account()
        claims = [{"id": "CLM006", "status": "closed", "resource": {}}]
        result = _parse_claims(claims, "reclamacao", account)
        assert result[0].requires_action is False


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 4: atendimento/service.py — _parse_message_packs (branches)
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseMessagePacks:

    def test_last_message_como_dict(self):
        """last_message é dict → texto do campo 'text'."""
        from app.atendimento.service import _parse_message_packs
        account = _make_account()
        packs = [{
            "id": "PACK001",
            "status": "unread",
            "last_message": {"text": "Olá, meu produto chegou danificado"},
            "date_created": "2026-04-15T10:00:00Z",
        }]
        result = _parse_message_packs(packs, account)
        assert result[0].text == "Olá, meu produto chegou danificado"

    def test_last_message_como_string(self):
        """last_message é string → usa diretamente (branch 178-179)."""
        from app.atendimento.service import _parse_message_packs
        account = _make_account()
        packs = [{
            "id": "PACK002",
            "status": "unread",
            "last_message": "Mensagem direta como string",
            "date_created": "2026-04-15T10:00:00Z",
        }]
        result = _parse_message_packs(packs, account)
        assert result[0].text == "Mensagem direta como string"

    def test_last_message_none_usa_fallback(self):
        """last_message ausente → texto fallback."""
        from app.atendimento.service import _parse_message_packs
        account = _make_account()
        packs = [{
            "id": "PACK003",
            "status": "read",
            "last_message": None,
            "date_created": "2026-04-15T10:00:00Z",
        }]
        result = _parse_message_packs(packs, account)
        assert result[0].text == "Conversa pós-venda"

    def test_status_unread_requires_action(self):
        from app.atendimento.service import _parse_message_packs
        account = _make_account()
        packs = [{"id": "P001", "status": "unread", "last_message": None}]
        result = _parse_message_packs(packs, account)
        assert result[0].requires_action is True

    def test_status_read_nao_requires_action(self):
        from app.atendimento.service import _parse_message_packs
        account = _make_account()
        packs = [{"id": "P002", "status": "read", "last_message": None}]
        result = _parse_message_packs(packs, account)
        assert result[0].requires_action is False

    def test_order_id_extraido(self):
        from app.atendimento.service import _parse_message_packs
        account = _make_account()
        packs = [{"id": "P003", "status": "read", "order_id": "ORD999", "last_message": None}]
        result = _parse_message_packs(packs, account)
        assert result[0].order_id == "ORD999"

    def test_from_buyer_alternativo(self):
        from app.atendimento.service import _parse_message_packs
        account = _make_account()
        packs = [{
            "id": "P004",
            "status": "read",
            "buyer": {"id": 777, "nickname": "compradorX"},
            "last_message": None,
        }]
        result = _parse_message_packs(packs, account)
        assert result[0].from_user == {"id": 777, "nickname": "compradorX"}


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 5: atendimento/service_claims.py — _parse_dt
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseDtClaims:

    def test_none_retorna_agora(self):
        from app.atendimento.service_claims import _parse_dt
        result = _parse_dt(None)
        # Retorna datetime.now(utc), então deve ser recente
        assert result.tzinfo is not None

    def test_string_vazia_retorna_agora(self):
        from app.atendimento.service_claims import _parse_dt
        result = _parse_dt("")
        assert result.tzinfo is not None

    def test_data_valida(self):
        from app.atendimento.service_claims import _parse_dt
        result = _parse_dt("2026-04-15T10:30:00Z")
        assert result.year == 2026

    def test_data_sem_tz_recebe_utc(self):
        from app.atendimento.service_claims import _parse_dt
        result = _parse_dt("2026-04-15T10:30:00")
        assert result.tzinfo == timezone.utc

    def test_invalida_retorna_agora(self):
        from app.atendimento.service_claims import _parse_dt
        result = _parse_dt("invalid-date")
        assert result.tzinfo is not None


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 6: atendimento/service_claims.py — _extract_buyer
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtractBuyer:

    def test_complainant_em_players(self):
        from app.atendimento.service_claims import _extract_buyer
        payload = {
            "players": [
                {"role": "seller", "user_id": 100},
                {"role": "complainant", "user_id": 200},
            ]
        }
        buyer_id, nickname = _extract_buyer(payload)
        assert buyer_id == 200
        assert nickname == "200"

    def test_complainant_uid_invalido_valueerror(self):
        """uid não numérico → ValueError → retorna (None, str_uid)."""
        from app.atendimento.service_claims import _extract_buyer
        payload = {
            "players": [
                {"role": "complainant", "user_id": "abc-invalid"},
            ]
        }
        buyer_id, nickname = _extract_buyer(payload)
        # int("abc-invalid") → ValueError → deve retornar (None, "abc-invalid")
        assert buyer_id is None
        assert nickname == "abc-invalid"

    def test_complainant_uid_none(self):
        from app.atendimento.service_claims import _extract_buyer
        payload = {
            "players": [
                {"role": "complainant", "user_id": None},
            ]
        }
        buyer_id, nickname = _extract_buyer(payload)
        assert buyer_id is None
        assert nickname is None

    def test_sem_complainant_usa_buyer_dict(self):
        """Sem complainant → usa buyer direto (linhas 62-63)."""
        from app.atendimento.service_claims import _extract_buyer
        payload = {
            "players": [{"role": "seller", "user_id": 100}],
            "buyer": {"id": 999, "nickname": "compradorFinal"},
        }
        buyer_id, nickname = _extract_buyer(payload)
        assert buyer_id == 999
        assert nickname == "compradorFinal"

    def test_buyer_id_nao_numerico(self):
        """buyer.id não numerico → ValueError → pass → retorna (None, None)."""
        from app.atendimento.service_claims import _extract_buyer
        payload = {
            "players": [],
            "buyer": {"id": "nao-numerico", "nickname": "N"},
        }
        buyer_id, nickname = _extract_buyer(payload)
        # Deve retornar (None, None) pois id não é int
        assert buyer_id is None

    def test_sem_players_sem_buyer(self):
        from app.atendimento.service_claims import _extract_buyer
        payload = {}
        buyer_id, nickname = _extract_buyer(payload)
        assert buyer_id is None
        assert nickname is None

    def test_players_nao_lista(self):
        from app.atendimento.service_claims import _extract_buyer
        payload = {"players": "nao-lista"}
        buyer_id, nickname = _extract_buyer(payload)
        assert buyer_id is None

    def test_buyer_none_retorna_none(self):
        from app.atendimento.service_claims import _extract_buyer
        payload = {"buyer": None}
        buyer_id, nickname = _extract_buyer(payload)
        assert buyer_id is None


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 7: atendimento/service_claims.py — _extract_order_and_item
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtractOrderAndItem:

    def test_resource_com_order_e_item(self):
        from app.atendimento.service_claims import _extract_order_and_item
        payload = {"resource": {"order_id": "ORD123", "item_id": "MLB456"}}
        order_id, item_id = _extract_order_and_item(payload)
        assert order_id == "ORD123"
        assert item_id == "MLB456"

    def test_resource_sem_campos(self):
        from app.atendimento.service_claims import _extract_order_and_item
        payload = {"resource": {}}
        order_id, item_id = _extract_order_and_item(payload)
        assert order_id is None
        assert item_id is None

    def test_sem_resource(self):
        from app.atendimento.service_claims import _extract_order_and_item
        payload = {}
        order_id, item_id = _extract_order_and_item(payload)
        assert order_id is None
        assert item_id is None

    def test_resource_nao_dict(self):
        """resource não é dict → retorna (None, None) — linha 71."""
        from app.atendimento.service_claims import _extract_order_and_item
        payload = {"resource": "string-nao-e-dict"}
        order_id, item_id = _extract_order_and_item(payload)
        assert order_id is None
        assert item_id is None

    def test_resource_lista_nao_dict(self):
        """resource é lista → também não é dict."""
        from app.atendimento.service_claims import _extract_order_and_item
        payload = {"resource": [1, 2, 3]}
        order_id, item_id = _extract_order_and_item(payload)
        assert order_id is None
        assert item_id is None

    def test_order_id_numerico(self):
        from app.atendimento.service_claims import _extract_order_and_item
        payload = {"resource": {"order_id": 12345678, "item_id": "MLB999"}}
        order_id, item_id = _extract_order_and_item(payload)
        assert order_id == "12345678"
        assert item_id == "MLB999"


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCO 8: atendimento/service.py — _parse_questions
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseQuestions:

    def test_pergunta_basica(self):
        from app.atendimento.service import _parse_questions
        account = _make_account()
        questions = [{
            "id": "Q001",
            "status": "UNANSWERED",
            "text": "Qual é a voltagem?",
            "date_created": "2026-04-15T10:00:00Z",
            "from": {"id": 123, "nickname": "comprador1"},
            "item_id": "MLB123",
        }]
        result = _parse_questions(questions, account)
        assert len(result) == 1
        assert result[0].type == "pergunta"
        assert result[0].text == "Qual é a voltagem?"
        assert result[0].requires_action is True

    def test_pergunta_answered(self):
        from app.atendimento.service import _parse_questions
        account = _make_account()
        questions = [{
            "id": "Q002",
            "status": "ANSWERED",
            "text": "Tem garantia?",
        }]
        result = _parse_questions(questions, account)
        assert result[0].requires_action is False

    def test_item_como_dict(self):
        """item_id passado como dict com id e title."""
        from app.atendimento.service import _parse_questions
        account = _make_account()
        questions = [{
            "id": "Q003",
            "status": "UNANSWERED",
            "text": "Pergunta sobre item",
            "item": {"id": "MLB789", "title": "Produto Especial"},
        }]
        result = _parse_questions(questions, account)
        assert result[0].item_id == "MLB789"
        assert result[0].item_title == "Produto Especial"

    def test_lista_vazia(self):
        from app.atendimento.service import _parse_questions
        account = _make_account()
        result = _parse_questions([], account)
        assert result == []
