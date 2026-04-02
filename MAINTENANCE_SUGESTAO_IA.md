# Manutenção — Sistema de Sugestão IA no Módulo Perguntas

## Visão Geral da Arquitetura

```
Frontend (React)
    ↓
POST /api/v1/perguntas/{id}/suggest
    ↓
Backend (FastAPI)
    ├─ Validação de autenticação
    ├─ Carregamento da pergunta
    ├─ generate_suggestion()
    │   ├─ Classificação de tipo (classify_with_ai_fallback)
    │   ├─ Verificação de cache Redis
    │   ├─ Coleta de contexto (context_collector)
    │   │   ├─ Q&A histórico (banco local)
    │   │   └─ Info do item (API ML)
    │   ├─ Chamada Claude API (httpx)
    │   ├─ Sanitização
    │   └─ Salvar log + cache
    └─ Retorno da sugestão
    ↓
Frontend (TanStack Query)
    ├─ Sucesso: exibir sugestão
    └─ Erro: exibir mensagem detalhada
```

## Arquivos Principais

### Backend

| Arquivo | Responsabilidade | Crítico |
|---------|-----------------|---------|
| `app/perguntas/router.py` | Endpoint `/suggest`, validação de auth | ⚠️ |
| `app/perguntas/service_suggestion.py` | Pipeline completo de geração | ⚠️⚠️⚠️ |
| `app/perguntas/context_collector.py` | Enriquecimento de contexto | ⚠️ |
| `app/perguntas/classifier.py` | Classificação de tipo de pergunta | ⚠️ |
| `app/perguntas/prompts.py` | Construção de prompts para Claude | ⚠️ |
| `app/perguntas/models.py` | Tabelas: Question, QASuggestionLog | ⚠️ |
| `app/core/config.py` | Config: ANTHROPIC_API_KEY | ⚠️⚠️ |
| `app/mercadolivre/client.py` | Cliente HTTP para ML API | ⚠️ |

### Frontend

| Arquivo | Responsabilidade | Crítico |
|---------|-----------------|---------|
| `pages/Perguntas/index.tsx` | UI: lista + detalhe de pergunta | ⚠️ |
| `services/perguntasService.ts` | API client: getSuggestion() | ⚠️ |

### Config

| Arquivo | Responsabilidade |
|---------|-----------------|
| `.env.example` | Documentação de ANTHROPIC_API_KEY |
| `railway.json` (backend) | Deploy config |
| `.github/workflows/` | CI/CD (se houver) |

---

## Pontos de Manutenção Críticos

### 1. ANTHROPIC_API_KEY — Configuração

**Localização:**
- Código: `backend/app/core/config.py:57`
- Env var: `ANTHROPIC_API_KEY`
- Docs: `.env.example:45`
- Railway: Projeto → MSM_Pro → Variables

**Validação:**
```bash
# Verificar se está configurada em produção
curl -X POST https://msmpro-production.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"maikeo@msmrp.com","password":"Msm@2026"}' \
  -c cookies.txt

# Se GET de pergunta retornar "ANTHROPIC_API_KEY não configurada",
# é porque a variável está vazia no Railway
```

**Ação se não estiver configurada:**
1. Ir para Railway: https://railway.app → vibrant-exploration → MSM_Pro
2. Aba "Variables"
3. Adicionar: `ANTHROPIC_API_KEY = sk-...` (da Anthropic Console)
4. Redeploy automático ou manual

**Validar API key:**
```python
# Teste local
from anthropic import Anthropic
client = Anthropic(api_key="sk-...")
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=100,
    messages=[{"role": "user", "content": "teste"}]
)
print(response.content[0].text)
```

---

### 2. Tratamento de Erros — Fluxo Crítico

**Arquivo:** `backend/app/perguntas/service_suggestion.py`

**Erros tratados:**
1. `settings.anthropic_api_key` vazio (linha 92)
2. `httpx.HTTPStatusError` (linha 103)
   - 401: chave inválida
   - 429: rate limit
   - outros: genérico
3. `httpx.ConnectError` (linha 124)
4. `httpx.TimeoutException` (linha 130)
5. `Exception` genérica (linha 136)

