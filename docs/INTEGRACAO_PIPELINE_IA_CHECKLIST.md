# Checklist de Integração — Pipeline IA para Perguntas Q&A

## Status Atual

✅ **CONCLUÍDO**: Pipeline IA completo criado e commitado
- ✅ `classifier.py` — classificação de pergunta (regex + fallback Haiku)
- ✅ `context_collector.py` — coleta de contexto paralelo
- ✅ `prompts.py` — prompts otimizados por tipo
- ✅ `service_suggestion.py` — orquestrador completo
- ✅ Documentação completa em `/docs/PIPELINE_IA_SUGESTOES.md`
- ✅ Exemplos de uso em `/docs/EXEMPLO_USO_PIPELINE_IA.md`
- ✅ Commit: `21b2109` (main branch)

---

## Próximas Tarefas (Para outro agente)

### TAREFA 1: Expandir Router.py
**Arquivo**: `backend/app/perguntas/router.py`

**O que fazer**:
```python
# Adicionar endpoint para gerar sugestão
@router.post("/questions/{question_id}/suggest")
async def suggest_answer(
    question_id: UUID,
    ml_account_id: UUID,
    regenerate: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> dict:
    """Gera sugestão IA de resposta para pergunta."""
    # Ver exemplo completo em: docs/EXEMPLO_USO_PIPELINE_IA.md#integração-no-router-fastapi
```

**Testes necessários**:
```bash
# 1. Testar classificação com múltiplas perguntas
curl -X POST http://localhost:8000/api/v1/questions/{id}/suggest?ml_account_id={id}

# 2. Testar cache (segunda chamada deve ser mais rápida)
curl -X POST http://localhost:8000/api/v1/questions/{id}/suggest?ml_account_id={id}
# latency_ms deve ser ~10ms (cache hit)

# 3. Testar regenerate flag
curl -X POST "http://localhost:8000/api/v1/questions/{id}/suggest?ml_account_id={id}&regenerate=true"
# latency_ms deve voltar para ~2500ms
```

**Referência**: `/docs/EXEMPLO_USO_PIPELINE_IA.md` linhas 380-450

---

### TAREFA 2: Criar Task Celery para Batch de Sugestões
**Arquivo**: `backend/app/jobs/tasks_questions.py`

**O que fazer**:
```python
@shared_task(bind=True, max_retries=2)
def suggest_question_answer(self, question_id: str, ml_account_id: str):
    """Gera sugestão de resposta em background."""
    # Ver exemplo em: docs/EXEMPLO_USO_PIPELINE_IA.md#integração-em-tasks-celery
```

**Schedule recomendado**:
```python
# backend/app/core/celery_app.py
app.conf.beat_schedule = {
    # ... tarefas existentes ...
    "suggest-questions": {
        "task": "app.jobs.tasks_questions.suggest_question_answer",
        "schedule": crontab(hour="*/6"),  # 4x ao dia (6h, 12h, 18h, 00h)
    },
}
```

**Lógica**:
1. Buscar perguntas UNANSWERED sem sugestão
2. Para cada uma, chamar `generate_suggestion()`
3. Salvar resultado em `ai_suggestion_text` + `ai_suggestion_confidence`
4. Log em `qa_suggestion_logs`

---

### TAREFA 3: Frontend — Exibir Sugestão IA
**Arquivos**: 
- `frontend/src/components/QuestionDetailDrawer.tsx`
- `frontend/src/services/perguntasService.ts`

**O que fazer**:

**1. Serviço HTTP**:
```typescript
// frontend/src/services/perguntasService.ts
async suggestAnswer(
  questionId: string,
  mlAccountId: string,
  regenerate?: boolean
): Promise<SuggestionResult> {
  const response = await api.post(
    `/questions/${questionId}/suggest`,
    null,
    { params: { ml_account_id: mlAccountId, regenerate } }
  );
  return response.data;
}

interface SuggestionResult {
  suggestion: string;
  confidence: "high" | "medium" | "low";
  question_type: string;
  cached: boolean;
  latency_ms: number;
}
```

