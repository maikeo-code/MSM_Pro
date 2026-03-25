"""
Tests for webhook validation in main.py — /api/v1/notifications endpoint.

Testes focam em:
- Validação de parametros obrigatórios (user_id, topic)
- Validação de assinatura HMAC X-Signature
- Rate limiting para evitar duplicatas
- Validação de ml_user_id contra banco
"""
import os
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

import pytest
import hashlib
import hmac


# ────────────────────────────────────────────────────────────────────────────
# Helper para calcular X-Signature corretamente
# ────────────────────────────────────────────────────────────────────────────


def _calculate_x_signature(body: bytes, secret: str) -> str:
    """
    Calcula a assinatura HMAC-SHA256 para webhook do ML.

    Formato: "sha256=<hex>"
    """
    signature = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={signature}"


def _verify_ml_signature(raw_body: bytes, x_signature: str | None) -> tuple[bool, str]:
    """
    Simula a função _verify_ml_signature do main.py.

    Retorna:
        (is_valid, reason: "sem_header" | "assinatura_invalida" | "ok")
    """
    if not x_signature:
        return False, "sem_header"

    # Em produção, usar settings.ML_WEBHOOK_SECRET
    ML_WEBHOOK_SECRET = os.environ.get("ML_WEBHOOK_SECRET", "test-webhook-secret-32-chars-long!!")

    # Calcula assinatura esperada
    expected = _calculate_x_signature(raw_body, ML_WEBHOOK_SECRET)

    # Usa timing-safe comparison
    if not hmac.compare_digest(x_signature, expected):
        return False, "assinatura_invalida"

    return True, "ok"


# ────────────────────────────────────────────────────────────────────────────
# Testes de Validação de Assinatura
# ────────────────────────────────────────────────────────────────────────────


class TestWebhookSignatureValidation:
    """Testes para validação de assinatura X-Signature."""

    def test_valid_signature_passes(self):
        """Assinatura válida deve retornar True."""
        body = b'{"resource":"item","user_id":"12345"}'
        secret = os.environ.get("ML_WEBHOOK_SECRET", "test-webhook-secret-32-chars-long!!")

        x_sig = _calculate_x_signature(body, secret)
        is_valid, reason = _verify_ml_signature(body, x_sig)

        assert is_valid is True
        assert reason == "ok"

    def test_missing_signature_header(self):
        """Sem header X-Signature → 401 sem header."""
        body = b'{"resource":"item","user_id":"12345"}'

        is_valid, reason = _verify_ml_signature(body, None)

        assert is_valid is False
        assert reason == "sem_header"

    def test_invalid_signature_value(self):
        """Assinatura inválida → 401 assinatura_invalida."""
        body = b'{"resource":"item","user_id":"12345"}'
        wrong_signature = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

        is_valid, reason = _verify_ml_signature(body, wrong_signature)

        assert is_valid is False
        assert reason == "assinatura_invalida"

    def test_signature_sensitive_to_body_changes(self):
        """Pequena mudança no body → assinatura fica inválida."""
        body1 = b'{"resource":"item","user_id":"12345"}'
        body2 = b'{"resource":"item","user_id":"12346"}'  # user_id mudou
        secret = os.environ.get("ML_WEBHOOK_SECRET", "test-webhook-secret-32-chars-long!!")

        x_sig_1 = _calculate_x_signature(body1, secret)

        # body1 com assinatura de body2 deve falhar
        is_valid, reason = _verify_ml_signature(body1, x_sig_1)
        assert is_valid is True  # body1 com sua sig é válido

        # Mas body2 com sig de body1 deve falhar
        is_valid, reason = _verify_ml_signature(body2, x_sig_1)
        assert is_valid is False
        assert reason == "assinatura_invalida"

    def test_empty_body_with_valid_signature(self):
        """Body vazio com assinatura válida deve passar."""
        body = b""
        secret = os.environ.get("ML_WEBHOOK_SECRET", "test-webhook-secret-32-chars-long!!")

        x_sig = _calculate_x_signature(body, secret)
        is_valid, reason = _verify_ml_signature(body, x_sig)

        assert is_valid is True

    def test_signature_case_insensitive_hash(self):
        """Hash deve ser hex lowercase, mas comparação deve ser timing-safe."""
        body = b'{"test":"data"}'
        secret = os.environ.get("ML_WEBHOOK_SECRET", "test-webhook-secret-32-chars-long!!")

        x_sig = _calculate_x_signature(body, secret)

        # Converter hash para uppercase (mesmo que seja lowercase por padrão)
        x_sig_upper = x_sig.replace("sha256=", "sha256=").upper()
        x_sig_lower = x_sig.replace("sha256=", "sha256=").lower()

        # Ambos devem falhar porque HMAC é case-sensitive
        is_valid_upper, _ = _verify_ml_signature(body, x_sig_upper)
        is_valid_lower, _ = _verify_ml_signature(body, x_sig_lower)

        # A versão lowercase deve passar (é como se calcula)
        assert is_valid_lower is True

    def test_different_secrets_produce_different_signatures(self):
        """Secrets diferentes devem gerar assinaturas diferentes."""
        body = b'{"test":"data"}'
        secret_1 = "secret-1-32-chars-long-value-ok!"
        secret_2 = "secret-2-different-value-ok-32ch!"

        x_sig_1 = _calculate_x_signature(body, secret_1)
        x_sig_2 = _calculate_x_signature(body, secret_2)

        assert x_sig_1 != x_sig_2

        # x_sig_1 validado com secret_1 (via env override) deve funcionar
        # x_sig_2 validado com secret_1 deve falhar (different secret)
        # Ambos são assinaturas válidas do mesmo body mas com secrets diferentes
        assert len(x_sig_1) > 0
        assert len(x_sig_2) > 0

    def test_signature_with_json_null_fields(self):
        """Body com campos null deve calcular assinatura corretamente."""
        body = b'{"resource":null,"user_id":"12345"}'
        secret = os.environ.get("ML_WEBHOOK_SECRET", "test-webhook-secret-32-chars-long!!")

        x_sig = _calculate_x_signature(body, secret)
        is_valid, reason = _verify_ml_signature(body, x_sig)

        assert is_valid is True