**Se adicionar novo tipo de erro:**
```python
# 1. Adicionar novo except após _call_claude():
except SeuErroCustom as e:
    logger.error("Seu erro: %s", e)
    return {
        "suggestion": "Sua mensagem útil aqui",
        "confidence": "low",
        "question_type": question_type,
        "cached": False,
        "latency_ms": int(time.time() * 1000) - start_ms,
    }

# 2. Manter estrutura de retorno (sempre dict com as 5 chaves)
# 3. Logar erro com contexto
# 4. Retornar mensagem amigável ao usuário
```

---

### 3. Cache Redis

**Localização:** `backend/app/perguntas/service_suggestion.py:247-284`

**Como funciona:**
```python
cache_key = f"qa:suggestion:{mlb_id}:{text_hash}"
# Exemplo: qa:suggestion:MLB6205732214:a1b2c3d4e5f6

# TTL: 86400 segundos (24 horas)
# Redis key expires automaticamente
```

**Limpar cache se necessário:**
```bash
# SSH Railway
railway run --service MSM_Pro -- redis-cli

# Dentro do redis-cli:
FLUSHDB
# OU
DEL qa:suggestion:MLB6205732214:*
```

**Desabilitar cache (temporário):**
```python
# Em service_suggestion.py, linha 65:
# if not regenerate:  # comentar esta linha
#     cached = await _get_from_cache(cache_key)  # comentar
#     if cached:
```

---

### 4. Modelo de Dados — Persistência

**Tabelas relevantes:**
1. `questions` — pergunta do comprador
2. `qa_suggestion_logs` — histórico de sugestões

**Campos críticos:**
```python
# Question model
ai_suggestion_text: str | None         # A sugestão gerada
ai_suggestion_confidence: str | None   # high | medium | low
ai_suggested_at: datetime | None       # Quando foi gerada

# QASuggestionLog model
question_id: UUID
suggested_answer: str
confidence: str
tokens_used: int
latency_ms: int
```

**Se precisar alterar schema:**
1. Modificar `app/perguntas/models.py`
2. Criar migration Alembic: `alembic revision --autogenerate -m "descricao"`
3. Verificar migration gerada
4. Testar localmente: `alembic upgrade head`
5. Commitar migration + models.py

---

### 5. Frontend — Tratamento de Erros

**Localização:** `frontend/src/pages/Perguntas/index.tsx:395-427`

**Fluxo atual:**
```tsx
1. Clique no botão
   └─ suggestMutation.mutate()
   
2. Durante: isPending = true
   └─ Botão desabilitado, mostrar "Gerando..."
   
3. Se sucesso: exibir sugestão em card violeta
   └─ Botões: "Usar resposta", "Regenerar"
   
4. Se erro: exibir mensagem abaixo do botão
   └─ Texto vermelho, borda, fundo rosa
   └─ Mensagem vem de response.data.detail ou error.message
```

**Se backend retorna novo erro:**
```tsx
// 1. Verificar que error.response existe:
(suggestMutation.error as any)?.response?.data?.detail

// 2. Se não existir, usar fallback:
?? (suggestMutation.error as any)?.message
?? "Erro ao consultar IA. Tente novamente."

// 3. Testar com React DevTools (react-query tab)
```

---

### 6. API Anthropic — Rate Limiting

**Limites atuais:**
- 1M tokens/minuto por chave
- ~2000 requisições/minuto (com max_tokens=500)

**Se exceder limite:**
```python
# Backend retorna HTTP 429
except httpx.HTTPStatusError as e:
    if e.response.status_code == 429:
        error_msg += "Limite de requisições excedido. Tente em alguns minutos."
```

**Mitigação:**
1. Frontend: máx 3 tentativas por minuto (implementar em useMutation)
2. Backend: rate limiting por usuário (slowapi)
3. Cache: reutilizar sugestões até 24h

**Implementar rate limit no frontend:**
```tsx
const [lastSuggestTime, setLastSuggestTime] = useState(0);
const handleGenerateSuggestion = () => {
  const now = Date.now();
  if (now - lastSuggestTime < 10000) { // 10s entre tentativas
    alert("Aguarde alguns segundos antes de tentar novamente");
    return;
  }
  setLastSuggestTime(now);
  suggestMutation.mutate(false);
};
```

