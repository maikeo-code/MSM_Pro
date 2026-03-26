# Unit Tests para Módulo Jobs — MSM_Pro

## Arquivo Criado
- `/backend/tests/test_tasks_logic.py` (522 linhas, 31 testes)

## O Que é Testado

### 1. **run_async() — tasks_helpers.py**
Helper que executa coroutines assíncronas dentro de tasks Celery síncronas.

**6 testes:**
- Executa coroutine simples e retorna resultado
- Manipula coroutines com await interno
- Propaga exceções corretamente
- Retorna dicts sem problema
- Fecha event loop após execução
- Lida com coroutines aninhadas

**Exemplo:**
```python
async def simple_coro():
    return 42

result = run_async(simple_coro())
assert result == 42
```

### 2. **Lock Key Format — tasks_lock.py**
Distributed lock baseado em Redis para prevenir execução duplicada de tasks.

**8 testes:**
- LOCK_PREFIX definido como "celery_lock:"
- Lock keys incluem prefix + task name
- Cada task tem lock key única
- acquire_task_lock retorna boolean
- Redis.set chamado com nx=True (atomic)
- Redis.delete chamado no release
- Graceful fallback se Redis está down (retorna True para prosseguir)
- Release não falha se Redis down

**Exemplo:**
```python
# Lock key para sync_all_snapshots
lock_key = f"{LOCK_PREFIX}sync_all_snapshots"
# Resultado: "celery_lock:sync_all_snapshots"
```

### 3. **Task Registration — tasks.py**
Verifica que todas as tasks esperadas estão registradas.

**5 testes:**
- 11 funções async importadas (_sync_ads_async, _evaluate_alerts_async, etc)
- 11 task decorators definidos (sync_listing_snapshot, sync_all_snapshots, etc)
- Lock functions importadas (acquire_task_lock, release_task_lock)
- run_async importado
- celery_app importado

### 4. **Sync Log Helpers — tasks_helpers.py**
Funções para criar e finalizar registros de sincronização.

**3 testes:**
- _create_sync_log é callable
- _finish_sync_log é callable
- Ambas têm signatures corretas (parâmetros esperados)

### 5. **Task Configuration**
Valida configurações dos task decorators.

**3 testes:**
- sync_listing_snapshot tem max_retries=3
- sync_all_snapshots é callable e é task Celery
- Todas as tasks seguem padrão "app.jobs.tasks.*"

### 6. **Async Lock Integration**
Testa padrão comum: acquire → work → finally release

**2 testes:**
- Padrão async: await acquire → return/try/finally release
- run_async com lock pattern (simulated)

### 7. **Edge Cases**
Cenários extremos e tratamento de erros.

**4 testes:**
- run_async com None return
- run_async com {} (dict vazio)
- Lock keys com caracteres especiais/números
- acquire_task_lock retorna False se lock já está held

---

## Como Rodar

```bash
# Todos os testes do jobs
pytest tests/test_tasks_logic.py -v

# Um test class específico
pytest tests/test_tasks_logic.py::TestRunAsync -v

# Um teste específico
pytest tests/test_tasks_logic.py::TestRunAsync::test_run_async_executes_simple_coroutine -v

# Rápido (sem output verbose)
pytest tests/test_tasks_logic.py -q
```

## Resultado

```
============================= 31 passed in 12.88s =============================
```

### Breakdown:
- TestRunAsync: 6/6 PASSED
- TestLockKeyFormat: 8/8 PASSED
- TestTaskRegistration: 5/5 PASSED
- TestSyncLogHelpers: 3/3 PASSED
- TestTaskConfiguration: 3/3 PASSED
- TestAsyncLockIntegration: 2/2 PASSED
- TestEdgeCases: 4/4 PASSED

---

## O Que NÃO é Testado (Por Design)

1. **Redis Interactions** — todo Redis é mockado com AsyncMock
2. **AsyncSession / Database** — nenhum teste toca o banco
3. **Full Task Execution** — não simula Celery worker real
4. **Network Calls** — não chama API do ML
5. **Celery Retry Logic** — não testa @self.retry

Isto é intencional: testes unitários devem ser **rápidos, isolados, determinísticos**.
Para testar integração com Redis/Celery/DB, usar testes de integração separados.

---

## Padrões Usados

### 1. **Mocks para Dependências Externas**
```python
@patch("app.jobs.tasks_lock.aioredis.from_url")
async def test_lock_acquire(self, mock_redis_from_url):
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis_from_url.return_value = mock_redis
    # ... test code
```

### 2. **Async Tests com @pytest.mark.asyncio**
```python
@pytest.mark.asyncio
async def test_acquire_task_lock_returns_boolean(self):
    result = await acquire_task_lock("test_task", timeout=600)
    assert isinstance(result, bool)
```

### 3. **Exception Testing**
```python
with pytest.raises(ValueError, match="test error"):
    run_async(coro_raises())
```

### 4. **Multiple Assertions per Test**
```python
result = run_async(coro_returns_dict())
assert isinstance(result, dict)
assert result["status"] == "ok"
assert result["count"] == 10
```

---

## Próximas Melhorias

1. **Adicionar testes para tasks_listings.py** (sync logic)
2. **Testes para tasks_tokens.py** (token refresh)
3. **Testes para tasks_competitors.py** (competitor sync)
4. **Integration tests** com Redis real (pytest fixture)
5. **Coverage report** (pytest-cov, target > 80%)

---

## Arquivos Relacionados

- Backend: `/backend/app/jobs/`
  - `tasks_helpers.py` — run_async, _create_sync_log, _finish_sync_log
  - `tasks_lock.py` — acquire_task_lock, release_task_lock
  - `tasks.py` — task definitions (11 tasks Celery)

- Tests:
  - `/backend/tests/test_tasks_logic.py` — este arquivo
  - `/backend/tests/conftest.py` — fixtures compartilhadas (db fixture)
  - `/backend/tests/test_config.py` — config validation tests

- Docs:
  - `/backend/app/jobs/` — docstrings de cada task
  - `/MSM_Pro/CLAUDE.md` — regras de jobs/tasks
