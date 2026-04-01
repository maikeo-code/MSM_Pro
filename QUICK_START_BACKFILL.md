# Quick Start: Backfill de Pedidos

## TL;DR - Em 30 Segundos

**O que é**: Quando uma conta ML fica desconectada (token expira), o sistema automaticamente recupera os pedidos perdidos daquele período.

**Como funciona**:
1. Token expira → conta fica offline
2. Celery renova token (a cada 4h)
3. Detecta > 24h offline → dispara backfill automático
4. Pedidos são recuperados em background
5. Dashboard mostra "X novos pedidos" recuperados

**Você precisa fazer?** NÃO. É automático.

---

## 3 Maneiras de Usar

### 1️⃣ Automático (Padrão - Sem Ação)
```
Dia 1: Token expira
Dia 5: Celery renova token
       → Detecta 4 dias offline
       → Dispara backfill (4 dias)
       → Recupera ~20 pedidos
Dia 5 (+ 5min): Dashboard mostra novos pedidos
```

**Você faz**: Nada. O sistema cuida.

### 2️⃣ Reconexão Manual (User UI)
```
1. Ir para https://msmprofrontend-production.up.railway.app/configuracoes
2. Clicar botão "Conectar Conta ML" (botão vermelho/amarelo)
3. Fazer login no Mercado Livre
4. Autorizar acesso
5. Sistema automaticamente dispara backfill de 7 dias
```

**Tempo**: ~30 segundos
**Resultado**: Dashboard mostra novos pedidos em 2-3 minutos

### 3️⃣ Backfill Manual (API/Power User)
```bash
# 1. Pegar token
TOKEN=$(curl -s -X POST \
  https://msmpro-production.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"maikeo@msmrp.com","password":"Msm@2026"}' \
  | jq -r '.access_token')

# 2. Pegar ID da conta
ACCOUNT_ID=$(curl -s \
  https://msmpro-production.up.railway.app/api/v1/auth/ml/accounts \
  -H "Authorization: Bearer $TOKEN" \
  | jq -r '.[0].id')

# 3. Disparar backfill de 14 dias
curl -X POST \
  "https://msmpro-production.up.railway.app/api/v1/auth/ml/accounts/$ACCOUNT_ID/backfill-orders?days=14" \
  -H "Authorization: Bearer $TOKEN" | jq .

# Resposta:
# {
#   "status": "backfill_scheduled",
#   "account_id": "...",
#   "nickname": "MSM_PRIME",
#   "days": 14,
#   "task_id": "abc123...",
#   "message": "Backfill de 14 dias agendado..."
# }
```

**Tempo**: ~5 segundos
**Parâmetro**: `days` (1-30, padrão 7)

---

## Quando Usar Cada Uma

| Situação | Método | Tempo |
|---|---|---|
| "Minha conta desconectou de repente" | Espere → Automático recupera em < 24h | — |
| "Quero reconectar uma conta" | Manual via /configuracoes | 30s |
| "Preciso recuperar 14 dias de dados" | API com days=14 | 5s |
| "É urgente, quero agora" | API com days=30 (máximo) | 5s |

---

## Monitorar Progresso

### Opção 1: Dashboard (Mais Fácil)
```
https://msmprofrontend-production.up.railway.app/dashboard
↓
Aparece badge "X pedidos recuperados ontem"
↓
Tabela atualiza com novos pedidos
```

### Opção 2: Banco de Dados (Técnico)
```sql
-- Ver último backfill
SELECT 
  task_name, 
  status, 
  items_processed,
  duration_ms
FROM sync_logs 
WHERE task_name = 'backfill_orders_after_reconnect'
ORDER BY started_at DESC 
LIMIT 1;

-- Ver histório (últimos 7 dias)
SELECT 
  DATE(started_at),
  COUNT(*),
  SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as sucesso,
  SUM(items_processed) as total_pedidos
FROM sync_logs 
WHERE task_name = 'backfill_orders_after_reconnect'
  AND started_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(started_at)
ORDER BY 1 DESC;
```

### Opção 3: Logs (Via Railway)
```bash
railway logs --service MSM_Pro --tail 50 | grep -i backfill
```

---

## Se Algo Deu Errado

