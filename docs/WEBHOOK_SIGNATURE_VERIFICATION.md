# Verificacao de Assinatura X-Signature em Webhooks do Mercado Livre

## Visao Geral

O endpoint `POST /api/v1/notifications` agora valida o header `X-Signature` de todos os webhooks recebidos do Mercado Livre usando HMAC-SHA256. Isso previne que atacantes disparem tasks de sync sem autorização.

## Implementacao

### Arquivo: `backend/app/main.py`

#### Funcao de Verificacao
```python
def _verify_ml_signature(body: bytes, x_signature: str | None) -> tuple[bool, str]:
    """Verifica a assinatura HMAC-SHA256 do webhook do Mercado Livre."""
```

**Comportamento:**

| Cenario | Retorno | Status HTTP | Descricao |
|---------|---------|-------------|-----------|
| Assinatura valida | `(True, "ok")` | 200 | Webhook processado normalmente |
| Assinatura invalida | `(False, "assinatura_invalida")` | 401 | Rejeita com 401 Unauthorized |
| Header ausente | `(False, "sem_header")` | 401 | Rejeita com 401 Unauthorized |
| Dev mode (sem secret) | `(True, "fallback_dev_mode")` | 200 | Aceita com warning de log |

### Fluxo de Validacao

```
1. Ler body bruto (await request.body())
2. Extrair header X-Signature
3. Chamar _verify_ml_signature()
   a. Se ML_CLIENT_SECRET nao configurado → aceita (dev mode)
   b. Se X-Signature ausente → rejeita 401
   c. Calcular HMAC-SHA256(body, secret)
   d. Comparar com compare_digest() (time-safe)
4. Se invalido → retorna 401
5. Se valido → continua com validacoes existentes
   - Parametros obrigatorios
   - ml_user_id no banco
   - Rate limiting
   - Processamento por topico
```

## Seguranca

### Protecao contra Timing Attacks
Usa `hmac.compare_digest()` em vez de `==` para evitar que o tempo de comparação revele informações sobre a assinatura correta.

```python
# CORRETO (time-safe)
if hmac.compare_digest(x_signature, expected_signature):
    ...

# INCORRETO (vulneravel a timing attack)
if x_signature == expected_signature:
    ...
```

### Fallback para Desenvolvimento
Sem `ML_CLIENT_SECRET` configurado, o endpoint:
- Aceita webhooks sem validacao
- Loga um warning
- Permite desenvolvimento/testes locais

Em producao, `ML_CLIENT_SECRET` DEVE estar configurado em variaveis de ambiente (Railway).

## Integracao com ML

### Como o ML envia a assinatura

O Mercado Livre envia o header:
```
X-Signature: sha256=<hmac>
```

Onde `<hmac>` é o resultado de:
```python
HMAC-SHA256(body_content, client_secret)
```

### Validacao local de testes

Para testar manualmente:

```bash
# 1. Gerar a assinatura esperada
BODY='{"resource":"MLB123456789","user_id":2050442871}'
SECRET="seu_client_secret"
SIGNATURE=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$SECRET" -hex | cut -d' ' -f2)

# 2. Fazer requisicao com header
curl -X POST http://localhost:8000/api/v1/notifications?user_id=2050442871&topic=orders \
  -H "X-Signature: $SIGNATURE" \
  -H "Content-Type: application/json" \
  -d "$BODY"
```

## Logging

Tentativas de webhook sao registradas:

**Sucesso:**
```
INFO: Webhook recebido e validado — user_id=2050442871 topic=orders
```

**Falha - Assinatura invalida:**
```
WARNING: Webhook rejeitado: assinatura invalida — esperava 715d00021c52...
```

**Falha - Header ausente:**
```
WARNING: Webhook rejeitado: header X-Signature ausente
```

**Dev mode:**
```
WARNING: Webhook: ML_CLIENT_SECRET nao configurado — aceitando sem validacao (dev mode)
```

## Variaveis de Ambiente

### Configuracao Obrigatoria (Producao)
```env
ML_CLIENT_SECRET=seu_secret_aqui
```

### Configuracao Local (Desenvolvimento)
Deixar em branco ou nao definir:
```env
ML_CLIENT_SECRET=
```

O sistema detecta e aplica fallback automaticamente.

## Impacto em Funcionalidade Existente

### Mantido
- Rate limiting (30s por user_id+topic)
- Validacao de parametros obrigatorios (user_id, topic)
- Validacao de ml_user_id no banco
- Processamento por topico (orders, items, questions)
- Logging de auditoria

### Novo
- Verificacao de assinatura HMAC (primeira validacao realizada)
- Retorno 401 para assinatura invalida

## Testes

Execute `test_webhook_signature.py` para validar a implementacao:

```bash
python test_webhook_signature.py
```

Testes incluem:
1. Assinatura valida → 200 OK
2. Assinatura invalida → 401 Unauthorized
3. Header ausente → 401 Unauthorized
4. Dev mode → 200 OK com warning
5. Protecao contra timing attacks

## Checklist de Deployment

- [ ] `ML_CLIENT_SECRET` configurado em Railway
- [ ] Webhook testado manualmente com assinatura valida
- [ ] Webhook testado manualmente com assinatura invalida
- [ ] Logs mostram validacao de assinatura
- [ ] Rate limiting continua funcionando
- [ ] Tasks de sync continuam sendo enfileiradas

## Referencia

- [Mercado Libre Webhooks](https://developers.mercadolibre.com.br/pt_br/notificacoes)
- [HMAC Time-Safe Comparison (Python docs)](https://docs.python.org/3/library/hmac.html#hmac.compare_digest)
