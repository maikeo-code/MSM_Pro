# Plano: Docker e Deploy Hardening
Data: 2026-03-13
Baseado em: Ciclo 6 — DevOps Audit (22 issues)
Prioridade: P1

## Acoes Imediatas

### 1. Non-root Docker user (backend + frontend)
- backend/Dockerfile: Adicionar `RUN addgroup --system app && adduser --system --ingroup app app` + `USER app`
- Dockerfile.frontend: Adicionar `USER node`

### 2. Security headers em server.js
- Instalar `helmet` e `compression` em server-package.json
- Adicionar `app.use(helmet())` e `app.use(compression())`

### 3. Substituir python-jose por PyJWT
- requirements.txt: Trocar `python-jose[cryptography]==3.3.0` por `PyJWT==2.9.0`
- Atualizar imports em auth/service.py e core/deps.py

### 4. .dockerignore
- Criar backend/.dockerignore: __pycache__, tests/, *.pyc, .env

### 5. Multi-stage build
- backend/Dockerfile: Stage 1 (builder com gcc), Stage 2 (runtime slim sem gcc)

### 6. Config defaults seguros
- config.py: debug=False, environment="production"

## Status: PENDENTE
