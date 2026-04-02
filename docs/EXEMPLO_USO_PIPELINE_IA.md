# Exemplo de Uso — Pipeline IA para Perguntas Q&A

## Exemplos Práticos de Classificação

### 1. Pergunta sobre Compatibilidade

```python
from app.perguntas.classifier import classify_question

texto = "Esse produto serve para iPhone 14 Pro Max? Preciso de proteção contra quedas."
tipo = classify_question(texto)
# Resultado: "compatibilidade"

# Detalhamento de matches:
# ✓ "serve" (padrão: r"\bserve\b.*\b(no|na|para)\b")
# ✓ "iPhone" (padrão: r"\bmodelo\b.*\b(do|da|meu|minha)\b")
# Score: 2 pontos
```

### 2. Pergunta sobre Material

```python
texto = "É de couro verdadeiro ou sintético?"
tipo = classify_question(texto)
# Resultado: "material"

# Matches:
# ✓ "couro" (padrão: r"\bpl[áa]stico\b|\bcouro\b")
# Score: 1 ponto
```

### 3. Pergunta sobre Envio

```python
texto = "Qual é o prazo de entrega para São Paulo? Quanto é o frete?"
tipo = classify_question(texto)
# Resultado: "envio"

# Matches:
# ✓ "prazo"
# ✓ "entrega"
# ✓ "frete"
# Score: 3 pontos
```

### 4. Pergunta Ambígua (Fallback IA)

```python
# Assume ANTHROPIC_API_KEY está configurada
from app.perguntas.classifier import classify_with_ai_fallback

texto = "Vocês entregam rápido? Meu avô quer para hoje!"
tipo_regex = classify_question(texto)
# Resultado regex: "outros" (nenhum padrão bate bem)

# Ativa fallback IA
tipo_ia = await classify_with_ai_fallback(texto)
# Claude Haiku responde: "envio" (contextualmente mais acertado)
```

---

## Exemplo Completo: Do Pergunta ao Suggestion

### Cenário
Você tem uma pergunta nova sincronizada da API ML:

```python
question = Question(
    ml_question_id=12345,
    ml_account_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
    mlb_id="MLB1234567890",
    item_title="Capinha iPhone 14 Anti-Queda Gorila Glass",
    text="Protege realmente contra queda de 2 metros?",
    status="UNANSWERED",
    buyer_nickname="comprador_teste",
)
```

### Passo 1: Classificação

```python
from app.perguntas.classifier import classify_with_ai_fallback

question_type = await classify_with_ai_fallback(question.text)
# Resultado: "compatibilidade" (match com "protege contra")
# Timing: ~5ms (regex hit imediato)
```

### Passo 2: Coleta de Contexto

```python
from app.perguntas.context_collector import collect_context
from app.mercadolivre.client import MLClient

token = "MLxxxxxxxxxxxxxxxxxxxxxx"  # da MLAccount
async with MLClient(token) as client:
    context = await collect_context(db, question, client)

# Resultado:
context = {
    "historical_qa": [
        {
            "pergunta": "Serve para iPhone 13?",
            "resposta": "Sim, serve para iPhone 13 e 14. A capa é compatível com modelos que têm o mesmo tamanho de tela.",
        },
    ],
    "item_description": "Capinha de proteção premium com vidro Gorila Glass...",
    "item_attributes": [
        "Compatibilidade: iPhone 14",
        "Material: Silicone + Vidro Temperado",
        "Tipo de Queda: Até 3 metros",
    ],
    "item_title": "Capinha iPhone 14 Anti-Queda Gorila Glass",
}
# Timing: ~500ms (parallelizado)
```

### Passo 3: Build Prompts

```python
from app.perguntas.prompts import build_prompt

system, user = build_prompt(
    question.text,
    "compatibilidade",
    context
)

# system prompt:
"""
Você é um assistente de vendas especializado no Mercado Livre Brasil.
Gere respostas profissionais, empáticas e objetivas para perguntas de compradores.
...
Instrução para este tipo (compatibilidade):
O comprador quer saber se o produto é compatível com algo específico.
Se houver informação nos atributos ou descrição, confirme ou negue claramente.
...
"""

# user prompt:
"""
Pergunta do comprador:
Protege realmente contra queda de 2 metros?

Produto: Capinha iPhone 14 Anti-Queda Gorila Glass

Atributos do produto:
Compatibilidade: iPhone 14
Material: Silicone + Vidro Temperado
Tipo de Queda: Até 3 metros

Descrição do produto (resumo):
Capinha de proteção premium com vidro Gorila Glass...

Exemplos de respostas anteriores deste anúncio:
P: Serve para iPhone 13?
R: Sim, serve para iPhone 13 e 14. A capa é compatível com modelos que têm o mesmo tamanho de tela.

Gere uma resposta adequada:
"""
```

