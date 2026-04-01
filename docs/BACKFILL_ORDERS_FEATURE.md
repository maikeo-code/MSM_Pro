# Backfill de Pedidos Após Reconexão de Conta ML

## Visão Geral

Quando uma conta do Mercado Livre (ML) fica desconectada por um período (token expirado e não renovado automaticamente), seus dados de pedidos são perdidos. A sync normal do MSM_Pro apenas busca os últimos 2 dias de pedidos.

Esta feature implementa um sistema automático e manual de **backfill de pedidos históricos** que preenche os gaps de desconexão.

## Arquitetura

### Componentes

1. **Task Celery**: `backfill_orders_after_reconnect`
   - Arquivo: `backend/app/jobs/tasks.py`
   - Função assíncrona: `backend/app/jobs/tasks_orders.py`
   - Executa backfill de N dias para uma conta específica

2. **Disparadores Automáticos**

   a) **Refresh automático de tokens** (`tasks_tokens.py`)
   - Detecta quando um token foi renovado após estar expirado há >24h
   - Calcula quantos dias de gap houve
   - Dispara `backfill_orders_after_reconnect` com delay de 60s

   b) **OAuth callback** (`auth/router.py`)
   - Quando usuário reconecta manualmente uma conta via OAuth
   - Sempre dispara backfill de 7 dias como padrão
   - Delay de 10s para permitir propagação do token

3. **Endpoint Manual** (`POST /api/v1/auth/ml/accounts/{account_id}/backfill-orders`)
   - Permite que usuário dispare backfill manualmente
   - Parâmetro: `days` (1-30, padrão 7)
   - Requer autenticação JWT

### Fluxo de Execução

```
Cenário 1: Reconexão Automática (token expirado e renovado via Celery)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Celery task `refresh_expired_tokens` roda a cada 4h
2. Detecta que token de conta X expirou há 5 dias
3. Renova o token com sucesso
4. Calcula gap_days = 5
5. Dispara `backfill_orders_after_reconnect(account_id, days=5)` com countdown=60s
6. Task aguarda 60s, depois busca pedidos dos últimos 5 dias no ML
7. Atualiza tabela orders com upsert

Cenário 2: Reconexão Manual (OAuth callback)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Usuário clica em "Conectar Conta ML" no frontend
2. Faz login no ML, autoriza acesso
3. ML redireciona para /api/v1/auth/ml/callback
4. Sistema salva novos tokens
5. Dispara `backfill_orders_after_reconnect(account_id, days=7)` com countdown=10s
6. Task aguarda 10s, depois busca pedidos dos últimos 7 dias no ML
7. Atualiza tabela orders com upsert

Cenário 3: Backfill Manual (usuário solicita)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Usuário chama: POST /api/v1/auth/ml/accounts/{account_id}/backfill-orders?days=14
2. Endpoint verifica que conta pertence ao usuário
3. Dispara `backfill_orders_after_reconnect(account_id, days=14)` com countdown=5s
4. Task aguarda 5s, depois busca pedidos dos últimos 14 dias no ML
5. Retorna task_id para user acompanhar

SyncLog
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Todas as execuções registram em tabela SyncLog:
- task_name: "backfill_orders_after_reconnect"
- ml_account_id: UUID da conta
- status: "success" ou "failed"
- items_processed: total de pedidos criados + atualizados
- items_failed: total de erros ao processar
- duration_ms: tempo total em ms
```

## Como Usar

### 1. Backfill Automático (sem ação do usuário)

O sistema faz automaticamente. Não há ação necessária:
- Token expira, fica desconectado 2+ dias
- Celery renova o token na próxima rodada de refresh (a cada 4h)
- Se gap > 24h, dispara backfill automaticamente
- Pedidos são recuperados em background

### 2. Backfill Manual via API

