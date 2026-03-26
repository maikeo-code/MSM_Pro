# Test Suite: API Endpoints Integration Tests

## Overview

**Arquivo**: `backend/tests/test_api_endpoints.py`

Suíte de 25 testes de integração para validar os routers FastAPI do MSM_Pro usando mocks HTTP, sem dependências externas (PostgreSQL, Redis, ML API).

**Objetivos**:
- Aumentar cobertura de testes dos routers (0% → 21.23%)
- Validar contrato das API endpoints
- Testar fluxos autenticados com mocks
- Documentar padrões de teste para FastAPI

---

## Cobertura

### Antes (17.42% total)
- Apenas 1 arquivo de teste unitário
- 0% cobertura de routers (auth, vendas, produtos, etc.)

### Depois (21.23% total)
- 25 novos testes de integração
- Auth router: ~50% de cobertura
- Vendas router: ~40% de cobertura
- Produtos router: 84% de cobertura
- Health/Root endpoints: 100%

---

## Estrutura dos Testes

### 1. **Fixtures Pytest** (linhas 31-101)

```python
# fake_user() — Usuário falso sem persistência
# fake_ml_account() — Conta ML falsa
# mock_async_session — Mock de AsyncSession
# valid_token() — JWT válido
# reset_overrides() — Limpa overrides a cada teste
# client_with_mocked_db — TestClient com get_db mockado
# client_with_auth — TestClient com DB + user autenticados
```

**Padrão importante**:
- `reset_overrides()` com `autouse=True` garante isolamento entre testes
- `fake_user` usa `hashed_password` (não `password_hash`)

### 2. **Classes de Testes**

#### TestHealthEndpoint (3 testes)
```python
✓ test_health_returns_200() — Status code 200
✓ test_health_response_format() — Campos {status, version}
✓ test_health_no_db_dependency() — Sem banco de dados
```

**Endpoint**: `GET /health`

#### TestRootEndpoint (2 testes)
```python
✓ test_root_returns_200()
✓ test_root_response_structure() — {message, timestamp, version_check}
```

**Endpoint**: `GET /`

#### TestAuthLogin (2 testes)
```python
✓ test_login_with_valid_credentials() — Retorna token
✓ test_login_with_invalid_credentials() — 401
```

**Endpoint**: `POST /api/v1/auth/login`

**Mocking**:
```python
patch("app.auth.service.authenticate_user", new_callable=AsyncMock)
patch("app.auth.service.create_access_token")
```

#### TestAuthMe (2 testes)
```python
✓ test_get_me_returns_current_user() — Retorna usuário autenticado
✓ test_get_me_without_token() — 403/401 sem token
```

**Endpoint**: `GET /api/v1/auth/me`

**Dependência**: `get_current_user` — mocked para retornar `fake_user`

#### TestAuthRefresh (1 teste)
```python
✓ test_refresh_token_returns_new_token() — Token renovado
```

**Endpoint**: `POST /api/v1/auth/refresh`

#### TestAuthMLConnect (1 teste)
```python
✓ test_ml_connect_returns_auth_url() — URL OAuth válida
```

**Endpoint**: `GET /api/v1/auth/ml/connect`

#### TestProdutosListEmpty (1 teste)
```python
✓ test_list_produtos_empty() — Lista vazia mockada
```

**Endpoint**: `GET /api/v1/produtos/`

**Mocking**:
```python
patch("app.produtos.service.list_products", new_callable=AsyncMock)
```

#### TestListingsListEmpty (2 testes)
```python
✓ test_list_listings_empty() — Lista vazia
✓ test_list_listings_without_auth() — 401/403 sem token
```

**Endpoint**: `GET /api/v1/listings/`

#### TestKPISummary (1 teste)
```python
✓ test_kpi_summary_returns_data() — KPIs por período
```

**Endpoint**: `GET /api/v1/listings/kpi/summary`

**Mocking**:
```python
patch("app.vendas.router.service.get_kpi_by_period", new_callable=AsyncMock)
```

#### TestErrorHandling (3 testes)
```python
✓ test_nonexistent_endpoint_returns_404()
✓ test_invalid_json_returns_422()
✓ test_method_not_allowed_returns_405()
```

#### TestDependencyInjection (3 testes)
```python
✓ test_get_current_user_dependency_mocked() — Verifica override
✓ test_get_db_dependency_mocked() — Verifica override
✓ test_override_cleared_after_test() — Isolamento
```