### Passo 4: Claude Sonnet

```python
from app.perguntas.service_suggestion import _call_claude

suggestion, tokens = await _call_claude(system, user)

# Resultado:
suggestion = "Olá! Sim, protege contra quedas de até 3 metros graças ao vidro Gorila Glass e silicone reforçado. Testado para impactos severos. Qualquer dúvida estamos à disposição!"
tokens = 142
# Timing: ~2000ms (30s timeout)
```

### Passo 5: Pipeline Completo

```python
from app.perguntas.service_suggestion import generate_suggestion

result = await generate_suggestion(
    db=db,
    question=question,
    account_token=token,
    regenerate=False,  # usar cache se disponível
)

# Resultado final:
result = {
    "suggestion": "Olá! Sim, protege contra quedas de até 3 metros graças ao vidro Gorila Glass e silicone reforçado. Testado para impactos severos. Qualquer dúvida estamos à disposição!",
    "confidence": "high",  # high pois tem historical_qa + item_attributes
    "question_type": "compatibilidade",
    "cached": False,
    "latency_ms": 2641
}
```

### Passo 6: Banco de Dados

```sql
-- Question atualizada:
UPDATE questions
SET
    ai_suggestion_text = 'Olá! Sim, protege contra quedas...',
    ai_suggestion_confidence = 'high',
    ai_suggested_at = NOW()
WHERE id = '550e8400-e29b-41d4-a716-446655440001'

-- Log criado:
INSERT INTO qa_suggestion_logs (
    question_id,
    question_text,
    suggested_answer,
    question_type,
    confidence,
    tokens_used,
    latency_ms,
    created_at
) VALUES (
    '550e8400-e29b-41d4-a716-446655440001',
    'Protege realmente contra queda de 2 metros?',
    'Olá! Sim, protege contra quedas...',
    'compatibilidade',
    'high',
    142,
    2641,
    NOW()
);
```

---

## Integração no Router FastAPI

```python
# backend/app/perguntas/router.py

from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.perguntas.service_suggestion import generate_suggestion
from app.core.database import get_db

router = APIRouter(prefix="/api/v1/questions", tags=["questions"])

@router.post("/{question_id}/suggest")
async def suggest_answer(
    question_id: UUID,
    ml_account_id: UUID,
    regenerate: bool = False,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Gera sugestão IA de resposta para uma pergunta.
    
    Path params:
        - question_id: UUID da pergunta
    
    Query params:
        - ml_account_id: UUID da conta ML (filtro multi-conta)
        - regenerate: bool — ignorar cache e gerar nova
    
    Returns:
        {
            "suggestion": str,
            "confidence": "high" | "medium" | "low",
            "question_type": str,
            "cached": bool,
            "latency_ms": int
        }
    
    Status codes:
        - 200: Sugestão gerada com sucesso
        - 404: Pergunta não encontrada
        - 403: Usuário sem permissão
        - 400: Conta ML sem token
    """
    # Buscar pergunta
    question = await db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada")
    
    # Validar permissão (multi-conta)
    if question.ml_account_id != ml_account_id:
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    # Buscar token da conta ML
    ml_account = await db.get(MLAccount, ml_account_id)
    if not ml_account or not ml_account.access_token:
        raise HTTPException(
            status_code=400,
            detail="Conta ML sem token configurado"
        )
    
    # Gerar sugestão
    try:
        result = await generate_suggestion(
            db=db,
            question=question,
            account_token=ml_account.access_token,
            regenerate=regenerate,
        )
        return result
    except Exception as e:
        logger.error(f"Erro ao gerar sugestão: {e}")
        raise HTTPException(status_code=500, detail="Erro interno")
```

### Teste com cURL