---

### 7. Logging — Monitoramento

**Locais onde logs são gerados:**
```python
# service_suggestion.py

logger.error("Claude API HTTP error: status=%s body=%s", ...)
logger.error("Erro de conexão com Claude API: %s", ...)
logger.error("Timeout ao chamar Claude API")
logger.error("Erro inesperado ao gerar sugestão IA: %s", ...)
logger.warning("Falha ao coletar contexto: %s", exc)
logger.warning("Context collection failed, proceeding without context: %s", exc)
```

**Buscar logs no Railway:**
```bash
railway logs --service MSM_Pro --follow

# Ou em tempo real:
railway logs --service MSM_Pro --tail 50
```

**Padrão de busca:**
```bash
# Claude API errors
railway logs --service MSM_Pro | grep -i "Claude API"

# Todos os erros de sugestão
railway logs --service MSM_Pro | grep -i "sugestao"

# Context collection failures
railway logs --service MSM_Pro | grep -i "context"
```

---

### 8. Testes — Cobertura

**Testes recomendados (em `backend/tests/`):**

```python
# test_perguntas_suggestion.py

async def test_suggestion_without_api_key():
    # settings.anthropic_api_key = ""
    # Expect: "IA não configurada..."
    
async def test_suggestion_with_invalid_key():
    # mock httpx.HTTPStatusError(status=401)
    # Expect: "ANTHROPIC_API_KEY inválida"
    
async def test_suggestion_rate_limit():
    # mock httpx.HTTPStatusError(status=429)
    # Expect: "Limite de requisições..."
    
async def test_suggestion_timeout():
    # mock httpx.TimeoutException()
    # Expect: "timeout..."
    
async def test_suggestion_caching():
    # 1ª chamada: gera (cached=false)
    # 2ª chamada: retorna cache (cached=true, latency < 50ms)
    
async def test_suggestion_with_context():
    # Mock context_collector com histórico
    # Expect: confidence="high" ou "medium"
    
async def test_suggestion_without_context():
    # Mock context_collector sem histórico
    # Expect: confidence="low"
```

**Rodar testes:**
```bash
cd backend
pytest tests/test_perguntas_suggestion.py -v
pytest tests/test_perguntas_suggestion.py::test_suggestion_without_api_key -v
```

---

## Checklist de Deploy

Antes de fazer deploy de qualquer mudança:

- [ ] Código compilado/sem erros de sintaxe?
- [ ] Todos os logs úteis têm contexto (não genéricos)?
- [ ] ANTHROPIC_API_KEY está configurada no Railway?
- [ ] Migrations foram aplicadas (se houver)?
- [ ] Frontend carrega sem erros TypeScript?
- [ ] Testado localmente (curl + frontend)?
- [ ] Commit com mensagem clara?
- [ ] Push para main (auto-deploy Railway)?
- [ ] Verificar /health endpoint?
- [ ] Monitorar logs por 5min após deploy?

---

## Contatos e Referências

**Documentação:**
- Anthropic API: https://docs.anthropic.com/
- Claude Models: https://docs.anthropic.com/claude/reference/getting-started-with-the-api
- Rate Limits: https://docs.anthropic.com/claude/reference/errors-and-rate-limits

**Ferramentas:**
- Railway CLI: `railway` command
- PostgreSQL: Railway managed DB
- Redis: Railway managed Cache
- Logs: Railway web dashboard

**Contato para suporte:**
- Anthropic: https://console.anthropic.com/
- Railway: https://railway.app/

---

## Histórico de Mudanças

| Data | Mudança | Commit |
|------|---------|--------|
| 2026-04-02 | Melhorar mensagens de erro | 78a1e6f |
| - | - | - |

---

## Notas Futuras

1. **Implementar retry automático com backoff** — para erros temporários (429, timeout)
2. **Adicionar telemetria** — latência média, taxa de erro, uso de tokens
3. **Batch processing** — gerar sugestões para múltiplas perguntas em paralelo
4. **A/B testing** — comparar diferentes modelos (Haiku vs Sonnet vs Opus)
5. **Custom training** — fine-tuning do modelo com histórico real de Q&A
6. **Multi-language** — suportar português, inglês, espanhol