```bash
# Listar contas do usuário
curl -s https://msmpro-production.up.railway.app/api/v1/auth/ml/accounts \
  -H "Authorization: Bearer $TOKEN" | jq '.[] | {id, nickname}'

# Disparar backfill de 7 dias
curl -s -X POST https://msmpro-production.up.railway.app/api/v1/auth/ml/accounts/{account_id}/backfill-orders \
  -H "Authorization: Bearer $TOKEN"

# Disparar backfill de 14 dias
curl -s -X POST "https://msmpro-production.up.railway.app/api/v1/auth/ml/accounts/{account_id}/backfill-orders?days=14" \
  -H "Authorization: Bearer $TOKEN"
```

**Resposta de sucesso (202)**:
```json
{
  "status": "backfill_scheduled",
  "account_id": "12345678-1234-1234-1234-123456789012",
  "nickname": "MSM_PRIME",
  "days": 7,
  "task_id": "abc123def456",
  "message": "Backfill de 7 dias agendado. Verifique o status em alguns minutos."
}
```

### 3. Monitorar Execução

```bash
# Ver logs do Celery (se tiver Flower rodando)
# http://localhost:5555/

# Query tabela SyncLog para ver histórico
# SELECT * FROM sync_logs 
# WHERE task_name = 'backfill_orders_after_reconnect'
# ORDER BY started_at DESC
# LIMIT 10;
```

## Detalhes Técnicos

### Parâmetros da Task

```python
@celery_app.task(
    name="app.jobs.tasks.backfill_orders_after_reconnect",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def backfill_orders_after_reconnect(self, ml_account_id: str, days_to_backfill: int = 7):
    """
    Args:
        ml_account_id: UUID da conta ML (string)
        days_to_backfill: Número de dias (1-30)
    
    Returns:
        {
            "success": bool,
            "created": int,  # pedidos novos
            "updated": int,  # pedidos atualizados
            "errors": int,   # erros ao processar
            "data_from": "YYYY-MM-DD...",
            "data_to": "YYYY-MM-DD...",
            "days_backfilled": int,
        }
    """
```

### Limites

- **Máximo 30 dias**: Por segurança e limitações da API ML
- **Offset máximo**: API ML retorna até 50 pedidos por página, paginação automática
- **Retry**: 2 tentativas com backoff exponencial (120s, 240s)
- **Timeout**: Task roda em background, sem limite de duração

### Dados Buscados

Para cada pedido, o backfill busca:
- ID do pedido (ml_order_id)
- Data de criação (order_date)
- Anúncio (mlb_id) e quantidade
- Preço unitário e total
- Taxa de venda (sale_fee) e frete (shipping_cost)
- Status de pagamento e envio
- Data de aprovação de pagamento
- Data de entrega estimada/real

Usa **upsert**: se pedido já existe, apenas atualiza status (payment_status, shipping_status, delivery_date).

### Sincronização com API ML

Usa endpoint: `GET /orders/search?seller={seller_id}&order.date_created.from=...&order.date_created.to=...`

Com paginação:
- Limit: 50 pedidos por página
- Offset: incrementado a cada página
- Continua até totalAtingir total_available do ML

## Exemplos de Uso

### Exemplo 1: Reconexão após 3 dias offline

```
2026-04-01 10:00 - Token expira, conta fica offline
2026-04-04 06:30 - Celery task refresh_expired_tokens roda
              - Detecta: token expirado há 3 dias
              - Renova token com sucesso
              - Dispara backfill(account_id, days=3)
              - SyncLog: backfill_orders_after_reconnect, status=success, created=42, updated=5
              - Dashboard mostra 47 novos pedidos de 2026-04-01 a 2026-04-04
```

### Exemplo 2: Usuário reconecta manualmente

```
POST /api/v1/auth/ml/accounts/abc123/backfill-orders?days=7
Authorization: Bearer eyJhbG...

Response:
{
  "status": "backfill_scheduled",
  "account_id": "abc123",
  "nickname": "Loja2",
  "days": 7,
  "task_id": "task-xyz789",
  "message": "Backfill de 7 dias agendado..."
}

[após 5s + execução]

SELECT COUNT(*) FROM orders 
WHERE ml_account_id = 'abc123' 
  AND order_date >= NOW() - INTERVAL '7 days'
```

