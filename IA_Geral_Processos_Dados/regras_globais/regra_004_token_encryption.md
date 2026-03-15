# Regra #4: Tokens ML Devem Ser Criptografados
Fonte: Ciclo 4 — Security Audit
Confianca: 98%
Status: ATIVA

## Regra
access_token e refresh_token do ML DEVEM ser criptografados no banco usando Fernet.
NUNCA armazenar em plaintext.

## Implementacao
- core/crypto.py com encrypt_token() e decrypt_token()
- Fernet key em env var TOKEN_ENCRYPTION_KEY
- decrypt_token() tem fallback gracioso para migrar dados existentes
