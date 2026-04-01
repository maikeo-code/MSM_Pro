# Rate Limiting na MSM_Pro API

## Visão Geral

A API MSM_Pro implementa rate limiting global usando **slowapi** para proteger endpoints críticos contra brute-force e abuso.

## Limites Configurados

| Endpoint | Limite | Chave | Descrição |
|----------|--------|-------|-----------|
| `/api/v1/auth/login` | 5/minuto | IP | Autentica usuário |
| `/api/v1/auth/register` | 3/hora | IP | Registra novo usuário |
| `/api/v1/*` (geral) | 120/minuto | User ID ou IP | Todos os outros endpoints |

## Como Funciona

### Chave de Rate Limiting

O sistema usa dois tipos de chaves:

1. **User ID** (usuários autenticados):
   - Extrai `user_id` do token JWT no header `Authorization: Bearer <token>`
   - Formato: `user:{user_id}`

2. **IP Address** (requisições anônimas):
   - Extrai IP do client via `request.client.host`
   - Formato: IP direto (ex: `192.168.1.1`)

### Resposta quando Limite é Atingido

Status HTTP: `429 Too Many Requests`

```json
{
  "detail": "Too many requests. Please try again later.",
  "limit": "5 per minute"
}
```

## Configuração

### Variáveis de Ambiente

```bash
# Habilitar/desabilitar rate limiting (default: true)
RATE_LIMIT_ENABLED=true
```

### Em Testes

Rate limiting é automaticamente **desabilitado** em testes:

```python
os.environ["RATE_LIMIT_ENABLED"] = "false"
```

Isso evita flakiness em testes que fazem múltiplas requisições rápidas.

## Implementação Técnica

### Arquivo Principal

`backend/app/core/rate_limit.py`

### Funções Principais

#### `setup_rate_limiting(app: FastAPI)`
Configura middleware e exception handler. Chamada em `main.py` após criar a app.

```python
app = FastAPI(...)
setup_rate_limiting(app)
```

#### `get_rate_limit_key(request: Request) -> str`
Extrai a chave de rate limiting (user ID ou IP).

#### Funções Helper

- `rate_limit_auth_login()` → `"5/minute"` ou `None`
- `rate_limit_auth_register()` → `"3/hour"` ou `None`
- `rate_limit_api_general()` → `"120/minute"` ou `None`

### Decoradores nos Endpoints

```python
from app.core.rate_limit import limiter, rate_limit_auth_login

@router.post("/login")
@limiter.limit(rate_limit_auth_login())
async def login(request: Request, ...):
    # request param é obrigatório com @limiter.limit()
    pass
```

## Testes

14 testes de rate limiting em `backend/tests/test_rate_limiting.py`:

```bash
pytest tests/test_rate_limiting.py -v
```

### Cobertura de Testes

- ✓ Configuração carrega corretamente
- ✓ Módulo pode ser importado
- ✓ Decoradores estão nos endpoints
- ✓ Funções retornam strings corretas
- ✓ Rate limit pode ser desabilitado
- ✓ slowapi está em requirements.txt
- ✓ Exception handler funciona
- ✓ Chave de rate limit é extraída corretamente

## Comportamento por Cenário

### Cenário 1: Usuário autenticado faz muitas requisições

1. Token JWT é validado
2. `user_id` é extraído
3. Limite é por usuário: `120/minuto`
4. Se ultrapassar: 429 Too Many Requests

### Cenário 2: IP faz brute-force em /auth/login

1. Sem token (anônimo)
2. IP é extraído
3. Limite é por IP: `5/minuto`
4. Após 5 tentativas em 1 minuto: 429

### Cenário 3: Usuário novo se registra múltiplas vezes

1. Sem token (anônimo)
2. IP é extraído
3. Limite é por IP: `3/hora`
4. Após 3 registros em 1 hora: 429

## Considerações de Produção

### Railway/Docker

Rate limiting funciona com IP real graças a:

- Header `X-Forwarded-For` (proxy reverso detecta IP real)
- `get_remote_address()` do slowapi já trata isso

### Redis (Opcional)

A implementação atual usa in-memory storage (rápido, mas não compartilha entre workers).

Para compartilhar entre múltiplos workers Celery:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379/3"  # ou env var
)
```

## Troubleshooting

### "Rate limit exceeded" mas usuário não fez tantas requisições

- Verificar se RATE_LIMIT_ENABLED está realmente true
- Verificar IP (pode estar atrás de proxy)
- Limpar cache da aplicação

### Rate limiting não funciona em testes

- ✓ Intencional - desabilitado para testes (`RATE_LIMIT_ENABLED=false`)
- Remover a linha de env var em conftest.py se quiser testar rate limit real

## Futuras Melhorias

1. Storage em Redis (para múltiplos workers)
2. Rate limiting por endpoint adicional (ex: /api/v1/vendas)
3. Whitelist de IPs confiáveis
4. Rate limiting customizado por tenant/usuário
5. Metrics de rate limiting (Dashboard em Prometheus)

## Referências

- [slowapi Documentation](https://github.com/laurentS/slowapi)
- [OWASP Rate Limiting](https://owasp.org/www-community/attacks/Rate_Limiting)
