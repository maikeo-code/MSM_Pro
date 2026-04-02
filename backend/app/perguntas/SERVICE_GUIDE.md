# Service Layer — Módulo Perguntas Q&A

## Arquivo
- **Path**: `backend/app/perguntas/service.py`
- **Linhas**: 655
- **Status**: Concluído e validado
- **Commit**: ffbd9a0

## Funcionalidades Implementadas

### 1. `async def sync_questions_for_account(db, account, statuses=None) -> dict`

Sincroniza perguntas de uma conta ML para o banco local via upsert.

**Lógica:**
- Itera sobre statuses: UNANSWERED, ANSWERED (padrão)
- Para cada status, busca até 50 perguntas da API ML via `client.get_received_questions()`
- Para cada pergunta:
  - Extrai `ml_question_id`, `text`, `mlb_id`, `buyer_id`, `buyer_nickname`
  - Tenta encontrar `listing_id` local pelo `mlb_id`
  - Parse de datas ISO com fallback para `now` em caso de erro
  - **Upsert**: se `ml_question_id` existe, atualiza; senão, cria novo `Question`
  - Atualiza campos: `status`, `answer_text`, `answer_date`, `answer_source="ml_direct"`, `synced_at`
  
**Tratamento de erros:**
- Try/except por pergunta (falha em 1 não bloqueia outras)
- Try/except por status (falha em 1 status não bloqueia outros)
- Try/except geral por conta
- Logging detalhado de cada etapa

**Retorno:**
```python
{
  "synced": int,     # total processado
  "new": int,        # criadas
  "updated": int,    # atualizadas
  "errors": int      # erros encontrados
}
```

---

### 2. `async def sync_all_questions() -> dict`

Sincroniza perguntas de TODAS as contas ML ativas. Usar em Celery task diária.

**Lógica:**
- Cria sessão `AsyncSessionLocal()`
- Seleciona todas `MLAccount` com `is_active=True` e `access_token` não-nulo
- Chama `sync_questions_for_account()` para cada conta
- Agrega estatísticas: `total_synced`, `new`, `updated`, `accounts_processed`, `errors`

**Closing:**
- `await db.close()` no finally

**Retorno:**
```python
{
  "total_synced": int,
  "new": int,
  "updated": int,
  "accounts_processed": int,
  "errors": int
}
```

---

### 3. `async def list_questions_from_db(db, user_id, status=None, ml_account_id=None, mlb_id=None, search=None, offset=0, limit=20) -> tuple[list[Question], int]`

Lista perguntas do banco com filtros avançados e paginação.

**Filtros:**
- `user_id`: obrigatório (filtra contas do usuário via JOIN MLAccount)
- `status`: opcional (UNANSWERED, ANSWERED, etc)
- `ml_account_id`: opcional (filtra por conta específica)
- `mlb_id`: opcional (filtra por anúncio)
- `search`: opcional (ILIKE em `text` ou `buyer_nickname`)

**Ordenação:**
- `ORDER BY Question.date_created DESC` (mais recente primeiro)

**Paginação:**
- `OFFSET offset LIMIT limit`

**Retorno:**
```python
(
  [Question, Question, ...],  # lista de objetos
  int                         # total de registros (sem offset/limit)
)
```

---

### 4. `async def answer_question_and_track(db, question_id, text, account, source="manual", template_id=None, suggestion_was_edited=False) -> dict`

Responde uma pergunta via API ML e registra no banco com tracking.

**Fluxo:**
1. Busca `Question` pelo `id`
2. Valida propriedade: `question.ml_account_id == account.id`
3. Chama `client.answer_question(question.ml_question_id, text)` via API ML
4. Se sucesso:
   - Atualiza `question`: `answer_text`, `answer_date`, `answer_source`, `status="ANSWERED"`, `updated_at=now`
   - Cria `QuestionAnswer` com `status="sent"`, `source`, `template_id`, `sent_at=now`
   - Se `source="ai"` e existe `QASuggestionLog`: atualiza `was_used=True`, `was_edited=suggestion_was_edited`
   - Commit
5. Se falha:
   - Cria `QuestionAnswer` com `status="failed"`, `error_message=str(exc)`
   - Commit (mesmo assim)
   - Retorna erro

**Tratamento:**
- `MLClientError` → registra falha, não levanta exceção
- Exception genérica → retorna erro formatado

**Retorno:**
```python
{
  "status": "success" | "error",
  "message": str,
  "response": dict | None,      # resposta da API ML (se sucesso)
  "error_code": str             # se erro
}
```

---

### 5. `async def get_question_stats(db, user_id, ml_account_id=None) -> dict`

Retorna estatísticas agregadas de perguntas.

**Métricas calculadas:**
- `total`: count total
- `unanswered`: count onde `status="UNANSWERED"`
- `answered`: count onde `status="ANSWERED"`
- `urgent`: count onde `status="UNANSWERED"` AND `date_created < now - 24h`
- `avg_response_time_hours`: avg de `(answer_date - date_created) / 3600`
  - Apenas para perguntas com `answer_date` não-nulo
  - Usa `func.extract("epoch", ...)` do PostgreSQL
  - Retorna `None` se não há respondidas