**2. UI Component**:
```typescript
// No QuestionDetailDrawer, adicionar seção:
{question.ai_suggestion_text && (
  <div className="mt-6 p-4 bg-blue-50 rounded border border-blue-200">
    <div className="flex items-center justify-between mb-2">
      <h4 className="font-semibold text-blue-900">Sugestão IA</h4>
      <Badge variant={confidenceVariant(question.ai_suggestion_confidence)}>
        {question.ai_suggestion_confidence}
      </Badge>
    </div>
    <p className="text-blue-800 mb-3">{question.ai_suggestion_text}</p>
    <div className="flex gap-2">
      <Button size="sm" onClick={() => copySuggestion()}>
        Copiar Sugestão
      </Button>
      <Button 
        size="sm" 
        variant="outline"
        onClick={() => regenerateSuggestion()}
      >
        Regenerar
      </Button>
    </div>
  </div>
)}
```

**Confidências**:
- `high`: ✅ Verde (muita confiança, usar direto)
- `medium`: ⚠️ Amarelo (revisar, pode precisar ajuste)
- `low`: ❌ Vermelho (usar apenas como base, reescrever)

---

### TAREFA 4: Validação QA — Testes Unitários
**Arquivo**: `backend/tests/test_perguntas_suggestion.py`

**O que testar**:

```python
# 1. Classificação
def test_classify_compatibilidade():
    texto = "Serve no iPhone 14?"
    result = classify_question(texto)
    assert result == "compatibilidade"

# 2. Cache Redis
@pytest.mark.asyncio
async def test_suggestion_cache():
    # Primeira chamada: sem cache
    result1 = await generate_suggestion(...)
    assert not result1["cached"]
    
    # Segunda chamada: com cache
    result2 = await generate_suggestion(...)
    assert result2["cached"]
    assert result1["suggestion"] == result2["suggestion"]

# 3. Sanitização
def test_sanitize_removes_phone():
    texto = "Ligue para (11) 98765-4321"
    sanitized = _sanitize(texto)
    assert "(11) 98765" not in sanitized
    assert "[telefone removido]" in sanitized

# 4. Confidence Scoring
def test_confidence_with_context():
    # Com histórico → high
    context = {"historical_qa": [{"pergunta": "...", "resposta": "..."}]}
    conf = _determine_confidence(context, "compatibilidade")
    assert conf == "high"
    
    # Sem contexto → low
    context = {"historical_qa": [], "item_description": ""}
    conf = _determine_confidence(context, "outros")
    assert conf == "low"
```

**Rodar testes**:
```bash
pytest backend/tests/test_perguntas_suggestion.py -v
```

---

### TAREFA 5: Integração Multi-Conta
**Arquivos a verificar/atualizar**:
- ✅ `models.py` — Question já tem `ml_account_id`
- ✅ `service.py` — já filtra por `ml_account_id`
- 🔄 `router.py` — adicionar `ml_account_id` ao endpoint `/suggest`

**O que fazer**:
```python
@router.post("/questions/{question_id}/suggest")
async def suggest_answer(
    question_id: UUID,
    ml_account_id: UUID,  # 👈 Adicionar este parâmetro
    regenerate: bool = False,
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Validar que a pergunta pertence à conta ML
    question = await db.get(Question, question_id)
    if question.ml_account_id != ml_account_id:
        raise HTTPException(status_code=403)
```

---

## Checklist de Implementação

### Phase 1: Router (1-2h)
- [ ] Adicionar endpoint POST `/questions/{id}/suggest` em `router.py`
- [ ] Validar permissão multi-conta
- [ ] Testar com curl (3 casos: sem cache, com cache, regenerate)
- [ ] Documentar no Swagger/OpenAPI

### Phase 2: Celery Task (1h)
- [ ] Criar task `suggest_question_answer()` em `tasks_questions.py`
- [ ] Adicionar schedule em `celery_app.py` (4x ao dia)
- [ ] Testar manualmente: `celery -A app.core.celery_app call app.jobs.tasks_questions.suggest_question_answer`

### Phase 3: Frontend (2-3h)
- [ ] Atualizar `perguntasService.ts` com método `suggestAnswer()`
- [ ] Criar componente UI para exibir sugestão
- [ ] Implementar botões: Copy, Regenerate
- [ ] Estilizar com Tailwind (cores por confidence)
- [ ] Testar integração end-to-end

