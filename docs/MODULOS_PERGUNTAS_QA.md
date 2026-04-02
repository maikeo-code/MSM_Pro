# Módulo Perguntas Q&A — Modelos e Schemas

## Status
✅ **CONCLUÍDO** — Commit: `4a37661`

---

## Arquivos Criados

### 1. `/backend/app/perguntas/models.py` (200 linhas)

Três tabelas SQLAlchemy 2.0 async relacionadas:

#### Tabela: `questions`
- **Propósito:** Persistência completa de perguntas recebidas do Mercado Livre
- **Colunas principais:**
  - `ml_question_id` (INTEGER UNIQUE) — ID da pergunta no ML
  - `ml_account_id` (FK, CASCADE) — Conta ML que recebeu a pergunta
  - `mlb_id` (VARCHAR 50) — ID do anúncio no ML
  - `text` (TEXT) — Texto da pergunta
  - `status` (VARCHAR 30) — UNANSWERED | ANSWERED | CLOSED_UNANSWERED | UNDER_REVIEW
  - `answer_text` (TEXT) — Resposta enviada
  - `answer_source` (VARCHAR 20) — manual | ai | template | ml_direct
  - `ai_suggestion_text` (TEXT) — Sugestão gerada pela IA
  - `ai_suggestion_confidence` (VARCHAR 10) — high | medium | low

- **Indexes:**
  - `(ml_account_id, status)` — filtro por conta e status
  - `(mlb_id)` — lookup por anúncio
  - `(date_created)` — ordenação temporal

- **Relacionamentos:**
  - 1 → N com `QuestionAnswers` (cascade delete)
  - FK `MLAccount` (cascade delete)
  - FK `Listing` (set null, opcional)

#### Tabela: `question_answers`
- **Propósito:** Histórico de respostas e metadados de envio
- **Colunas:**
  - `question_id` (FK, CASCADE)
  - `text` (TEXT) — Texto da resposta
  - `status` (VARCHAR 20) — pending | sent | failed
  - `source` (VARCHAR 20) — manual | ai | template
  - `template_id` (FK, SET NULL) — Link para template reutilizado
  - `sent_at` (TIMESTAMP) — Quando foi enviada
  - `error_message` (TEXT) — Se falhou

#### Tabela: `qa_suggestion_logs`
- **Propósito:** Auditoria de sugestões IA e métricas
- **Colunas:**
  - `question_id` (FK, CASCADE, NULLABLE) — Pode existir independentemente
  - `question_text` (TEXT) — Pergunta original
  - `suggested_answer` (TEXT) — Resposta sugerida
  - `confidence` (VARCHAR 10) — high | medium | low
  - `was_used` (BOOLEAN) — Se o usuário usou
  - `was_edited` (BOOLEAN) — Se editou antes de usar
  - `tokens_used` (INTEGER) — Tokens consumidos pela API Claude
  - `latency_ms` (INTEGER) — Tempo de resposta da IA

---

### 2. `/backend/migrations/versions/0026_create_questions.py` (170 linhas)

Migration Alembic completa:
- **revision:** `"0026_create_questions"`
- **down_revision:** `"0025_create_user_notifications"`
- Cria tabelas em ordem: questions → question_answers → qa_suggestion_logs
- Cria todos os indexes
- `downgrade()` reverso completo

**Como aplicar:**
```bash
cd backend
alembic upgrade head
```

---

### 3. `/backend/app/perguntas/schemas.py` (ATUALIZADO)

**Mantém schemas antigos** (backward compat):
- `AnswerQuestionIn` — Body para responder pergunta
- `QuestionOut` — Pass-through da API ML
- `QuestionListOut` — Paginação simples
- `AnswerQuestionOut` — Resposta ao responder

**Adiciona schemas novos:**
- `QuestionDB` — Representação completa do banco
- `QuestionDBListOut` — Paginação com page, limit, total
- `QuestionStatsOut` — KPIs: total, unanswered, answered, urgent, by_account
- `AISuggestionRequest` — `{regenerate: bool}`
- `AISuggestionResponse` — `{suggestion, confidence, question_type, cached, latency_ms}`
- `SyncQuestionsOut` — `{synced, new, updated, errors}`
- `AnswerFromSuggestionIn` — Resposta editável com sugestão IA

---

### 4. `/backend/app/main.py`

Adicionada importação de modelos:
```python
import app.perguntas.models  # noqa: F401
```

---

## Padrões Seguidos

✅ **SQLAlchemy 2.0 async com Mapped[]**
✅ **DateTime(timezone=True) com UTC**
✅ **ForeignKey com ondelete CASCADE/SET NULL**
✅ **UUID com PG_UUID(as_uuid=True)**
✅ **Relationships com back_populates**
✅ **Indexes compostos em __table_args__**
✅ **Schemas com ConfigDict(from_attributes=True)**
✅ **Comentários em colunas críticas**

---

## Exemplo de Uso

```python
from app.perguntas.models import Question, QuestionAnswer, QASuggestionLog
from datetime import datetime, timezone

# 1. Criar pergunta
question = Question(
    ml_question_id=123456,
    ml_account_id=account_uuid,
    mlb_id="MLB1234567890",
    text="Qual é a composição?",
    status="UNANSWERED",
    date_created=datetime.now(timezone.utc)
)
db.add(question)
await db.commit()

# 2. Adicionar sugestão IA
question.ai_suggestion_text = "100% algodão."
question.ai_suggestion_confidence = "high"
question.ai_suggested_at = datetime.now(timezone.utc)

# 3. Log de auditoria
log = QASuggestionLog(
    question_id=question.id,
    question_text=question.text,
    suggested_answer=question.ai_suggestion_text,
    confidence="high",
    tokens_used=142,
    latency_ms=2340
)
db.add(log)
await db.commit()

# 4. Registrar resposta
answer = QuestionAnswer(
    question_id=question.id,
    text="100% algodão.",
    source="ai",
    status="pending"
)
db.add(answer)
await db.commit()
```

---

## Validação

✅ AST validation passed (models.py, schemas.py, migration)
✅ Python compile check: OK
✅ Imports corretos (padrões do projeto)
✅ Backward compat: schemas antigos mantidos
✅ Git commit: `4a37661`

---

## Próximas Tarefas

**Task #2:** `service.py` com métodos:
- `sync_from_ml()` — sincronizar perguntas da API ML
- `list_by_status()` — listar com paginação
- `get_stats()` — calcular KPIs
- `answer_question()` — responder via ML API

**Task #3:** Pipeline IA (classifier, context, prompts)

**Task #4:** Expandir router.py + tasks Celery

**Task #5:** Frontend React (master-detail + IA)

---

## Links

- **Models:** `/backend/app/perguntas/models.py`
- **Migration:** `/backend/migrations/versions/0026_create_questions.py`
- **Schemas:** `/backend/app/perguntas/schemas.py`
- **Commit:** `4a37661`
- **Branch:** `main` (production)
