# Checklist de Verificação: OAuth Token Refresh

**Data:** 2026-04-01  
**Para:** Validação em produção

Use este checklist para confirmar que o sistema de OAuth Token Refresh está funcionando corretamente.

---

## SEÇÃO 1: Verificação de Código

### Escopo offline_access
- [ ] Verificar que URL OAuth inclui `scope=offline_access+read+write`
  ```bash
  # Teste local:
  cd backend && python -c "import sys; sys.path.insert(0, '.'); from app.auth.service import get_ml_auth_url; print(get_ml_auth_url())"
  # Deve conter: scope=offline_access+read+write
  
  # Teste em produção:
  curl -s "https://msmpro-production.up.railway.app/api/v1/auth/oauth-url" | grep -o "scope=[^&]*"
  # Esperado: scope=offline_access+read+write
  ```

- [ ] Confirmar arquivo: `backend/app/auth/service.py` linhas 80-95
  - [ ] Linha 89: `"scope": "offline_access read write",`

### Funções de Refresh
- [ ] Arquivo `backend/app/auth/service.py` contém:
  - [ ] Função `refresh_ml_token()` (linhas 123-133)
  - [ ] Função `refresh_ml_token_by_id()` (linhas 135-223)
  - [ ] Função `_exchange_refresh_token()` (linhas 225-279)

- [ ] Logging detalhado presente:
  - [ ] `logger.error()` com motivo do erro (linhas 253-266)
  - [ ] `logger.info()` com sucesso e expires_in (linhas 270-273)
  - [ ] Rastreamento de `last_token_refresh_at` (linhas 193, 214)
  - [ ] Counter `token_refresh_failures` (linhas 172, 194, 213)

### Lock Distribuído
- [ ] Arquivo `backend/app/jobs/tasks_tokens.py` contém:
  - [ ] Função `_acquire_token_refresh_lock()` (linhas 26-54)
  - [ ] Função `_release_token_refresh_lock()` (linhas 57-66)
  - [ ] Usage em `_refresh_expired_tokens_async()` (linhas 101-179)

### Parada em Falha de Refresh
- [ ] Arquivo `backend/app/jobs/tasks_listings.py`:
  - [ ] Linhas 55-81: Check de token_expires_at
  - [ ] Linhas 70-80: Return com error se refresh falha
  - [ ] Campo `skip_reason: "token_refresh_failed"`

### Intervalo de Refresh
- [ ] Arquivo `backend/app/core/celery_app.py`:
  - [ ] Linha 62: `"schedule": crontab(minute="*/30"),`
  - [ ] Significa: A cada 30 minutos (minutos 0 e 30 de cada hora)

---

## SEÇÃO 2: Verificação em Produção

### Logs de Refresh (últimas 24h)
- [ ] Acessar Railway logs: `railway logs --follow`
- [ ] Filtrar por "Token renovado":
  ```
  railway logs --follow | grep "Token renovado"
  ```
- [ ] Esperado: 2-3 logs por hora (a cada 30 min)
  - Exemplo log: `Token renovado com sucesso para MSM_PRIME: expires_at=2026-04-01T12:30:00+00:00, elapsed=0.45s`

### Verificar Lock Distribuído
- [ ] Acessar Railway Redis:
  ```bash
  # Connect to Redis via Railway CLI
  railway run -- redis-cli KEYS "ml_token_refresh:*"
  ```
- [ ] Se houver chaves: Lock foi adquirido recentemente
- [ ] Se não houver: Locks foram liberados (normal)

### Verificar Token Salvo no Banco
- [ ] Acessar Railway PostgreSQL:
  ```bash
  railway run -- psql -c "SELECT id, nickname, token_expires_at, last_token_refresh_at, token_refresh_failures FROM ml_accounts;"
  ```