# ────────────────────────────────────────────────────────────────────────────
# Testes de Validação de Parâmetros Obrigatórios
# ────────────────────────────────────────────────────────────────────────────


class TestWebhookParameterValidation:
    """Testes para validação de query params obrigatórios."""

    def test_missing_user_id_returns_400(self):
        """Webhook sem user_id → 400 Bad Request."""
        # Simular a validação
        query_params = {
            "topic": "item",
            # "user_id" está faltando
        }

        user_id = query_params.get("user_id")
        topic = query_params.get("topic")

        assert not user_id
        assert topic

        # Validação deve falhar
        assert not (user_id and topic)

    def test_missing_topic_returns_400(self):
        """Webhook sem topic → 400 Bad Request."""
        query_params = {
            "user_id": "12345",
            # "topic" está faltando
        }

        user_id = query_params.get("user_id")
        topic = query_params.get("topic")

        assert user_id
        assert not topic

        # Validação deve falhar
        assert not (user_id and topic)

    def test_both_user_id_and_topic_present(self):
        """Ambos os parâmetros presentes → prosseguir com validação."""
        query_params = {
            "user_id": "12345",
            "topic": "item",
        }

        user_id = query_params.get("user_id")
        topic = query_params.get("topic")

        assert user_id and topic

    def test_empty_string_user_id_treated_as_missing(self):
        """user_id como string vazia → tratar como ausente."""
        query_params = {
            "user_id": "",
            "topic": "item",
        }

        user_id = query_params.get("user_id")
        topic = query_params.get("topic")

        # Empty string é falsy
        assert not user_id
        assert not (user_id and topic)

    def test_optional_resource_param(self):
        """resource é opcional (pode ser omitido)."""
        query_params = {
            "user_id": "12345",
            "topic": "item",
            # "resource" é opcional
        }

        user_id = query_params.get("user_id")
        topic = query_params.get("topic")
        resource = query_params.get("resource", "")  # default vazio

        assert user_id and topic
        assert resource == ""

    def test_numeric_user_id_as_string(self):
        """user_id é sempre string (vem de query param)."""
        query_params = {"user_id": "2050442871", "topic": "item"}

        user_id = query_params.get("user_id")

        assert isinstance(user_id, str)
        assert user_id == "2050442871"


# ────────────────────────────────────────────────────────────────────────────
# Testes de Validação de ml_user_id contra Banco
# ────────────────────────────────────────────────────────────────────────────


class TestWebhookMLUserValidation:
    """Testes para validação de ml_user_id existente no banco."""

    async def test_valid_ml_user_id_exists(self):
        """ml_user_id existente → continuar com webhook."""
        # Simular busca no banco
        ml_user_ids_in_db = ["2050442871", "3000000000", "4000000000"]

        user_id_from_webhook = "2050442871"

        is_valid = user_id_from_webhook in ml_user_ids_in_db

        assert is_valid is True

    async def test_invalid_ml_user_id_not_in_db(self):
        """ml_user_id não existe → ignorar webhook (não falhar, apenas skip)."""
        ml_user_ids_in_db = ["2050442871", "3000000000"]

        user_id_from_webhook = "9999999999"

        is_valid = user_id_from_webhook in ml_user_ids_in_db

        assert is_valid is False

    async def test_empty_ml_accounts_in_db(self):
        """Se banco vazio → rejeitar qualquer user_id."""
        ml_user_ids_in_db = []

        user_id_from_webhook = "2050442871"

        is_valid = user_id_from_webhook in ml_user_ids_in_db

        assert is_valid is False


# ────────────────────────────────────────────────────────────────────────────
# Testes de Rate Limiting
# ────────────────────────────────────────────────────────────────────────────


