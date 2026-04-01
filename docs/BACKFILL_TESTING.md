# Testes do Sistema de Backfill de Pedidos

## Status da Implementação

### Implementado
- ✅ Função assíncrona `_backfill_orders_after_reconnect_async()` em `tasks_orders.py`
- ✅ Task Celery `backfill_orders_after_reconnect` em `tasks.py`
- ✅ Disparador automático em `tasks_tokens.py` (após refresh bem-sucedido)
- ✅ Disparador em OAuth callback em `auth/router.py`
- ✅ Endpoint manual `POST /api/v1/auth/ml/accounts/{account_id}/backfill-orders` em `auth/router.py`
- ✅ Notificações in-app quando refresh de token falha permanentemente
- ✅ Documentação completa em `BACKFILL_ORDERS_FEATURE.md`

### Arquivos Modificados
1. `backend/app/jobs/tasks_orders.py` — contém `_backfill_orders_after_reconnect_async()`
2. `backend/app/jobs/tasks.py` — contém wrapper da task Celery
3. `backend/app/jobs/tasks_tokens.py` — disparador automático + notificações
4. `backend/app/auth/router.py` — OAuth callback + endpoint manual
5. `frontend/src/services/notificationsService.ts` — serviço de notificações

## Testes Manuais

### 1. Teste de Backfill Automático (após token refresh)

**Setup**:
1. Conectar conta ML via `/api/v1/auth/ml/connect`
2. Forçar expiração de token (atualizar `token_expires_at` para data passada no banco)
3. Aguardar próxima execução de `refresh_expired_tokens` (a cada 4h) ou disparar manualmente

**Verificação**:
```bash
# 1. Verificar token renovado
SELECT id, nickname, token_expires_at 
FROM ml_accounts 
WHERE id = '<account_id>';

# 2. Verificar SyncLog com backfill disparado
SELECT * FROM sync_logs 
WHERE task_name = 'backfill_orders_after_reconnect'
  AND ml_account_id = '<account_id>'
ORDER BY started_at DESC 
LIMIT 5;

# 3. Contar pedidos novos
SELECT COUNT(*) FROM orders 
WHERE ml_account_id = '<account_id>' 
  AND created_at >= NOW() - INTERVAL '7 days';
```

### 2. Teste de Reconexão Manual (OAuth callback)

**Setup**:
1. Desconectar conta: `DELETE FROM ml_accounts WHERE id = '<account_id>'`
2. Ou desativar: `UPDATE ml_accounts SET is_active = false WHERE id = '<account_id>'`
3. Ir para `/configuracoes` no frontend
4. Clicar em "Conectar Conta ML"
5. Fazer login no ML e autorizar

**Verificação**:
```bash
# 1. Verificar callback executou
SELECT * FROM sync_logs 
WHERE task_name = 'backfill_orders_after_reconnect'
ORDER BY started_at DESC LIMIT 1;

# 2. Logs da aplicação
railway logs --service MSM_Pro --tail 50 | grep -i backfill

# 3. Verificar pedidos recuperados
SELECT COUNT(*), MIN(order_date) FROM orders 
WHERE ml_account_id = '<account_id>';
```

### 3. Teste de Backfill Manual (endpoint)

**Setup**:
```bash
# 1. Obter account_id
TOKEN=$(curl -s -X POST https://msmpro-production.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"maikeo@msmrp.com","password":"Msm@2026"}' \
  | jq -r '.access_token')

ACCOUNT_ID=$(curl -s https://msmpro-production.up.railway.app/api/v1/auth/ml/accounts \
  -H "Authorization: Bearer $TOKEN" | jq -r '.[0].id')

echo "Account: $ACCOUNT_ID"

# 2. Disparar backfill de 7 dias
curl -s -X POST "https://msmpro-production.up.railway.app/api/v1/auth/ml/accounts/$ACCOUNT_ID/backfill-orders?days=7" \
  -H "Authorization: Bearer $TOKEN" | jq .

# 3. Resposta esperada
# {
#   "status": "backfill_scheduled",
#   "account_id": "...",
#   "nickname": "...",
#   "days": 7,
#   "task_id": "abc123...",
#   "message": "Backfill de 7 dias agendado..."
# }
```

**Verificação**:
```bash
# 1. Acompanhar execução
# Via Flower: http://localhost:5555/ (se rodando localmente)

# 2. Verificar SyncLog
SELECT task_name, status, items_processed, items_failed, duration_ms
FROM sync_logs 
WHERE ml_account_id = '$ACCOUNT_ID'
ORDER BY started_at DESC LIMIT 1;

# 3. Contar pedidos antes/depois
SELECT COUNT(*) FROM orders WHERE ml_account_id = '$ACCOUNT_ID';
```

### 4. Teste de Erro (token inválido)