- [ ] Verificar:
  - [ ] `token_expires_at` é sempre futuro (nunca passado)
  - [ ] `last_token_refresh_at` é recente (< 30 min)
  - [ ] `token_refresh_failures` é 0 (ou baixo: 1-2)

### Dashboard de Contas ML
- [ ] Acessar: https://msmprofrontend-production.up.railway.app/configuracoes
- [ ] Verificar cada conta:
  - [ ] Status = "Ativo" (não "Expirado")
  - [ ] Botão "Conectar" não aparece (conta já autenticada)

### Verificar Sync de Listings
- [ ] Acessar: https://msmprofrontend-production.up.railway.app/dashboard
- [ ] Verificar dados:
  - [ ] Anúncios aparecem (fetch bem-sucedido)
  - [ ] Preços estão atualizados
  - [ ] KPIs (vendas, visitas) são recentes

---

## SEÇÃO 3: Testes Manuais

### Teste 1: Simular Expiração de Token (ADMIN ONLY)

**⚠️ Apenas em staging — NÃO em produção sem backup**

```bash
# 1. SSH para Railway container
railway run -- bash

# 2. Entrar no psql
psql $DATABASE_URL

# 3. Simular expiração (30 minutos atrás)
UPDATE ml_accounts 
SET token_expires_at = NOW() - INTERVAL '30 minutes'
WHERE nickname = 'MSM_PRIME';

# 4. Aguardar próximo refresh (próximos 30 min)
# 5. Verificar logs
railway logs --follow | grep "Token renovado"

# 6. Confirmar em banco que token foi atualizado
SELECT token_expires_at FROM ml_accounts WHERE nickname = 'MSM_PRIME';
# Deve estar ~6h no futuro
```

**Resultado esperado:**
- [ ] Task `refresh_expired_tokens` roda
- [ ] Log: "Token renovado com sucesso para MSM_PRIME"
- [ ] Banco: `token_expires_at` atualizado para futuro

---

### Teste 2: Verificar Retry Automático

**Se conseguir trigger de erro de ML sem derrubar inteiro:**

```bash
# Observar logs enquanto refresh está acontecendo
railway logs --follow

# Se vir erro 400/429:
# "Tentativa 1/3 falhou..." → aguardar backoff → "Tentativa 2/3"
```

**Resultado esperado:**
- [ ] Múltiplas tentativas com backoff
- [ ] Eventual sucesso ou falha clara
- [ ] Log com motivo exato

---

### Teste 3: Testar Sync com Token Expirado

```bash
# 1. Simular expiração (como em Teste 1)
UPDATE ml_accounts SET token_expires_at = NOW() - INTERVAL '30 minutes';

# 2. Disparar sync manualmente
curl -X POST https://msmpro-production.up.railway.app/api/v1/jobs/sync-now \
  -H "Authorization: Bearer $TOKEN"

# 3. Verificar logs
railway logs --follow

# 4. Verificar resultado
# Se refresh funcionou: sync prossegue normalmente
# Se refresh falhou: sync aborta com skip_reason
```

**Resultado esperado:**
- [ ] Antes de sync: Log "Token expira em < 1h, renovando..."
- [ ] Log: "Token renovado com sucesso"
- [ ] Sync: Processa normalmente com novo token

---

## SEÇÃO 4: Verificação de Notificações

### Simular Conta com 5 Falhas
```bash
# Marcar conta como needs_reauth
UPDATE ml_accounts 
SET token_refresh_failures = 5, needs_reauth = true
WHERE nickname = 'TEST_ACCOUNT';

# Aguardar próximo refresh (30 min)
# Verificar notificação in-app
```

**Resultado esperado:**
- [ ] Notificação in-app criada (tabela `notifications`)
- [ ] Mensagem: "Conta 'TEST_ACCOUNT' desconectada"
- [ ] Usuário vê na página Configurações

---

## SEÇÃO 5: Testes de Resiliência

### Teste: Redis Down

