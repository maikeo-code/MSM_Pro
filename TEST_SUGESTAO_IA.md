# Testes Manuais — Sugestão IA no Módulo Perguntas

## Pré-requisitos

1. Sistema em produção (Railway) ou em desenvolvimento local
2. Usuário autenticado na conta do MSM_Pro
3. Pelo menos 1 pergunta pendente (UNANSWERED)

## Endpoints Testados

```
POST /api/v1/perguntas/{question_id}/suggest
Content-Type: application/json
Authorization: Bearer {access_token}

Body:
{
  "regenerate": false
}

Response:
{
  "suggestion": "string",
  "confidence": "high|medium|low",
  "question_type": "string | null",
  "cached": boolean,
  "latency_ms": integer | null
}
```

## Cenário 1: Sem ANTHROPIC_API_KEY (Desenvolvimento)

### Setup
```bash
# Remover ANTHROPIC_API_KEY do .env
unset ANTHROPIC_API_KEY

# Iniciar backend
cd backend
python -m uvicorn app.main:app --reload
```

### Teste
```bash
# 1. Pegar token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"maikeo@msmrp.com","password":"Msm@2026"}' | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

# 2. Gerar sugestão
curl -X POST http://localhost:8000/api/v1/perguntas/{question_id}/suggest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"regenerate": false}' | python3 -m json.tool
```

### Resultado Esperado
```json
{
  "suggestion": "Sugestão IA indisponível: ANTHROPIC_API_KEY não configurada no servidor. Configure a variável de ambiente no Railway.",
  "confidence": "low",
  "question_type": "availability",
  "cached": false,
  "latency_ms": 150
}
```

### Frontend
- Botão "Gerar sugestão IA" clicável
- Ao clicar: "Gerando sugestão..." (loading)
- Resultado: mensagem de erro abaixo do botão
- Texto: "Sugestão IA indisponível: ANTHROPIC_API_KEY..."

---

## Cenário 2: Com ANTHROPIC_API_KEY Válida (Produção)

### URL
```
https://msmprofrontend-production.up.railway.app/perguntas
```

### Teste
1. Autenticar com `maikeo@msmrp.com` / `Msm@2026`
2. Ir para aba "Pendentes"
3. Selecionar uma pergunta
4. Clicar em "Gerar sugestão IA"
5. Aguardar resposta (2-5 segundos)

### Resultado Esperado
- Botão muda para "Gerando sugestão..." com spinner
- Sugestão aparece em card violeta
- Badge de confiança (Alta/Média/Baixa)
- Botões "Usar resposta" e "Regenerar"
- Latência entre 2000-5000ms

### Resultado se Erro
- Botão volta a "Gerar sugestão IA" após 2-3s
- Mensagem de erro abaixo:
  - Se 401: "ANTHROPIC_API_KEY inválida"
  - Se 429: "Limite de requisições excedido. Tente em alguns minutos."
  - Se timeout: "A requisição demorou muito tempo. Tente novamente."
  - Se conexão: "Verifique sua conexão de internet"

---

## Cenário 3: ANTHROPIC_API_KEY Inválida (Teste Negativo)

### Setup (Railway)
```bash
# 1. Ir para Railway dashboard
# 2. Projeto: vibrant-exploration
# 3. Serviço: MSM_Pro
# 4. Variables
# 5. Editar ANTHROPIC_API_KEY = "sk-xxxx-fake-key-xxxx"
# 6. Redeploy
```

### Teste
```bash
# Curl
TOKEN=$(curl -s -X POST https://msmpro-production.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"maikeo@msmrp.com","password":"Msm@2026"}' | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

curl -X POST https://msmpro-production.up.railway.app/api/v1/perguntas/{question_id}/suggest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"regenerate": false}' | python3 -m json.tool
```

### Resultado Esperado
```json
{
  "suggestion": "Erro na API Claude (HTTP 401). ANTHROPIC_API_KEY inválida.",
  "confidence": "low",
  "question_type": null,
  "cached": false,
  "latency_ms": 200
}
```

---

## Cenário 4: Rate Limit (HTTP 429)

### Setup
```bash
# Chamar sugestão IA muito rapidamente em loop (simular abuso)
for i in {1..15}; do
  curl -X POST https://msmpro-production.up.railway.app/api/v1/perguntas/{question_id}/suggest \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"regenerate": true}' &
done
wait
```

### Resultado Esperado (a partir da 11ª chamada)
```json
{
  "suggestion": "Erro na API Claude (HTTP 429). Limite de requisições excedido. Tente em alguns minutos.",
  "confidence": "low",
  "question_type": null,
  "cached": false,
  "latency_ms": 100
}
```

---

## Cenário 5: Conexão Perdida (Connection Error)

### Setup
```bash
# Desligar internet durante a chamada
# Ou usar Mock/Proxy que simula connection error
```

### Resultado Esperado
```json
{
  "suggestion": "Erro de conexão com a API Claude. Verifique sua conexão de internet e tente novamente.",
  "confidence": "low",
  "question_type": null,
  "cached": false,
  "latency_ms": 1200
}
```

---

## Cenário 6: Timeout (>30s)

### Setup
```bash
# Mock da API Claude com delay de 31s
# Ou usar Proxy que injeta latência
```

### Resultado Esperado
```json
{
  "suggestion": "Timeout ao chamar a API Claude. A requisição demorou muito tempo. Tente novamente.",
  "confidence": "low",
  "question_type": null,
  "cached": false,
  "latency_ms": 31000
}
```

---

## Checklist de Validação

- [ ] Teste 1: Sem ANTHROPIC_API_KEY — mensagem clara
- [ ] Teste 2: Com chave válida — sugestão gerada em 2-5s
- [ ] Teste 3: Chave inválida (401) — mensagem específica
- [ ] Teste 4: Rate limit (429) — mensagem sobre limite
- [ ] Teste 5: Conexão — mensagem sobre internet
- [ ] Teste 6: Timeout — mensagem sobre tempo
- [ ] Frontend: Botão em loading state durante chamada
- [ ] Frontend: Mensagem de erro visível abaixo do botão
- [ ] Frontend: Poder clicar novamente sem recarregar
- [ ] Frontend: Sugestão em cache na 2ª chamada com o mesmo texto
- [ ] Backend: Logs contêm contexto do erro (status, body, etc.)

---

## Logs a Verificar (Railway)

```bash
# SSH into Railway
railway run --service MSM_Pro -- bash

# Tail logs de erro
tail -f /tmp/logs/app.log | grep -i "claude\|anthropic\|sugestao"
```

### Esperado
```
ERROR - Claude API HTTP error: status=401 body={"error":{"type":"authentication_error"}}
ERROR - Erro de conexão com Claude API: ConnectError(...)
ERROR - Timeout ao chamar Claude API
```

---

## Após Validação

1. Restaurar ANTHROPIC_API_KEY válida no Railway
2. Executar redeploy
3. Testar novamente com sugestão gerando corretamente
4. Registrar em `_auto_learning/db/learning.db` se houver sistema
5. Considerar adicionar teste automatizado em `backend/tests/`
