# CORS Hardening — MSM_Pro Backend

## Mudanças Implementadas

### Antes (Vulnerável)
```python
# main.py — Regex genérico permitia QUALQUER subdomínio Railway
allow_origin_regex=r"https://.*\.up\.railway\.app",
```

**Risco**: Qualquer aplicação deployada no Railway com um subdomínio `.up.railway.app` poderia fazer requisições autenticadas ao backend MSM_Pro.

### Depois (Hardened)
```python
# main.py — Lista explícita de origens permitidas
_cors_origins: list[str] = [
    settings.frontend_url,
    "http://localhost:5173",
    "http://localhost:3000",
    "https://msmprofrontend-production.up.railway.app",
]

# Permitir origens extras via env var CORS_ORIGINS (comma-separated)
if settings.cors_origins:
    _cors_origins.extend(
        o.strip() for o in settings.cors_origins.split(",") if o.strip()
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,  # Lista explícita
    # Removido: allow_origin_regex  ← vulnerabilidade eliminada
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)
```

## Arquitetura

### Origens Padrão (hardcoded)
- `settings.frontend_url` — URL do frontend configurável
- `http://localhost:5173` — Vite dev server local
- `http://localhost:3000` — Express fallback local
- `https://msmprofrontend-production.up.railway.app` — Frontend em produção Railway

### Origens Extras (via env var)
Para adicionar domínios personalizados sem alterar código:

```bash
# .env ou Railway environment variables
CORS_ORIGINS="https://custom.example.com,https://another.domain.com"
```

A aplicação lê e expande automaticamente.

## Configuração

### Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `FRONTEND_URL` | `http://localhost:5173` | URL do frontend (dev: Vite, prod: domínio) |
| `CORS_ORIGINS` | (vazio) | Origens extras (comma-separated) |

### Exemplo Railway (production)
```
FRONTEND_URL=https://msmprofrontend-production.up.railway.app
CORS_ORIGINS=https://meu-dominio-customizado.com
ENVIRONMENT=production
SECRET_KEY=<seu-secret-key-aqui>
```

## Logging

Ao iniciar, o backend loga as origens configuradas:
```
INFO: CORS configured for origins: ['https://msmprofrontend-production.up.railway.app', 'http://localhost:5173', 'http://localhost:3000']
```

## Teste de Validação

### Origem Permitida (200 OK)
```bash
curl -X OPTIONS https://msmpro-production.up.railway.app/api/v1/listings \
  -H "Origin: https://msmprofrontend-production.up.railway.app" \
  -H "Access-Control-Request-Method: GET"

# Resposta inclui header:
# Access-Control-Allow-Origin: https://msmprofrontend-production.up.railway.app
```

### Origem Bloqueada (sem header CORS)
```bash
curl -X OPTIONS https://msmpro-production.up.railway.app/api/v1/listings \
  -H "Origin: https://random-railway-app.up.railway.app" \
  -H "Access-Control-Request-Method: GET"

# Resposta NÃO inclui Access-Control-Allow-Origin
# Browser bloqueará requisição
```

## Impacto

- ✅ **Segurança aumentada** — CORS restrictivo, whitelist explícito
- ✅ **Backward compatible** — `settings.cors_origins` permite extensão
- ✅ **Fácil administração** — adicionar domínio = adicionar env var
- ✅ **Auditável** — todas as origens permitidas estão explícitas
- ✅ **Logging** — origens configuradas registradas no startup

## Mudanças de Arquivo

- `backend/app/main.py` — Removido `allow_origin_regex`, mantém `allow_origins` explícito
- `backend/app/core/config.py` — Adicionado comentário sobre hardening CORS
- `backend/tests/test_webhook_signature.py` — Movido de raiz para local correto

## Referência Completa

Ver:
- FastAPI CORS docs: https://fastapi.tiangolo.com/tutorial/cors/
- OWASP CORS: https://owasp.org/www-community/Cross-Origin_Resource_Sharing_(CORS)
