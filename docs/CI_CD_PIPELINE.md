# Pipeline CI/CD — MSM_Pro

## Visão Geral

O projeto MSM_Pro possui um pipeline CI/CD automatizado via **GitHub Actions** que executa:
1. **Backend Tests**: testes unitários Python + cobertura de código
2. **Frontend Tests & Build**: type-check + lint + vitest + build Vite

O pipeline roda em:
- **Push para `main` ou `staging`**
- **Pull Requests para `main` ou `staging`**

## Componentes

### 1. Backend Tests Job (`backend-tests`)

#### Ambiente
```yaml
SECRET_KEY: test-secret-key-for-unit-tests-32chars!!
ENVIRONMENT: test
ML_CLIENT_ID: test-client-id
ML_CLIENT_SECRET: test-client-secret
```

#### Passos
1. **Checkout** do código (actions/checkout@v4)
2. **Setup Python 3.12** com cache pip (baseado em `backend/requirements.txt`)
3. **Install deps**: pip + pytest + pytest-asyncio + pytest-cov
4. **Run tests**:
   ```bash
   cd backend
   python -m pytest tests/ -q \
     --ignore=tests/test_financeiro_features.py \
     --tb=short \
     --junitxml=test-results.xml \
     --cov=app --cov-report=xml --cov-report=term
   ```
   - **Ignora** `test_financeiro_features.py` (requer PostgreSQL)
   - **Gera** relatório JUnit XML + cobertura XML + termo
5. **Upload artifacts**:
   - `backend-test-results` (test-results.xml)
   - `backend-coverage` (coverage.xml)

#### Duração esperada
~1-2 minutos

---

### 2. Frontend Tests & Build Job (`frontend-tests`)

#### Ambiente
- **Node.js**: 20.x (matrix strategy)
- **Cache**: npm (baseado em `frontend/package-lock.json`)

#### Passos
1. **Checkout** do código
2. **Setup Node.js 20.x** com cache npm
3. **Install deps**: `npm ci` (instalação exata baseada em lock file)
4. **Type check**: `npm run type-check` (TypeScript strict)
5. **Lint**: `npm run lint` (ESLint + Prettier, não-bloqueante)
6. **Run tests**: `npm run test` (vitest runner mode)
7. **Build**: `npm run build` (tsc + vite build)
8. **Upload artifacts**: `frontend-build` (pasta `dist/`)

#### Duração esperada
~2-3 minutos

---

### 3. CI Status Check Job (`ci-status`)

#### Comportamento
- Aguarda `backend-tests` e `frontend-tests`
- Falha se qualquer job retornar status "failure"
- Bloqueia merge em PRs se falhar

---

## Fluxo de Execução

```
┌─────────────────────────────────────────┐
│  Push/PR criado em main ou staging      │
└──────────────┬──────────────────────────┘
               │
        ┌──────┴──────┐
        │             │
    ┌───▼────┐    ┌──▼──────┐
    │Backend │    │Frontend  │
    │ Tests  │    │ Tests &  │
    │        │    │  Build   │
    └───┬────┘    └──┬───────┘
        │            │
        └──────┬─────┘
               │
          ┌────▼─────┐
          │CI Status  │
          │  Check    │
          └────┬─────┘
               │
         ┌─────┴──────┐
         │            │
      ✓ PASS      ✗ FAIL
         │            │
      Merge       Block merge
      allowed      / comment
```

---

## Configurações e Variáveis

### Environment Variables
Definidas no workflow YAML (não em `.env`):

| Variável | Valor | Uso |
|----------|-------|-----|
| `SECRET_KEY` | `test-secret-key-for-unit-tests-32chars!!` | JWT tests |
| `ENVIRONMENT` | `test` | Modo teste |
| `ML_CLIENT_ID` | `test-client-id` | Mock OAuth |
| `ML_CLIENT_SECRET` | `test-client-secret` | Mock OAuth |

### Cache
- **Python**: Baseado em `backend/requirements.txt`
- **npm**: Baseado em `frontend/package-lock.json`

---

## Testes Ignorados

**Por quê?** Alguns testes requerem PostgreSQL real, que não está disponível em CI.

### Backend
- `tests/test_financeiro_features.py` — requer PostgSQL + dados

**Como desabilitar no código:**
```python
import pytest

@pytest.mark.skip(reason="Requires PostgreSQL")
def test_something():
    pass
```

---

## Relatórios e Artefatos

### Backend
- **test-results**: `backend/test-results.xml` (JUnit format)
- **coverage**: `backend/coverage.xml` (Cobertura format)

### Frontend
- **frontend-build**: `frontend/dist/` (artifacts de build)

Acesse em: **Actions → Run → Artifacts**

---

## Falhas Comuns e Soluções

| Sintoma | Causa | Solução |
|---------|-------|---------|
| `ModuleNotFoundError: No module named 'xxx'` | Dependência faltando | Adicionar a `backend/requirements.txt` + push |
| `TypeError: Cannot find module 'xxx'` | npm dependency faltando | Adicionar a `frontend/package.json` + `npm install` + commit `package-lock.json` |
| `SyntaxError` no Python | Code inválido | Rodar `black` e `isort` localmente |
| `Type error no TypeScript` | Type mismatch | Rodar `npm run type-check` localmente |
| `ESLint error` | Lint fail | Rodar `npm run lint` localmente |
| Timeout (> 10 min) | Teste travado ou compilação lenta | Adicionar timeout ou otimizar teste |

---

## Desenvolvimento Local

### Simular o Pipeline Localmente

#### Backend
```bash
cd backend

# Instalar dependências
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov

# Rodar testes (mesmo comando do CI)
export SECRET_KEY="test-secret-key-for-unit-tests-32chars!!"
export ENVIRONMENT="test"
python -m pytest tests/ -q --ignore=tests/test_financeiro_features.py --tb=short
```

#### Frontend
```bash
cd frontend

# Instalar dependências
npm ci

# Type check
npm run type-check

# Lint
npm run lint

# Testes
npm run test

# Build
npm run build
```

---

## Melhorias Futuras

- [ ] **Integration Tests**: adicionar testes contra PostgreSQL/Redis em Docker
- [ ] **SAST**: adicionar static analysis (bandit para Python, sonarqube)
- [ ] **Dependency Scanning**: Dependabot para alertas de vulnerabilidades
- [ ] **Codecov**: integração de relatórios de cobertura
- [ ] **Performance Testing**: benchmark de endpoints críticos
- [ ] **E2E Tests**: Playwright/Cypress para testes de UI completo
- [ ] **Deploy Staging**: auto-deploy em `staging` após tests passarem

---

## Links Úteis

- **GitHub Actions Docs**: https://docs.github.com/en/actions
- **Pytest Docs**: https://docs.pytest.org/
- **Vitest Docs**: https://vitest.dev/
- **Setup Python Action**: https://github.com/actions/setup-python
- **Setup Node Action**: https://github.com/actions/setup-node

---

## Contato

Para dúvidas sobre CI/CD, consulte:
- CLAUDE.md (projeto)
- Workflow: `.github/workflows/ci.yml`
- Último run: https://github.com/maikeo-code/MSM_Pro/actions
