# Plano: Security Hardening P0
Data: 2026-03-13
Baseado em: Ciclo 3 — Security Audit Findings 1, 3, 7 + Consenso #1
Prioridade: P0

## Problema Identificado
3 vulnerabilidades que devem ser corrigidas imediatamente:
1. JWT secret key tem fallback inseguro hardcoded
2. /auth/login aceita requests ilimitados (brute force)
3. debug=True por padrao em producao

## Solucao Proposta

### 1. JWT Startup Guard (5 min)
Em main.py, adicionar validacao no startup:
```python
if settings.secret_key == "insecure-default-secret-change-in-production":
    raise RuntimeError("SECRET_KEY must be overridden in production")
```

### 2. Rate Limit em Login (30 min)
Instalar slowapi e adicionar decorator no /auth/login:
- Max 5 tentativas por IP por minuto
- Max_length=128 no UserLogin.password schema

### 3. Config Defaults Seguros (5 min)
Mudar defaults em config.py:
- debug: bool = False
- environment: str = "production"

## Arquivos Afetados
- backend/app/main.py
- backend/app/core/config.py
- backend/app/auth/router.py
- backend/app/auth/schemas.py
- backend/requirements.txt (slowapi)

## Riscos
- Startup guard pode impedir deploy se SECRET_KEY nao estiver no Railway env
- Mitigacao: verificar Railway env vars antes do deploy

## Metricas de Sucesso
- App nao inicia sem SECRET_KEY valido
- Login retorna 429 apos 5 tentativas em 1 minuto
- /health nao expoe "environment: development"

## Status: PENDENTE