```bash
# 1. Derrubar Redis (simular ou snapshot)
# 2. Aguardar próximo refresh (30 min)
# 3. Verificar logs
```

**Resultado esperado:**
- [ ] Log: "Erro ao adquirir lock Redis... prosseguindo sem lock"
- [ ] Refresh ainda acontece (fail-open)
- [ ] Possível race condition (raro), mas app não quebra

---

### Teste: ML API Lenta (Timeout)

```bash
# Observar quando refresh roda (a cada 30 min)
# Se houver timeout:
```

**Resultado esperado:**
- [ ] Log: "Tentativa 1/3 falhou: timeout"
- [ ] Retry automático com backoff exponencial
- [ ] Eventual sucesso (se ML volta) ou erro claro

---

## SEÇÃO 6: Performance

### Verificar Latência de Refresh
```bash
# Em logs, procurar por:
"elapsed=X.XXs"

# Exemplo:
"Token renovado com sucesso... elapsed=0.35s"
```

- [ ] Latência esperada: 0.3-0.8 segundos
- [ ] Se > 2s: Investigar rede/ML API lentidão
- [ ] Se > 5s: Problema crítico, alertar

---

### Verificar Uso de Memória
```bash
# Redis memory
railway run -- redis-cli INFO memory

# Esperado: ~10-50MB (Redis locks são temporários, TTL 60s)
```

- [ ] Memória não deve crescer linearmente
- [ ] Se cresce: Investigar leak (locks não liberados)

---

## SEÇÃO 7: Documentação

### Verificar Arquivos Criados
- [ ] `docs/OAUTH_TOKEN_REFRESH_SYSTEM.md` — Explicação completa
- [ ] `docs/TESTING_TOKEN_REFRESH.md` — Guia de testes
- [ ] `OAUTH_TOKEN_FIX_VERIFICATION.md` — Esta verificação
- [ ] `OAUTH_TOKEN_IMPROVEMENTS_ROADMAP.md` — Melhorias futuras
- [ ] `OAUTH_TOKEN_EXECUTIVE_SUMMARY.md` — Resumo para stakeholders

---

## SEÇÃO 8: Checklist Final

### Pré-Deploy
- [ ] Todas as 5 tarefas implementadas
- [ ] Nenhum erro de import em Python
- [ ] Nenhum erro de TypeScript
- [ ] Tests passam: `pytest` e `npm test`

### Pós-Deploy (Produção)
- [ ] Logs mostram refresh a cada 30 min
- [ ] Nenhum erro crítico em 24h
- [ ] Tokens sempre válidos (token_expires_at > NOW())
- [ ] Notificações criadas quando necessário

### Antes de Considerar Concluído
- [ ] Usuário pode conectar conta ML (OAuth flow)
- [ ] Dashboard mostra dados sem erro de token
- [ ] Sync automático roda sem 401
- [ ] Documentação está atualizada

---

## Resultado Final

Se TODOS os checkboxes acima estão marcados ✅:

**OAuth Token Refresh está FUNCIONANDO CORRETAMENTE em produção.**

Você pode:
1. Informar ao usuário que sistema está pronto
2. Monitorar logs periodicamente
3. Implementar melhorias do roadmap na próxima sprint

---

## Links Rápidos

| O que | Onde |
|------|------|
| Código | `backend/app/auth/service.py` |
| Tasks | `backend/app/jobs/tasks_tokens.py` |
| Agendamento | `backend/app/core/celery_app.py` |
| Docs completas | `docs/OAUTH_TOKEN_REFRESH_SYSTEM.md` |
| Testes | `docs/TESTING_TOKEN_REFRESH.md` |
| Dashboard | https://msmprofrontend-production.up.railway.app |
| Logs | `railway logs --follow` |
| Banco | `railway run -- psql -c "SELECT ..."` |

---

**Última atualização:** 2026-04-01  
**Próxima revisão:** 2026-05-01 (após 1 mês em produção)
