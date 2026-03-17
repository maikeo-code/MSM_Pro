# MAPA MENTAL — MSM_Pro (Ciclo 20)

## Arquitetura
```
[Frontend React 18]
    ├── 12 paginas, 11 services, 1 store Zustand
    ├── TanStack Query (56 hooks)
    ├── Tailwind + shadcn/ui
    ├── ReactQueryDevtools dev-only (lazy)
    └── Vite + Express SPA (Docker)

[API FastAPI]
    ├── 10 routers, ~50 endpoints
    ├── 15 modelos SQLAlchemy
    ├── JWT auth (PyJWT 2.9.0)
    ├── OAuth ML multi-conta
    ├── Global exception handler (safe 500)
    ├── Docs ocultos em producao
    ├── Webhook validacao basica
    └── CORS regex Railway

[PostgreSQL 16]
    ├── 13 migrations Alembic
    ├── Tokens OAuth encriptados (Fernet EncryptedString)
    ├── pool_size=10, max_overflow=20, timeout=30, recycle=1800
    └── Railway managed

[Redis 7 + Celery]
    ├── 8 tasks agendadas
    ├── sync diario 06:00 BRT
    ├── refresh tokens 4h
    ├── alertas 2h
    └── orders 2h

[CI/CD]
    ├── GitHub Actions (.github/workflows/test.yml)
    ├── Railway auto-deploy on push
    └── 124 testes automatizados
```

## Score por Area (Ciclo 20)
| Area | Inicio | Agora | Delta |
|------|--------|-------|-------|
| Features | 75 | 75 | = |
| Deploy | 70 | 78 | +8 |
| Code Quality | 40 | 73 | +33 |
| Frontend | 60 | 70 | +10 |
| Testing | 5 | 65 | +60 |
| Security | 20 | 63 | +43 |
| Error Handling | 25 | 60 | +35 |
| Architecture | 55 | 65 | +10 |
| **GLOBAL** | **43** | **74** | **+31** |

## Problemas Resolvidos (20 ciclos)
1. Tokens OAuth plaintext → Fernet EncryptedString
2. python-jose CVE → PyJWT 2.9.0
3. Sem error handler → @app.exception_handler global
4. Docs em producao → ocultos
5. Health leak environment → removido
6. DB sem pool timeout → pool_timeout=30, pool_recycle=1800
7. ReactQueryDevtools em prod → lazy dev-only
8. 2 testes → 124 testes
9. vendas/service.py 2116 linhas → 7 submodulos
10. debug=True default → False (secure by default)
11. Webhook sem validacao → user_id + topic required
12. CI/CD inexistente → GitHub Actions
13. Magic numbers → constants.py
14. 8 bug fixes runtime (None guards, MLClient leak, price sort)
15. Frontend limpo (0 console.log, 0 hardcoded URLs)

## Problemas Pendentes
1. jobs/tasks.py grande (1366 linhas) — refatorar como vendas
2. AnuncioDetalhe.tsx grande (1314 linhas)
3. asyncio.Lock entre Celery workers
4. Flower sem autenticacao
5. OAuth state deveria ser CSRF nonce
6. Cobertura de testes: ~40% (meta: 60%)

## 9 Regras Aprendidas
1. EncryptedString para tokens OAuth
2. PyJWT (nao python-jose)
3. Exception handler global obrigatorio
4. pool_timeout/recycle no engine
5. DevTools dev-only
6. sum() com or 0 em colunas nullable
7. async with MLClient (context manager)
8. debug=False por padrao
9. Services >500 linhas devem ser divididos

## 3 Padroes Descobertos
1. Anti-pattern: comentario ≠ codigo
2. Success: TypeDecorator transparente
3. Success: testes isolados de deps pesadas