**Setup**:
1. Conectar conta ML normal
2. Invalidar token no banco: `UPDATE ml_accounts SET access_token = 'INVALID' WHERE id = '<id>'`
3. Disparar backfill manual

**Verificação**:
```bash
# SyncLog deve mostrar "failed"
SELECT status, error 
FROM sync_logs 
WHERE task_name = 'backfill_orders_after_reconnect'
ORDER BY started_at DESC LIMIT 1;

# Resultado esperado: status = 'failed', error contém detalhes do erro
```

### 5. Teste de Paginação (muitos pedidos)

**Setup**:
1. Disparar backfill com 30 dias (máximo)
2. Verificar que paginação funciona (offset aumenta, paging.total respeitado)

**Verificação**:
```bash
# 1. Logs da tarefa devem mostrar paginação
railway logs --service MSM_Pro --tail 100 | grep -i "processed\|offset"

# 2. Exemplo de log esperado:
# "Backfill: processados 50 pedidos, criados 45, atualizados 2"
# "Backfill: processados 100 pedidos, criados 92, atualizados 3"
```

## Testes Integrados (pytest)

### Exemplo de teste unitário (a ser implementado)

```python
# backend/tests/test_backfill_orders.py
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.vendas.models import Order
from app.auth.models import MLAccount
from app.jobs.tasks_orders import _backfill_orders_after_reconnect_async

@pytest.mark.asyncio
async def test_backfill_orders_after_reconnect(db, ml_account):
    """Testa backfill de 7 dias para uma conta ML"""
    # Setup
    account_id = str(ml_account.id)
    
    # Execute
    result = await _backfill_orders_after_reconnect_async(account_id, days_to_backfill=7)
    
    # Verify
    assert result["success"] == True
    assert result["created"] >= 0
    assert result["updated"] >= 0
    assert result["days_backfilled"] == 7
    
    # Verificar que pedidos foram salvos no banco
    orders = await db.execute(
        select(Order).where(Order.ml_account_id == ml_account.id)
    )
    orders_list = orders.scalars().all()
    assert len(orders_list) > 0

@pytest.mark.asyncio
async def test_backfill_max_30_days(db, ml_account):
    """Testa que máximo de 30 dias é respeitado"""
    result = await _backfill_orders_after_reconnect_async(str(ml_account.id), days_to_backfill=60)
    assert result["days_backfilled"] == 30  # Limitado a 30

@pytest.mark.asyncio
async def test_backfill_no_token(db, ml_account):
    """Testa comportamento com token inválido"""
    ml_account.access_token = None
    await db.commit()
    
    result = await _backfill_orders_after_reconnect_async(str(ml_account.id))
    assert result["success"] == False
    assert result["reason"] == "no_access_token"
```

## Checklist de Validação

- [ ] Backfill automático dispara após token refresh bem-sucedido
- [ ] Backfill automático **não** dispara se token estava expirado < 24h
- [ ] OAuth callback dispara backfill de 7 dias
- [ ] Endpoint manual aceita `days` entre 1-30
- [ ] Endpoint manual rejeita `days` > 30 com erro 422
- [ ] SyncLog registra cada execução com status, items_processed, duration_ms
- [ ] Pedidos não são duplicados (upsert funciona)
- [ ] Frete com fallback a 0 quando shipment indisponível
- [ ] Listing_id é NULL quando MLB não encontrado
- [ ] Notificação in-app criada quando refresh falha permanentemente
- [ ] Redis lock impede refresh paralelo (testado)
- [ ] API rate-limit tratado com retry (MLClient)

## Métricas de Sucesso

1. **Taxa de sucesso**: > 90% das execuções (status="success")
2. **Tempo de execução**: < 5min para 30 dias de backfill (~1000 pedidos)
3. **Duplicação zero**: Nenhum pedido duplicado após backfill
4. **Cobertura de gaps**: Backfill recupera 100% dos pedidos da API ML nos dias solicitados

## Troubleshooting Comum

| Sintoma | Causa Provável | Solução |
|---------|---|---|
| Backfill não roda | Celery offline | `railway logs --service MSM_Pro` \| grep celery |
| SyncLog mostra "skipped" | Lock ativo (refresh em progresso) | Aguardar 5min, tentar novamente |
| SyncLog mostra "failed" | Token inválido | Reconectar conta via OAuth |
| Pedidos antigos não aparecem | Backfill rodou após sync anterior limpar dados? | Disparar backfill novamente |
| Mesmo pedido 2x no banco | Bug de upsert (raro) | Verificar SQL: DELETE duplicados, rodar backfill novamente |

## Referências
- Feature doc: `docs/BACKFILL_ORDERS_FEATURE.md`
- Code: `backend/app/jobs/tasks_orders.py`
- Code: `backend/app/jobs/tasks_tokens.py`
- Code: `backend/app/auth/router.py`