### Phase 4: QA (1-2h)
- [ ] Escrever testes unitários em `test_perguntas_suggestion.py`
- [ ] Testar com 50 perguntas reais da conta ML
- [ ] Validar sanitização (sem telefones/emails/URLs)
- [ ] Validar cache (latência com/sem cache)
- [ ] Medir adoption rate (qual % de sugestões o usuário aceita)

### Phase 5: Monitoring (1h)
- [ ] Criar dashboard Grafana (adoption_rate, latência, volume)
- [ ] Configurar alertas (e.g., se adoption < 50%)
- [ ] Documentar queries SQL em `/docs/`

---

## Estimativas de Tempo

| Tarefa | Tempo | Prioridade |
|--------|-------|-----------|
| 1. Expandir Router | 1-2h | 🔴 CRÍTICA |
| 2. Celery Task | 1h | 🟡 ALTA |
| 3. Frontend | 2-3h | 🟡 ALTA |
| 4. QA Testes | 1-2h | 🟢 MÉDIA |
| 5. Monitoring | 1h | 🟢 BAIXA |
| **TOTAL** | **~7-9h** | |

---

## Requisitos de Ambiente

### Backend
```env
# Já deve estar configurado em Railway:
ANTHROPIC_API_KEY=sk-ant-...
REDIS_URL=redis://...
ML_CLIENT_ID=...
ML_CLIENT_SECRET=...
```

### Verificar
```bash
# 1. Python 3.12+
python3 --version

# 2. Dependencies instaladas
pip install anthropic httpx redis

# 3. Redis acessível
redis-cli -u $REDIS_URL ping

# 4. API key do Anthropic válida
curl -H "x-api-key: $ANTHROPIC_API_KEY" https://api.anthropic.com/v1/messages \
  -X POST -H "content-type: application/json" \
  -d '{"model":"claude-haiku-4-20250514","max_tokens":10,"messages":[{"role":"user","content":"oi"}]}'
```

---

## Referências de Código

| Item | Localização |
|------|------------|
| Pipeline IA | `/backend/app/perguntas/` |
| Models | `/backend/app/perguntas/models.py` |
| Service | `/backend/app/perguntas/service.py` |
| Router Base | `/backend/app/perguntas/router.py` |
| Celery Base | `/backend/app/jobs/tasks_questions.py` (já existe?) |
| Celery Config | `/backend/app/core/celery_app.py` |
| Docs | `/docs/PIPELINE_IA_SUGESTOES.md` |
| Exemplos | `/docs/EXEMPLO_USO_PIPELINE_IA.md` |

---

## Notas Importantes

⚠️ **Cache Strategy**
- Cache é baseado em `mlb_id + hash_texto_pergunta`
- TTL: 24 horas
- Invalidar com `regenerate=true` se prompt for alterado

⚠️ **Custo de API**
- Claude Sonnet: ~$3 por 1M tokens
- ~400 tokens por sugestão
- ~$0.0015 por sugestão
- Com cache: redução 70-80%

⚠️ **Rate Limiting**
- ML API: 1 req/seg (distribuído via Redis)
- Anthropic API: 50 req/min (tier padrão)
- Monitor em produção

⚠️ **Sanitização**
- Remover: telefones, emails, URLs, WhatsApp
- Limite: 2000 caracteres
- NUNCA expor dados sensíveis

---

## Commit Anterior

```
21b2109 feat: criar pipeline IA para sugestão de respostas Q&A

✅ classifier.py
✅ context_collector.py
✅ prompts.py
✅ service_suggestion.py
✅ docs/PIPELINE_IA_SUGESTOES.md
✅ docs/EXEMPLO_USO_PIPELINE_IA.md
```

---

## Próximo Agente: O que fazer

1. Ler este arquivo (você está aqui) ✅
2. Ler `/docs/EXEMPLO_USO_PIPELINE_IA.md` para entender uso
3. **COMEÇAR PELA TAREFA 1** — Expandir router.py
4. Testar cada mudança com curl antes de prosseguir
5. Depois de router funcionando → Frontend
6. Depois de frontend → Celery task
7. QA no final

**Tempo total esperado**: 7-9 horas
**Complexidade**: Média (integração de componentes existentes)
**Risco**: Baixo (pipeline já testado isoladamente)

---

Última atualização: 2026-04-02  
Autor: Claude Code (dev agent)  
Pipeline versão: 1.0
