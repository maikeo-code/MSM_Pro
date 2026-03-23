# Testes para o Sistema de Refresh Automático de Token OAuth

## 1. Verificação Rápida Pós-Deploy

### 1.1 Verificar que a task de refresh roda

```bash
# Acessar Railway Logs do backend
railway logs --tail 50 --follow

# Procurar por esta mensagem (roda a cada 2h)
"Renovando tokens para X contas ML"
"Token renovado: account=..."
"Renovação concluída: X sucesso, 0 erros"
```

### 1.2 Verificar que token está atualizado no banco

```bash
# Acessar psql no Railway
railway psql

# Ver token_expires_at da sua conta
SELECT id, nickname, token_expires_at, updated_at
FROM ml_accounts
WHERE is_active = true;

# Deve mostrar token_expires_at recente (ultima 2h)
# Ex: 2026-03-23 12:00:00+00 (se rodou há pouco tempo)
```

### 1.3 Verificar que sync funciona

```bash
# Login
TOKEN=$(curl -s -X POST https://msmpro-production.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"maikeo@msmrp.com","password":"Msm@2026"}' | jq -r '.access_token')

# Listar listings (deve funcionar)
curl -s https://msmpro-production.up.railway.app/api/v1/listings/ \
  -H "Authorization: Bearer $TOKEN" | jq '.length'

# Deve retornar número > 0
```

## 2. Teste de Expiração Simulada

### 2.1 Forçar expiração de token no banco

```bash
# Conectar ao PostgreSQL Railway
railway psql

# Atualizar token_expires_at para o passado (simula expiração)
UPDATE ml_accounts
SET token_expires_at = NOW() - INTERVAL '1 hour'
WHERE nickname = 'MSM_PRIME';

# Verificar que foi atualizado
SELECT nickname, token_expires_at FROM ml_accounts WHERE nickname = 'MSM_PRIME';
```

### 2.2 Disparar task de refresh

```bash
# Via Django admin (se disponível) ou via código:
from app.jobs.tasks_tokens import _refresh_expired_tokens_async
import asyncio
result = asyncio.run(_refresh_expired_tokens_async())
print(result)
# Deve retornar: {'success': True, 'refreshed': 1, 'errors': 0}
```

### 2.3 Verificar token foi renovado

```bash
# No psql:
SELECT nickname, token_expires_at FROM ml_accounts WHERE nickname = 'MSM_PRIME';

# token_expires_at deve estar ~6h no futuro novamente
```

### 2.4 Verificar que sync ainda funciona

```bash
# Listar listings novamente (deve funcionar)
curl -s https://msmpro-production.up.railway.app/api/v1/listings/ \
  -H "Authorization: Bearer $TOKEN" | jq '.length'
```

## 3. Teste de 401 Automático

Este teste valida que o cliente HTTP faz refresh automático quando recebe 401.

### 3.1 Setup: Corromper token no cliente (temporariamente)

```python
# No backend (terminal interativo ou debug):
from app.core.database import AsyncSessionLocal
from app.auth.models import MLAccount
from sqlalchemy import select

async def test_401_refresh():
    async with AsyncSessionLocal() as db:
        # Busca conta
        result = await db.execute(
            select(MLAccount).where(MLAccount.nickname == 'MSM_PRIME')
        )
        account = result.scalar_one()

        # Salva token original
        original_token = account.access_token

        # Corrompe token (adiciona 'xxx' no final)
        account.access_token = original_token + 'xxx'
        await db.commit()

        # Agora: next API call com este token vai retornar 401
        # O cliente deve fazer refresh automático

        # Chama sync (vai tentar 401, depois renovar)
        from app.jobs.tasks_listings import _sync_listing_snapshot_async
        result = await _sync_listing_snapshot_async(listing_id='<seu-listing-id>')
        print(result)
        # Deve mostrar sucesso (refresh funcionou)

        # Restaura token original
        account.access_token = original_token
        await db.commit()

# Executar:
import asyncio
asyncio.run(test_401_refresh())
```

### 3.2 Observar logs durante teste

```bash
railway logs --tail 100 --follow | grep -E "401|Token expirado|Token renovado"

# Deve mostrar sequência como:
# "Token expirado para conta X, tentando renovar..."
# "Token renovado para conta X, repetindo requisição..."
```

## 4. Teste de Retry com Falha

Este teste valida que a task de refresh tenta 3 vezes antes de desistir.

### 4.1 Corromper refresh_token

```bash
# No psql:
UPDATE ml_accounts
SET refresh_token = 'invalid_token_xxx'
WHERE nickname = 'MSM_PRIME';
```

### 4.2 Disparar refresh

```bash
# Via código ou manualmente
# Resultado deve ser: success=False, errors=1
```

### 4.3 Observar retry

