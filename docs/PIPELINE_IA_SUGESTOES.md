# Pipeline IA para Sugestão de Respostas Q&A

## Resumo Executivo

Pipeline sofisticado de IA para sugerir respostas a perguntas de compradores no Mercado Livre. Combina:
- **Classificação por tipo** (7 categorias: compatibilidade, material, envio, preço, instalação, estoque, garantia)
- **Coleta de contexto** paralela (histórico + dados do item)
- **Cache Redis** (24h TTL)
- **Claude Sonnet 4** como modelo de IA
- **Sanitização** de dados sensíveis
- **Logging detalhado** com métricas

---

## Arquivos Criados

| Arquivo | Linhas | Responsabilidade |
|---------|--------|-----------------|
| `backend/app/perguntas/classifier.py` | 120 | Classificação de pergunta (regex + fallback Haiku) |
| `backend/app/perguntas/context_collector.py` | 110 | Coleta histórico + dados do item via API ML |
| `backend/app/perguntas/prompts.py` | 90 | Prompts de sistema e usuário por tipo |
| `backend/app/perguntas/service_suggestion.py` | 250 | Orquestração completa do pipeline |

**Total: ~570 linhas de código bem documentado**

---

## Fluxo de Dados

```
Question (modelo BD)
    ↓
[1. Classificação] → regex patterns (90% casos) + Claude Haiku fallback (10%)
    ↓ question_type: str
[2. Contexto] → paralelo:
    ├→ BD: histórico Q&A do mesmo MLB
    └→ API ML: item details + descrição + atributos
    ↓ context: dict
[3. Cache Redis] → busca por chave (mlb_id + hash_texto)
    ↓ Se hit: retorna cached
[4. Build Prompts] → system + user por tipo de pergunta
[5. Claude Sonnet] → chamada API com timeout 30s
[6. Sanitizar] → remove telefones, emails, URLs, WhatsApp
[7. Determinar Confiança] → high/medium/low baseado em contexto
[8. Salvar] → QASuggestionLog + atualizar question.ai_suggestion_*
[9. Cache] → Redis 24h

Return: {
    "suggestion": str,
    "confidence": "high" | "medium" | "low",
    "question_type": str,
    "cached": bool,
    "latency_ms": int
}
```

---

## Uso no Router

```python
# backend/app/perguntas/router.py

from app.perguntas.service_suggestion import generate_suggestion

@router.post("/questions/{question_id}/suggest")
async def suggest_answer(
    question_id: UUID,
    ml_account_id: UUID,
    regenerate: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> dict:
    """
    Gera sugestão IA de resposta para uma pergunta.
    
    Query params:
        - regenerate: bool — ignorar cache e gerar nova sugestão
    
    Returns:
        {
            "suggestion": "Olá! Sim, produto é compatível com...",
            "confidence": "high",
            "question_type": "compatibilidade",
            "cached": false,
            "latency_ms": 2341
        }
    """
    # Buscar pergunta
    question = await db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404)
    
    # Verificar permissão
    if question.ml_account_id != ml_account_id:
        raise HTTPException(status_code=403)
    
    # Buscar token da conta ML
    ml_account = await db.get(MLAccount, ml_account_id)
    if not ml_account or not ml_account.access_token:
        raise HTTPException(status_code=400, detail="Conta ML sem token")
    
    # Gerar sugestão
    result = await generate_suggestion(
        db=db,
        question=question,
        account_token=ml_account.access_token,
        regenerate=regenerate,
    )
    
    return result
```

---

## Integração em Tasks Celery

```python
# backend/app/jobs/tasks_questions.py

from celery import shared_task
from app.perguntas.service_suggestion import generate_suggestion

@shared_task(bind=True, max_retries=2)
def suggest_question_answer(self, question_id: str, ml_account_id: str):
    """
    Task que roda em background para gerar sugestão de resposta.
    Chamada após questão ser sincronizada do ML.
    
    Celery Beat: rodar a cada sincronização de perguntas (e.g., 2x ao dia)
    """
    import asyncio
    from uuid import UUID
    from sqlalchemy import select
    from app.core.database import async_session_maker
    from app.perguntas.models import Question
    from app.auth.models import MLAccount
    
    async def run():
        async with async_session_maker() as db:
            question = await db.get(Question, UUID(question_id))
            ml_account = await db.get(MLAccount, UUID(ml_account_id))
            
            if not question or not ml_account:
                return False
            
            try:
                result = await generate_suggestion(
                    db=db,
                    question=question,
                    account_token=ml_account.access_token,
                )
                return result
            except Exception as exc:
                raise self.retry(exc=exc, countdown=60)
    
    return asyncio.run(run())
```

---

## Tipos de Pergunta Suportados