- `by_account`: dict `{ "account_nickname": count, ... }`

**Filtros:**
- `user_id`: obrigatório
- `ml_account_id`: opcional (filtra uma conta específica)

**Retorno:**
```python
{
  "total": int,
  "unanswered": int,
  "answered": int,
  "urgent": int,
  "avg_response_time_hours": float | None,
  "by_account": { "nickname1": 5, "nickname2": 3 }
}
```

---

### 6. `async def get_questions_by_listing(db, user_id, mlb_id) -> list[Question]`

Busca histórico completo de Q&A de um anúncio.

**Lógica:**
- JOIN com MLAccount para validar propriedade do usuário
- WHERE `mlb_id = ...`
- ORDER BY `date_created` (cronológico)

**Retorno:**
```python
[Question, Question, ...]  # lista cronológica
```

---

## Tratamento de Erros

Todas as funções implementam:

1. **Try/except granular**: falha em 1 item não bloqueia outros
2. **Logging estruturado**: `logger.error()` com `exc_info=True`
3. **Graceful degradation**: retorna resultados parciais + contagem de erros
4. **No raise**: exceto quando a sessão não pode ser criada

---

## Integração com Outros Módulos

### Dependências
- `app.auth.models.MLAccount`, `User`
- `app.core.database.AsyncSessionLocal`, `AsyncSession`
- `app.mercadolivre.client.MLClient`, `MLClientError`
- `app.perguntas.models.Question`, `QuestionAnswer`, `QASuggestionLog`
- `app.vendas.models.Listing`

### Re-exports esperados (em `__init__.py`)
```python
from app.perguntas.service import (
    sync_questions_for_account,
    sync_all_questions,
    list_questions_from_db,
    answer_question_and_track,
    get_question_stats,
    get_questions_by_listing,
)
```

---

## Uso em Celery Tasks

Para integrar em `backend/app/jobs/tasks.py`:

```python
from app.perguntas.service import sync_all_questions

@celery_app.task(name="sync_questions")
def task_sync_questions():
    """Sincroniza perguntas de todas as contas — executado daily."""
    result = asyncio.run(sync_all_questions())
    logger.info("Sync perguntas concluído: %s", result)
    return result
```

Schedule no `celery_app.conf.beat_schedule`:
```python
"sync-questions": {
    "task": "sync_questions",
    "schedule": crontab(hour=7, minute=0),  # 7h BRT
},
```

---

## Uso no Router

Para integrar em `backend/app/perguntas/router.py`:

```python
from app.perguntas.service import list_questions_from_db, get_question_stats

@router.get("/", response_model=QuestionDBListOut)
async def list_questions_route(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(None),
    ml_account_id: UUID | None = Query(None),
    offset: int = Query(0),
    limit: int = Query(20),
):
    questions, total = await list_questions_from_db(
        db=db,
        user_id=current_user.id,
        status=status,
        ml_account_id=ml_account_id,
        offset=offset,
        limit=limit,
    )
    return QuestionDBListOut(
        total=total,
        page=offset // limit + 1,
        limit=limit,
        questions=questions,
    )

@router.get("/stats", response_model=QuestionStatsOut)
async def stats(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    ml_account_id: UUID | None = Query(None),
):
    return await get_question_stats(
        db=db,
        user_id=current_user.id,
        ml_account_id=ml_account_id,
    )
```

---

## Próximas Etapas

- [ ] Expandir `router.py` com endpoints para list, answer, stats
- [ ] Integrar `sync_all_questions()` em Celery beat schedule
- [ ] Criar pipeline IA para sugestões (`service_suggestion.py`)
- [ ] Frontend: componente master-detail de perguntas
- [ ] QA: testes com dados reais da API ML

---

## Notas Técnicas

### Timezone
- Todas as datas usam `datetime.now(timezone.utc)`
- Parse de ISO: `datetime.fromisoformat(value.replace("Z", "+00:00"))`

### PostgreSQL
- Índices em `questions` (ml_account_id + status, mlb_id, date_created)
- Extração de tempo em segundos: `func.extract("epoch", field) / 3600` para horas

### Rate Limiting
- Respeitado automaticamente via `MLClient` (1 req/seg)
- Múltiplas contas sincronizadas em sequência (não paralelo)

### Estatísticas
- Urgentes: `date_created < now - 24h` (hardcoded)
- Resposta média: apenas perguntas com `answer_date` não-nulo

---

## Testing

Para testar a importação:
```bash
python -c "from app.perguntas.service import *; print('OK')"
```

Todas as funções validadas:
- ✓ `sync_questions_for_account()`
- ✓ `sync_all_questions()`
- ✓ `list_questions_from_db()`
- ✓ `answer_question_and_track()`
- ✓ `get_question_stats()`
- ✓ `get_questions_by_listing()`