```bash
# Gerar sugestão
curl -X POST "http://localhost:8000/api/v1/questions/550e8400-e29b-41d4-a716-446655440001/suggest?ml_account_id=550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"

# Resposta esperada (200 OK):
{
  "suggestion": "Olá! Sim, protege contra quedas de até 3 metros graças ao vidro Gorila Glass e silicone reforçado. Testado para impactos severos. Qualquer dúvida estamos à disposição!",
  "confidence": "high",
  "question_type": "compatibilidade",
  "cached": false,
  "latency_ms": 2641
}

# Regenerar ignorando cache
curl -X POST "http://localhost:8000/api/v1/questions/550e8400-e29b-41d4-a716-446655440001/suggest?ml_account_id=550e8400-e29b-41d4-a716-446655440000&regenerate=true" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Métricas & Monitoring

### Query SQL: Análise de Adoção

```sql
-- Qual é a taxa de adoção de sugestões por tipo?
SELECT
    question_type,
    COUNT(*) as total_generated,
    SUM(CASE WHEN was_used THEN 1 ELSE 0 END) as used_count,
    ROUND(
        100.0 * SUM(CASE WHEN was_used THEN 1 ELSE 0 END) / COUNT(*),
        2
    ) as adoption_rate_pct,
    ROUND(AVG(latency_ms), 0) as avg_latency_ms
FROM qa_suggestion_logs
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY question_type
ORDER BY adoption_rate_pct DESC;
```

### Resultado Esperado

```
 question_type  | total_generated | used_count | adoption_rate_pct | avg_latency_ms
----------------+-----------------+------------+-------------------+----------------
 compatibilidade |              145 |        129 |             88.97 |           1843
 envio          |              98  |         79 |             80.61 |           1752
 garantia       |              67  |         52 |             77.61 |           1891
 preco          |              54  |         35 |             64.81 |           1634
 material       |              42  |         28 |             66.67 |           1721
 instalacao     |              31  |         18 |             58.06 |           1805
 outros         |              8   |          3 |             37.50 |           2145
```

### Dashboard Grafana

Queries recomendadas:
1. **Taxa de Adoção por Dia**: `adoption_rate_pct` trend over time
2. **Latência Média**: `avg_latency_ms` histogram
3. **Volume de Sugestões**: `total_generated` bar chart por tipo
4. **Confiança vs Adoção**: scatter plot `confidence` vs `adoption_rate`

---

## Troubleshooting

### Problema: Sugestão sempre retorna "outros"

**Causa**: Padrões regex não batendo com perguntas em linguagem natural variada.

**Solução**:
```python
# Debug: ver o que os padrões estão matchando
from app.perguntas.classifier import classify_question, _PATTERNS

texto = "Funciona no meu carro 2020?"
for qtype, patterns in _PATTERNS.items():
    matches = []
    for pattern in patterns:
        if re.search(pattern, texto.lower()):
            matches.append(pattern)
    if matches:
        print(f"{qtype}: {matches}")
# Output: compatibilidade: [r'\bfunciona\b.*\b(no|na|com|para)\b', r'\bano\b.*\d{4}']
```

### Problema: Cache não está funcionando

**Causa**: Redis não acessível ou endereço incorreto.

**Debug**:
```bash
# Testar conexão Redis
redis-cli -u redis://localhost:6379/0 ping
# Esperado: PONG

# Ver chaves de cache
redis-cli -u redis://localhost:6379/0 keys "qa:suggestion:*"

# Limpar cache se necessário
redis-cli -u redis://localhost:6379/0 flushdb
```

### Problema: API Claude retorna erro 429 (rate limit)

**Causa**: Muitas requisições simultâneas.

**Solução**:
```python
# Aumentar timeout e adicionar retry logic
async def _call_claude(system: str, user: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            # ... chamada Claude
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                wait_time = 2 ** attempt  # backoff exponencial
                await asyncio.sleep(wait_time)
                continue
        except Exception:
            raise
```

---

## Próximos Passos Recomendados

1. **Implementar no Router** — adicionar endpoint `/questions/{id}/suggest`
2. **Task Celery** — gerar sugestões em background (2x ao dia)
3. **Frontend** — mostrar sugestão com UI de Accept/Edit/Reject
4. **Validação** — testar com 100 perguntas reais da conta ML
5. **Fine-tuning** — ajustar prompts baseado em feedback do usuário
6. **Analytics** — monitorar adoption_rate por tipo de pergunta

---

Documentação: `/docs/PIPELINE_IA_SUGESTOES.md`  
Código: `/backend/app/perguntas/`  
Modelos: `/backend/app/perguntas/models.py`