| Tipo | Padrões Regex | Exemplo de Pergunta |
|------|---------------|-------------------|
| **compatibilidade** | "serve no", "compatível", "funciona" | "Serve para iPhone 14?" |
| **material** | "material", "feito de", "composição" | "É de couro verdadeiro?" |
| **envio** | "prazo", "entrega", "frete" | "Quanto custa o frete?" |
| **preco** | "desconto", "menor preço", "parcelar" | "Tem desconto à vista?" |
| **instalacao** | "instalar", "montagem", "manual" | "Precisa de montador?" |
| **estoque** | "disponível", "tem em estoque" | "Ainda tem disponível?" |
| **garantia** | "garantia", "troca", "defeito" | "Qual a garantia?" |

---

## Exemplo de Output

```json
{
    "suggestion": "Olá! Sim, o produto é 100% compatível com iPhone 14. Acompanha capinha de proteção. Qualquer dúvida estamos à disposição!",
    "confidence": "high",
    "question_type": "compatibilidade",
    "cached": false,
    "latency_ms": 2150
}
```

---

## Variáveis de Ambiente Necessárias

```env
# Anthropic API
ANTHROPIC_API_KEY=sk-ant-...

# Redis (para cache)
REDIS_URL=redis://localhost:6379/0

# ML OAuth (já existente, necessário para contexto)
ML_CLIENT_ID=...
ML_CLIENT_SECRET=...
```

---

## Logging & Métricas

Todos os logs são salvos em `qa_suggestion_logs`:

```python
QASuggestionLog(
    question_id=question.id,
    question_text=question.text,
    suggested_answer=str,  # resposta gerada
    question_type=str,     # classificação
    confidence=str,        # high/medium/low
    was_used=bool,         # preenchido later pelo usuário
    was_edited=bool,       # preenchido later pelo usuário
    tokens_used=int,       # total de tokens da API
    latency_ms=int,        # tempo de processamento
)
```

Para análise em tempo real:
```sql
SELECT
    question_type,
    confidence,
    AVG(latency_ms) as avg_latency,
    COUNT(*) as total_suggestions,
    COUNT(CASE WHEN was_used THEN 1 END)::float / COUNT(*) as adoption_rate
FROM qa_suggestion_logs
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY 1, 2
ORDER BY 3 DESC;
```

---

## Tratamento de Erros

### Classificação falha?
→ Retorna `"outros"` (genérico)

### Contexto indisponível?
→ Context collector retorna `{..., item_description: "", item_attributes: []}`
→ Sugestão ainda é gerada com base na pergunta sozinha
→ Confidence downgrade para `"low"`

### API Claude indisponível?
→ Retorna mensagem: *"Erro ao consultar IA. Tente novamente."*
→ Log no servidor para debug

### Redis indisponível?
→ Cache é skipped silenciosamente
→ Regenera sugestão toda vez (sem impacto na qualidade)

---

## Performance

| Operação | Tempo Típico | Limites |
|----------|-------------|---------|
| Classificação (regex) | ~5ms | — |
| Classificação (Haiku fallback) | ~800ms | max 10s timeout |
| Coleta de contexto | ~500ms | parallelizado |
| Claude Sonnet | ~2000ms | max 30s timeout |
| Sanitização | ~10ms | — |
| **Total (sem cache)** | **~2.5s** | — |
| **Total (com cache hit)** | **~10ms** | — |

---

## Próximos Passos (Integração)

1. **Expandir router.py** com endpoint `/questions/{id}/suggest`
2. **Criar task Celery** em `tasks_questions.py` para sugerir em background
3. **Atualizar modelo Question** se necessário (campos já existem)
4. **Frontend**: criar UI para exibir sugestão + botão Accept/Edit/Reject
5. **Validação**: testar com perguntas reais da conta ML

---

## Referências

- **Classifier patterns**: `backend/app/perguntas/classifier.py` (linhas 18-72)
- **Type prompts**: `backend/app/perguntas/prompts.py` (linhas 15-48)
- **Full service**: `backend/app/perguntas/service_suggestion.py`
- **Models**: `backend/app/perguntas/models.py` (Question, QASuggestionLog)
- **Docs ML**: https://developers.mercadolivre.com.br/pt_br/recurso-questions

---

## Notas Importantes

⚠️ **Sanitização de Dados**
- Telefones, emails, URLs e menções WhatsApp são removidas
- Resposta limitada a 2000 caracteres
- Nunca exponha endpoints, senhas ou chaves de API

⚠️ **Cache Strategy**
- TTL de 24h baseado em `mlb_id + hash_texto_pergunta`
- Invalidar manualmente com `regenerate=True` se precisar
- Redis é crítico para performance em produção

⚠️ **Custo de API**
- Claude Sonnet: ~$3 por 1M input tokens
- Estimado: 300-500 tokens por sugestão
- Custo por sugestão: ~$0.001-0.002
- Com cache: redução de 70-80% em chamadas

---

Documentação completa em: `/docs/PIPELINE_IA_SUGESTOES.md`
