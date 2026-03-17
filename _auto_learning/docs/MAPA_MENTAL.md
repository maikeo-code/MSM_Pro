# MAPA MENTAL — MSM_Pro (Ciclo 5)

## Arquitetura
```
[Frontend React 18]
    ├── 12 paginas, 11 services, 1 store Zustand
    ├── TanStack Query (56 hooks)
    ├── Tailwind + shadcn/ui
    └── Vite + Express SPA

[API FastAPI]
    ├── 9 routers, ~50 endpoints
    ├── 15 modelos SQLAlchemy
    ├── JWT auth (PyJWT 2.9.0)
    ├── OAuth ML multi-conta
    ├── Global exception handler
    └── CORS regex Railway

[PostgreSQL 16]
    ├── 13 migrations Alembic
    ├── Tokens OAuth encriptados (Fernet)
    ├── pool_size=10, max_overflow=20
    ├── pool_timeout=30, pool_recycle=1800
    └── Railway managed

[Redis 7 + Celery]
    ├── 8 tasks agendadas
    ├── sync diario 06:00 BRT
    ├── refresh tokens 4h
    ├── alertas 2h
    └── orders 2h
```

## Score por Area (Ciclo 5)
| Area | Score | Tendencia |
|------|-------|-----------|
| Features | 75 | estavel |
| Deploy | 70 | estavel |
| Frontend | 60 | estavel |
| Security | 55 | subindo (era 20) |
| Architecture | 55 | estavel |
| Code Quality | 50 | subindo (era 40) |
| Error Handling | 45 | subindo (era 25) |
| Testing | 25 | subindo (era 5) |

## Problemas Resolvidos (Ciclos 1-5)
1. Tokens OAuth em plaintext → EncryptedString Fernet
2. python-jose CVE → PyJWT 2.9.0
3. Sem error handler global → @app.exception_handler
4. Docs expostos em producao → ocultos
5. Health leak environment → removido
6. DB sem pool_timeout → adicionado
7. ReactQueryDevtools em producao → dev-only
8. 2 testes → 28 testes

## Problemas Pendentes
1. vendas/service.py monolitico (2109 linhas)
2. jobs/tasks.py grande (1366 linhas)
3. AnuncioDetalhe.tsx grande (1314 linhas)
4. Webhook sem autenticacao
5. asyncio.Lock entre Celery workers
6. Cobertura testes ~15% (meta: 60%)
7. CI/CD pipeline inexistente
8. Flower sem autenticacao

## 5 Regras Aprendidas
1. EncryptedString para tokens
2. PyJWT (nao python-jose)
3. Exception handler global
4. pool_timeout/recycle no engine
5. DevTools dev-only

## 3 Padroes Descobertos
1. Anti-pattern: comentario ≠ codigo
2. Success: TypeDecorator transparente
3. Success: testes isolados de deps