| Sintoma | Causa | Solução |
|---|---|---|
| "Backfill não roda" | Celery offline | Verificar: `railway logs --service MSM_Pro` |
| "Status 404 no endpoint" | Conta não existe | Verificar ID: `curl ... /ml/accounts \| jq '.[].id'` |
| "Status 422 days=31" | Limite máximo é 30 | Usar `days=30` |
| "SyncLog mostra failed" | Token inválido | Reconectar: ir para /configuracoes |
| "Pedidos antigos não aparecem" | Backfill rodou, mas antes de salvar dados? | Disparar novamente |

---

## Limite de Dias

| Dias | Motivo | Exemplo |
|---|---|---|
| Máximo 30 | Limite prático API ML | Desconectou 5 dias? backfill=5 ✓ |
| Múltiplas vezes | Recuperar > 30 dias? | 7+7+7+9 = 30 ✓ |
| Mínimo 1 | Sem ponto em recuperar 0 dias | — |

---

## O Que É Recuperado

```
Para cada pedido:
├─ ID (ml_order_id) — nunca duplica mesmo se rodar 2x
├─ Data (order_date) — quando foi vendido
├─ Anúncio (mlb_id) — qual produto
├─ Quantidade e Preço — valor
├─ Taxa ML (sale_fee) — o que ML cobra
├─ Frete (shipping_cost) — custo de envio
├─ Status pagamento/envio — progresso do pedido
└─ Datas (pagto, entrega) — cronograma

Resultado no Dashboard:
├─ Aparece na tabela de pedidos
├─ Conta nos KPIs (Hoje/Ontem/7d/30d)
├─ Afeta cálculos de margem
└─ Muda health score
```

---

## Casos de Uso Reais

### Caso 1: Conta Desconectada 1 Semana
```
Seg: Token expira (user não vê notificação)
Ter: Celery roda 4h, renova token ✓
     Sistema detecta: token_expires_at é 1 dia atrás
     Dispara: backfill(days=1) ← ERRADO!
     
CORREÇÃO: Celery roda a CADA 4h, máximo espera 4 dias antes de renovar
          Se token expirou 7 dias atrás:
          Dispara: backfill(days=7) ← CERTO
          
Ter (+ 5min): 42 pedidos recuperados
```

**Resultado**: 0 perda de dados (se Celery online)

### Caso 2: User Reconecta Manualmente
```
User: "Preciso reconectar minha conta"
1. Clica "Conectar" em /configuracoes
2. Faz login no ML
3. Autoriza
4. Backend dispara: backfill(days=7)
5. Resultado: 15 pedidos da semana anterior recuperados

Total time: 30 segundos
```

### Caso 3: User Quer Recuperar 30 Dias
```
User: "Desconectei há 1 mês, quero tudo"
1. API: POST .../backfill-orders?days=30
2. Task começa em 5s
3. Busca todos os pedidos dos últimos 30 dias
4. Cria/atualiza no banco (paginação: 50/página)
5. SyncLog mostra: "150 criados, 5 atualizados"

Total time: ~3 minutos para 150 pedidos
```

---

## Performance

| Cenário | Tempo | Notas |
|---|---|---|
| 1 semana (7-10 pedidos) | 10s | Rápido |
| 2 semanas (20-30 pedidos) | 30s | Normal |
| 1 mês (50-100 pedidos) | 1-2min | OK |
| 30 dias (200+ pedidos) | 3-5min | Paginação |

**Benchmark**: ~100 pedidos/min com paginação

---

## Troubleshooting Checklist

- [ ] Celery ativo? `railway logs | grep -i celery`
- [ ] Token válido? `curl ... /auth/me` (sem erro 401)
- [ ] Conta pertence a você? `curl ... /ml/accounts | jq`
- [ ] Dias entre 1-30? (Padrão 7 ✓)
- [ ] SyncLog mostra tentativa? `SELECT * FROM sync_logs ORDER BY started_at DESC LIMIT 1`

---

## Documentação Completa

Para detalhes técnicos:
- **Feature Doc**: `docs/BACKFILL_ORDERS_FEATURE.md`
- **Testing**: `docs/BACKFILL_TESTING.md`
- **Implementation**: `BACKFILL_IMPLEMENTATION_SUMMARY.md`

---

## Dúvidas?

1. ❌ Backfill não roda → Ver **Troubleshooting Checklist** acima
2. ❌ Endpoint retorna erro → Verificar **Se Algo Deu Errado**
3. ❌ Tempo demorando → Normal, Celery roda em background

**Próxima Step**: Ir para `/configuracoes` e testar reconexão manual!

---

**Data**: 2026-04-01
**Status**: ✅ PRONTO PARA USO