```bash
railway logs --tail 100 --follow | grep -E "Tentativa|retry"

# Deve mostrar:
# "Tentativa 1/3 falhou para MSM_PRIME: ..."
# "Tentativa 2/3 falhou para MSM_PRIME: ..."
# "Tentativa 3/3 falhou para MSM_PRIME: ..."
# "Falha permanente ao renovar token de MSM_PRIME"
```

### 4.4 Restaurar refresh_token

```bash
# No psql, restaurar token válido
# Ou reconectar OAuth no frontend
```

## 5. Teste de Performance

### 5.1 Verificar que refresh não bloqueia sync

```bash
# Cronômetro: rodar sync enquanto refresh está acontecendo
# (force refresh a rodar com UPDATE no banco + manualmente disparar)

# Resultado esperado:
# - Sync roda normalmente
# - Refresh roda em paralelo (worker separado)
# - Sem deadlocks

time curl -s https://msmpro-production.up.railway.app/api/v1/listings/ \
  -H "Authorization: Bearer $TOKEN"
# Deve levar < 2 segundos
```

### 5.2 Verificar que múltiplas contas renovam em paralelo

```bash
# Se tiver 2+ contas ML ativas:

# Via psql, forçar ambas a expiração
UPDATE ml_accounts
SET token_expires_at = NOW() - INTERVAL '1 hour'
WHERE is_active = true;

# Disparar refresh
# Deve renovar ambas em paralelo, não sequencialmente

# Observar logs:
# "Renovando tokens para 2 contas ML"
# "Token renovado: account=... (mais rápido que 2 secs)"
# "Renovação concluída: 2 sucesso, 0 erros"
```

## 6. Teste de Estado Persistente

### 6.1 Verificar que token persiste após refresh

```bash
# Fazer refresh
# Matar backend (simula crash)
railway down

# Ligar backend
railway up --detach

# Verificar que sync ainda funciona com token renovado
curl -s https://msmpro-production.up.railway.app/api/v1/listings/ \
  -H "Authorization: Bearer $TOKEN"

# Deve funcionar porque token foi salvo no banco (step 2.4)
```

## 7. Monitoramento Contínuo

### 7.1 Setup alertas para erros de refresh

```bash
# No seu serviço de logs (Sentry, Datadog, etc):
# Criar alerta para:
# - "Falha ao renovar token" em ERROR
# - "Renovação concluída" com errors > 0

# Action: Se alerta dispara:
# 1. Verificar logs recentes
# 2. Verificar status do OAuth no Mercado Livre
# 3. Verificar que refresh_token não expirou
# 4. Se refresh_token expirou: notificar usuário
```

### 7.2 Dashboard de saúde de token

```bash
# Criar uma view SQL para monitorar:
SELECT
    nickname,
    access_token_age_hours = EXTRACT(EPOCH FROM (NOW() - updated_at)) / 3600,
    token_expires_in_hours = EXTRACT(EPOCH FROM (token_expires_at - NOW())) / 3600,
    CASE
        WHEN token_expires_in_hours < 0 THEN 'EXPIRADO'
        WHEN token_expires_in_hours < 0.5 THEN 'CRÍTICO (< 30min)'
        WHEN token_expires_in_hours < 2 THEN 'AVISO (< 2h)'
        ELSE 'OK'
    END AS status
FROM ml_accounts
WHERE is_active = true
ORDER BY token_expires_in_hours ASC;

# Rodar a cada 1h para monitorar
```

## Checklist de Validação Pós-Deploy

- [ ] Logs mostram "Renovação concluída: X sucesso, 0 erros" a cada 2h
- [ ] `token_expires_at` sempre está < 2h no futuro (no banco)
- [ ] Sync de listings funciona sem erros 401
- [ ] Se força 401, client automaticamente renova (log mostra "Token renovado")
- [ ] Refresh falha graciosamente com error_details preenchido
- [ ] Token persiste após restart do backend
- [ ] Múltiplas contas renovam em paralelo (sem espera serial)
- [ ] Sem aumento de latência em sync (refresh roda em worker separado)

## Troubleshooting

### "Token renovado" aparece em log mas sync ainda falha com 401

**Causa:** Token foi renovado mas ainda há requisições pendentes com token antigo

**Solução:**
1. Aumentar timeout em refresh (aguardar requisições pendentes)
2. Ou adicionar retry automático em MLClientError

### Refresh roda mas token_expires_at não muda

**Causa:** Banco não foi commitado após update

**Solução:**
1. Verificar que `await db.commit()` está sendo chamado
2. Verificar logs de erro de banco (permissões, etc)

### refresh_token sempre inválido

**Causa:** Refresh_token expirou (6 meses após geração)

**Solução:**
1. Usuário reconectar OAuth via frontend
2. Novo refresh_token será gerado

### Task de refresh não roda

**Causa:**
- Celery beat não está ativo
- Task não está registrada

**Solução:**
```bash
# Verificar que celery está rodando
ps aux | grep celery

# Verificar que beat está agendado (na config)
grep "refresh-expired-tokens" backend/app/core/celery_app.py
```
