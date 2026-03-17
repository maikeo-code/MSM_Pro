"""Tests for Fernet token encryption (EncryptedString)."""
import os
import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")


def test_encrypt_decrypt_roundtrip():
    from app.core.crypto import EncryptedString

    es = EncryptedString(2000)
    original = "APP_USR-3490124889364697-031217-abcdef123456"

    encrypted = es.process_bind_param(original, None)
    assert encrypted is not None
    assert encrypted != original  # must be different
    assert encrypted.startswith("gAAAA")  # Fernet prefix

    decrypted = es.process_result_value(encrypted, None)
    assert decrypted == original


def test_none_passthrough():
    from app.core.crypto import EncryptedString

    es = EncryptedString(2000)
    assert es.process_bind_param(None, None) is None
    assert es.process_result_value(None, None) is None


def test_legacy_plaintext_fallback():
    """Tokens stored before encryption should still be readable."""
    from app.core.crypto import EncryptedString

    es = EncryptedString(2000)
    legacy_token = "APP_USR-old-plaintext-token-12345"

    result = es.process_result_value(legacy_token, None)
    assert result == legacy_token


def test_different_tokens_produce_different_ciphertext():
    from app.core.crypto import EncryptedString

    es = EncryptedString(2000)
    enc1 = es.process_bind_param("token-aaa", None)
    enc2 = es.process_bind_param("token-bbb", None)
    assert enc1 != enc2


def test_empty_string_encrypts():
    from app.core.crypto import EncryptedString

    es = EncryptedString(2000)
    encrypted = es.process_bind_param("", None)
    assert encrypted is not None
    decrypted = es.process_result_value(encrypted, None)
    assert decrypted == ""
