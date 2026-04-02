# Fix: Sugestão IA no Módulo Perguntas — Sumário de Correções

## Problema Identificado
Quando o usuário clica "Sugestão IA" na página de Perguntas, recebe mensagem genérica "Erro ao consultar IA. Tente novamente." sem detalhes do erro real.

## Causa Raiz
1. **Backend**: Tratamento de erros genérico demais — não diferencia entre:
   - ANTHROPIC_API_KEY não configurada
   - API key inválida (HTTP 401)
   - Limite de requisições excedido (HTTP 429)
   - Erros de conexão
   - Timeouts
   - Erros inesperados

2. **Frontend**: Exibe apenas mensagem de erro genérica, sem detalhes do servidor

## Correções Implementadas

### 1. Backend — `service_suggestion.py` (44 linhas adicionadas)

**Antes:**
```python
except Exception as exc:
    logger.error("Erro ao gerar sugestão IA: %s", exc)
    return {
        "suggestion": "Erro ao consultar IA. Tente novamente.",
        ...
    }
```

**Depois:**
```python
if not settings.anthropic_api_key:
    return {
        "suggestion": "Sugestão IA indisponível: ANTHROPIC_API_KEY não configurada no servidor. Configure a variável de ambiente no Railway.",
        ...
    }

try:
    suggestion_text, tokens_used = await _call_claude(system_prompt, user_prompt)
except httpx.HTTPStatusError as e:
    logger.error("Claude API HTTP error: status=%s body=%s", e.response.status_code, e.response.text[:200])
    error_msg = f"Erro na API Claude (HTTP {e.response.status_code}). "
    if e.response.status_code == 401:
        error_msg += "ANTHROPIC_API_KEY inválida."
    elif e.response.status_code == 429:
        error_msg += "Limite de requisições excedido. Tente em alguns minutos."
    else:
        error_msg += "Tente novamente."
    return { "suggestion": error_msg, ... }
    
except httpx.ConnectError as e:
    logger.error("Erro de conexão com Claude API: %s", e)
    return { "suggestion": "Erro de conexão com a API Claude. Verifique sua conexão de internet e tente novamente.", ... }
    
except httpx.TimeoutException:
    logger.error("Timeout ao chamar Claude API")
    return { "suggestion": "Timeout ao chamar a API Claude. A requisição demorou muito tempo. Tente novamente.", ... }
    
except Exception as exc:
    logger.error("Erro inesperado ao gerar sugestão IA: %s", exc, exc_info=True)
    return { "suggestion": f"Erro inesperado ao gerar sugestão: {str(exc)[:100]}...", ... }
```

**Benefícios:**
- Mensagens específicas para cada tipo de erro
- Contexto útil para diagnóstico
- Ajuda o usuário a resolver o problema

### 2. Frontend — `Perguntas/index.tsx` (17 linhas adicionadas)

**Antes:**
```tsx
{tab === "pendentes" && !question.ai_suggestion_text && !question.answer_text && (
  <button
    onClick={handleGenerateSuggestion}
    disabled={suggestMutation.isPending}
    className={...}
  >
    ...
  </button>
)}
```

**Depois:**
```tsx
{tab === "pendentes" && !question.ai_suggestion_text && !question.answer_text && (
  <div className="space-y-2">
    <button ... >...</button>
    {suggestMutation.isError && (
      <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
        {(suggestMutation.error as any)?.response?.data?.detail ||
          (suggestMutation.error as any)?.message ||
          "Erro ao consultar IA. Tente novamente."}
      </div>
    )}
  </div>
)}
```

**Benefícios:**
- Mensagem de erro visível logo abaixo do botão
- Prioridade: mensagem detalhada do servidor > erro genérico
- Estilo visual claro (fundo vermelho, borda, padding)

### 3. Config — `config.py`

**Verificado:**
- ✅ Campo `anthropic_api_key: str = ""` já existe na linha 57
- ✅ Lê variável de ambiente `ANTHROPIC_API_KEY` automaticamente (Pydantic)
- ✅ `.env.example` já documenta a variável na linha 45

Nenhuma alteração necessária.

## Arquivos Modificados

| Arquivo | Linhas | Mudança |
|---------|--------|---------|
| `backend/app/perguntas/service_suggestion.py` | +44 | Tratamento detalhado de erros |
| `frontend/src/pages/Perguntas/index.tsx` | +17 | Exibição de mensagem de erro |
| **Total** | **+61** | **2 arquivos** |

## Commit

```bash
commit 78a1e6f
Author: maikeo-code <maikeo@msmrp.com>
Date:   [timestamp]

    fix: melhorar mensagens de erro da sugestão IA no módulo Perguntas
    
    - Backend: tratamento específico por tipo de erro (401, 429, timeout, conexão)
    - Frontend: exibir mensagem detalhada do servidor junto ao botão
    - Config: ANTHROPIC_API_KEY já documentado no .env.example
```

## Testes Recomendados

### 1. ANTHROPIC_API_KEY não configurada
```bash
# Railway: remover ANTHROPIC_API_KEY do env
# Esperado: "Sugestão IA indisponível: ANTHROPIC_API_KEY não configurada no servidor..."
```

### 2. ANTHROPIC_API_KEY inválida
```bash
# Railway: definir ANTHROPIC_API_KEY=sk-xxxx-invalido
# Esperado: "Erro na API Claude (HTTP 401). ANTHROPIC_API_KEY inválida."
```

### 3. Limite de requisições excedido
```bash
# Chamar sugestão IA mais de 10x em 1 minuto
# Esperado: "Erro na API Claude (HTTP 429). Limite de requisições excedido. Tente em alguns minutos."
```

### 4. Erro de conexão
```bash
# Simular desligamento da rede durante a chamada
# Esperado: "Erro de conexão com a API Claude. Verifique sua conexão de internet..."
```

### 5. Timeout (>30s)
```bash
# Mock da API Claude com delay > 30s
# Esperado: "Timeout ao chamar a API Claude. A requisição demorou muito tempo. Tente novamente."
```

## Deploy

Railway detectará automaticamente o push e fará deploy em produção.

URL em produção:
- Backend: https://msmpro-production.up.railway.app/api/v1/perguntas/{id}/suggest
- Frontend: https://msmprofrontend-production.up.railway.app/perguntas

## Monitoramento

Após deploy, verificar logs do Railway:
```bash
railway logs --service MSM_Pro
# Procurar por: "Claude API" ou "sugestão IA"
```

## Próximas Melhorias

1. Cache de sugestões por períodos mais longos (reduz chamadas à API)
2. Rate limiting no frontend (máx 3 tentativas por minuto por usuário)
3. Retry automático com backoff exponencial para erros temporários (429, timeout)
4. Analytics: registrar frequência de erros por tipo em log estruturado
5. Telemetria: monitorar latência média da Claude API