#### TestResponseSchemas (2 testes)
```python
✓ test_health_response_schema() — Validação de tipos
✓ test_token_response_schema() — Token + user
```

#### TestRateLimiting (1 teste)
```python
✓ test_rate_limit_can_be_disabled() — Configuração
```

#### TestAuthFlow (1 teste) — Cenário completo
```python
✓ test_login_then_access_protected_route()
  1. Login com credenciais
  2. Extrai token da resposta
  3. Usa token para acessar rota protegida
  4. Valida que retorna dados do usuário
```

---

## Técnicas de Mocking

### 1. **Dependency Injection Override**

```python
# Mockar get_db
async def override_get_db():
    yield mock_async_session
app.dependency_overrides[get_db] = override_get_db

# Mockar get_current_user
async def override_get_current_user(token: str = None):
    return fake_user
app.dependency_overrides[get_current_user] = override_get_current_user
```

### 2. **Service Patching**

```python
# Mockar função de serviço para evitar DB
with patch("app.auth.service.authenticate_user", new_callable=AsyncMock) as mock:
    mock.return_value = fake_user
```

### 3. **AsyncMock para Funções Assíncronas**

```python
# Para AsyncMock funcionar com "await"
with patch("app.vendas.service_kpi.get_kpi_by_period", new_callable=AsyncMock) as mock:
    mock.return_value = {...}  # Define return value (não return_value ao chamar)
```

### 4. **Fixtures com Autouse**

```python
@pytest.fixture(autouse=True)
def reset_overrides():
    """Limpa overrides antes/depois de cada teste."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
```

---

## Executar os Testes

### Rodar todos os testes
```bash
cd backend
python -m pytest tests/test_api_endpoints.py -v
```

### Rodar teste específico
```bash
python -m pytest tests/test_api_endpoints.py::TestAuthLogin::test_login_with_valid_credentials -v
```

### Com coverage
```bash
python -m pytest tests/test_api_endpoints.py --cov=app --cov-report=html
```

### Sem captura de output (debug)
```bash
python -m pytest tests/test_api_endpoints.py -v -s
```

---

## Padrões Aplicados

### ✓ Isolamento entre testes
- `reset_overrides()` fixture com `autouse=True`
- Cada teste limpa `app.dependency_overrides`

### ✓ Sem dependências externas
- TestClient (não HTTPClient assíncrono)
- Mocks de AsyncSession
- Nenhuma conexão real ao PostgreSQL/Redis

### ✓ Fixtures reutilizáveis
- `fake_user`, `fake_ml_account`, `valid_token`
- `client_with_mocked_db`, `client_with_auth`

### ✓ Validação de esquemas
- Testa presença de campos esperados
- Valida tipos (str, int, dict, list)

### ✓ Cenários realistas
- Teste de autenticação completo
- Endpoints protegidos vs públicos
- Erros HTTP (404, 422, 405)

---

## Limitações Conhecidas

1. **Não testa DB logic**
   - Só valida endpoint contract
   - Para lógica de DB, usar testes unitários

2. **Não testa rate-limiting real**
   - Rate limit é testado em `test_rate_limiting.py`
   - Aqui apenas verifica se setting existe

3. **Não testa webhook validations**
   - Assinatura HMAC testada em `test_webhook_signature.py`
   - Rota `/api/v1/notifications` não incluída nesta suíte

4. **TestClient vs AsyncClient**
   - TestClient é síncrono (mais simples)
   - Para casos complexos, usar `httpx.AsyncClient`

---

## Próximas Melhorias

1. **Adicionar testes para mais routers**
   - `TestConcorrenciaRouter` (concorrência)
   - `TestAlertasRouter` (alertas)
   - `TestFinanceiroRouter` (financeiro)
   - `TestAdsRouter` (publicidade)

2. **Testes paramétricos**
   ```python
   @pytest.mark.parametrize("status_code", [401, 403])
   def test_auth_errors(status_code):
       ...
   ```

3. **Snapshot testing**
   - Validar estrutura completa de respostas JSON

4. **Performance testing**
   - Medir tempo de resposta de endpoints

5. **WebSocket tests**
   - Quando WebSocket for implementado

---

## Referências

- [FastAPI Testing Documentation](https://fastapi.tiangolo.com/tutorial/testing/)
- [Pytest Fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [SQLAlchemy Async Testing](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)

---

## Autores

- Claude Code — Implementação inicial (25 testes)
- MSM_Pro Team — Manutenção contínua

**Data**: 2026-03-26
**Versão**: 1.0