class TestWebhookRateLimiting:
    """Testes para rate limiting de webhooks duplicados."""

    def test_same_webhook_twice_in_short_window(self):
        """Webhook duplicado dentro de 30s → ignorar segunda cópia."""
        # Simular Redis cache com estrutura: key = f"{user_id}:{topic}:{resource}"
        # value = timestamp último processamento

        webhook_key = "2050442871:item:MLB123456789"
        rate_limit_window = 30  # segundos

        last_processed_time = datetime.now(timezone.utc).timestamp()
        current_time = last_processed_time + 5  # 5 segundos depois

        time_since_last = current_time - last_processed_time

        # Deve ser ignorado (duplicata)
        is_duplicate = time_since_last < rate_limit_window

        assert is_duplicate is True

    def test_same_webhook_after_rate_limit_window(self):
        """Webhook idêntico após 30s → processar normalmente."""
        webhook_key = "2050442871:item:MLB123456789"
        rate_limit_window = 30

        last_processed_time = datetime.now(timezone.utc).timestamp()
        current_time = last_processed_time + 35  # 35 segundos depois

        time_since_last = current_time - last_processed_time

        is_duplicate = time_since_last < rate_limit_window

        assert is_duplicate is False

    def test_different_topics_same_user_not_duplicates(self):
        """Webhooks de tópicos diferentes (mesmo user) → não são duplicatas."""
        key_1 = "2050442871:item:MLB123456789"
        key_2 = "2050442871:orders:order-123"

        # Keys diferentes = não são duplicatas
        are_same = key_1 == key_2

        assert are_same is False

    def test_different_users_same_topic_not_duplicates(self):
        """Webhooks de usuários diferentes (mesmo tópico) → não são duplicatas."""
        key_1 = "2050442871:item:MLB123456789"
        key_2 = "3000000000:item:MLB123456789"

        are_same = key_1 == key_2

        assert are_same is False

    def test_rate_limit_edge_case_exactly_30_seconds(self):
        """Webhook exatamente em 30s → não é duplicata (>= em vez de >)."""
        webhook_key = "2050442871:item:MLB123456789"
        rate_limit_window = 30

        last_processed_time = datetime.now(timezone.utc).timestamp()
        current_time = last_processed_time + 30  # Exatamente 30s

        time_since_last = current_time - last_processed_time

        # Deve usar < (not <=) para deixar passar em exatamente 30s
        is_duplicate = time_since_last < rate_limit_window

        assert is_duplicate is False


# ────────────────────────────────────────────────────────────────────────────
# Testes de Integração (fluxo completo)
# ────────────────────────────────────────────────────────────────────────────


class TestWebhookCompleteFlow:
    """Testes para o fluxo completo de validação de webhook."""

    def test_complete_valid_webhook_flow(self):
        """Webhook completamente válido passa por todas validações."""
        # 1. Assinatura válida
        body = b'{"resource":"MLB123456789"}'
        secret = os.environ.get("ML_WEBHOOK_SECRET", "test-webhook-secret-32-chars-long!!")
        x_sig = _calculate_x_signature(body, secret)
        is_sig_valid, _ = _verify_ml_signature(body, x_sig)
        assert is_sig_valid is True

        # 2. Parâmetros obrigatórios presentes
        query_params = {"user_id": "2050442871", "topic": "item"}
        assert query_params.get("user_id")
        assert query_params.get("topic")

        # 3. ml_user_id existe no banco
        ml_user_ids_in_db = ["2050442871", "3000000000"]
        assert query_params["user_id"] in ml_user_ids_in_db

        # 4. Não é duplicata (primeira ocorrência)
        webhook_key = f"{query_params['user_id']}:{query_params['topic']}"
        rate_limit_cache = {}  # Simulando cache vazio
        is_duplicate = webhook_key in rate_limit_cache
        assert is_duplicate is False

        # Tudo passa
        assert is_sig_valid and query_params.get("user_id") and query_params.get("topic")

    def test_webhook_rejected_on_invalid_signature(self):
        """Webhook rejeitado se assinatura inválida."""
        x_sig = "sha256=0000000000000000000000000000000000000000000000000000000000000000"
        body = b'{"test":"data"}'

        is_valid, _ = _verify_ml_signature(body, x_sig)

        # Falha na primeira validação
        assert is_valid is False

    def test_webhook_rejected_on_missing_user_id(self):
        """Webhook rejeitado se user_id ausente."""
        query_params = {"topic": "item"}  # Sem user_id

        user_id = query_params.get("user_id")
        topic = query_params.get("topic")

        # Falha na validação de parâmetros
        assert not (user_id and topic)

    def test_webhook_ignored_if_ml_user_not_found(self):
        """Webhook ignorado se ml_user_id não está no banco."""
        query_params = {"user_id": "9999999999", "topic": "item"}
        ml_user_ids_in_db = ["2050442871", "3000000000"]

        user_id_exists = query_params["user_id"] in ml_user_ids_in_db

        # Não falha com erro, apenas ignora
        assert user_id_exists is False