## Resiliência

### Tratamento de Erros

1. **Token inválido**: Task detecta, loga `MLClientError`, pula conta
2. **API rate-limit**: Implementado retry com backoff na `MLClient`
3. **Shipment indisponível**: Skipa custo de frete, usa 0 como fallback
4. **Listing não encontrado**: Salva order com `listing_id = NULL` (permitido)
5. **Parse error em data**: Usa `datetime.now()` como fallback

### Duplicação

- Usa `UNIQUE(ml_order_id)` na tabela orders
- Upsert: se order já existe, apenas atualiza status (não duplica)
- SyncLog registra "updated" separado de "created"

### Conflitos de Concorrência

- Redis lock: `refresh_expired_tokens` tem lock de 5min
- Backfill não tem lock (pode rodar em paralelo com sync_orders normal)
- Postgres: `UNIQUE ml_order_id` previne duplicação

## Monitoramento

### Métricas para Observar

```sql
-- Backfills executados nos últimos 7 dias
SELECT 
  DATE(started_at) as data,
  COUNT(*) as total,
  SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as sucesso,
  SUM(items_processed) as pedidos_recuperados
FROM sync_logs
WHERE task_name = 'backfill_orders_after_reconnect'
  AND started_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(started_at)
ORDER BY data DESC;

-- Contas que mais precisaram de backfill
SELECT 
  a.nickname,
  COUNT(DISTINCT l.id) as execucoes,
  SUM(l.items_processed) as total_pedidos
FROM sync_logs l
JOIN ml_accounts a ON l.ml_account_id = a.id
WHERE l.task_name = 'backfill_orders_after_reconnect'
  AND l.status = 'success'
  AND l.started_at >= NOW() - INTERVAL '30 days'
GROUP BY a.id, a.nickname
ORDER BY total_pedidos DESC;
```

### Alertas Recomendados

- **Taxa de sucesso < 80%**: Investigar erro na API ML ou tokens
- **Backfill > 4h**: Possível problema de API rate-limit ou muitos pedidos
- **Skipped por lock**: Normal, significa task já rodando, mas monitorar frequência

## Troubleshooting

| Problema | Causa | Solução |
|----------|-------|---------|
| Backfill não roda | Celery worker offline | Verificar `railway logs --service MSM_Pro` |
| SyncLog mostra "failed" | Token não mais válido | Usuário reconecta manualmente via UI |
| Pedidos antigos não aparecem | Backfill rodou antes de dados antigos serem salvos | Disparar backfill novamente manualmente |
| Mesmo pedido duplicado | Migration antiga sem constraint | UPDATE orders SET ... WHERE ml_order_id IN (...) |
| Frete sempre zero | API shipments/X falha | Normal, fallback funcionando, frete = 0 |

## Roadmap Futuro

1. **Backfill pré-configurado**: Usuário define % de dias a fazer backfill ao conectar conta (5d, 7d, 14d, 30d)
2. **Webhook**: Notificar user quando backfill terminar (POST para webhook_url)
3. **Resumo em Dashboard**: "X pedidos recuperados ontem via backfill"
4. **Priorização**: Backfill de contas com mais listings primeiro
5. **Compactação**: Deletar orders do ano passado para não sobrecarregar banco

## Referências

- Arquivo: `backend/app/jobs/tasks_orders.py` (_backfill_orders_after_reconnect_async)
- Arquivo: `backend/app/jobs/tasks.py` (task wrapper)
- Arquivo: `backend/app/jobs/tasks_tokens.py` (disparador automático)
- Arquivo: `backend/app/auth/router.py` (endpoint manual + OAuth callback)
- Task executada com: `celery_app.task(name="app.jobs.tasks.backfill_orders_after_reconnect")`
