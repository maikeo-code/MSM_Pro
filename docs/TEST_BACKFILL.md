# Teste do Mecanismo de Backfill

## Pré-requisitos
- Token JWT válido da conta de teste
- Ao menos um anúncio ativo na conta ML
- Railway backend disponível

## Teste 1: Verificar Cobertura Padrão (30 dias)

```bash
# 1. Obter token
TOKEN=$(curl -s -X POST https://msmpro-production.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "maikeo@msmrp.com",
    "password": "Msm@2026"
  }' | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

# 2. Chamar endpoint de coverage
curl -s "https://msmpro-production.up.railway.app/api/v1/listings/coverage" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | python3 -m json.tool
```

**Resultado esperado:**
```json
{
  "period_days": 30,
  "overall_coverage_pct": 95.5,
  "listings": [
    {
      "mlb_id": "MLB-123456789",
      "title": "Produto Teste",
      "days_with_data": 28,
      "expected_days": 30,
      "coverage_pct": 93.3
    }
  ]
}
```

**Validação:**
- [x] Status HTTP 200
- [x] `period_days` = 30
- [x] `overall_coverage_pct` entre 0-100
- [x] Lista de anúncios com campos obrigatórios
- [x] `coverage_pct` calculado corretamente (dias_com_dados/dias_esperados * 100)

## Teste 2: Filtro de Período (60 dias)

```bash
curl -s "https://msmpro-production.up.railway.app/api/v1/listings/coverage?days=60" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Validação:**
- [x] Status HTTP 200
- [x] `period_days` = 60
- [x] `overall_coverage_pct` possível ser menor (mais dias para cobrir)

## Teste 3: Filtro por Conta ML

```bash
# Obter UUID da conta ML (a partir de /api/v1/auth/ml/accounts)
ACCOUNT_ID=$(curl -s "https://msmpro-production.up.railway.app/api/v1/auth/ml/accounts" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['id'])")

# Chamar coverage com filtro
curl -s "https://msmpro-production.up.railway.app/api/v1/listings/coverage?ml_account_id=$ACCOUNT_ID" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Validação:**
- [x] Status HTTP 200
- [x] Retorna apenas anúncios da conta especificada
- [x] `overall_coverage_pct` pode ser diferente do teste 1 (filtrado)

## Teste 4: Parâmetros Inválidos

### 4a. Period muito pequeno (< 1)
```bash
curl -s "https://msmpro-production.up.railway.app/api/v1/listings/coverage?days=0" \
  -H "Authorization: Bearer $TOKEN"
```

**Esperado:** HTTP 422 (Validation Error)

### 4b. Period muito grande (> 90)
```bash
curl -s "https://msmpro-production.up.railway.app/api/v1/listings/coverage?days=91" \
  -H "Authorization: Bearer $TOKEN"
```

**Esperado:** HTTP 422 (Validation Error)

### 4c. ML Account ID inválido
```bash
curl -s "https://msmpro-production.up.railway.app/api/v1/listings/coverage?ml_account_id=invalid-uuid" \
  -H "Authorization: Bearer $TOKEN"
```

**Esperado:** HTTP 200 com lista vazia `"listings": []`

## Teste 5: Sem Autenticação

```bash
curl -s "https://msmpro-production.up.railway.app/api/v1/listings/coverage"
```

**Esperado:** HTTP 401 (Unauthorized)

## Teste 6: Simular Trigger de Sync (Manual)

### Passo 1: Verificar coverage antes
```bash
curl -s "https://msmpro-production.up.railway.app/api/v1/listings/coverage?days=7" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Anotar `overall_coverage_pct`.

### Passo 2: Disparar refresh de tokens manualmente (via Railway)

No painel Railway:
1. Acessar serviço "MSM_Pro"
2. Executar command:
   ```bash
   python -c "
   import asyncio
   from app.jobs.tasks_tokens import _refresh_expired_tokens_async
   result = asyncio.run(_refresh_expired_tokens_async())
   print(f'Refreshed: {result[\"refreshed\"]}, Errors: {result[\"errors\"]}')
   "
   ```

### Passo 3: Aguardar 90 segundos

O sync é disparado com 30s de delay após a renovação bem-sucedida.

### Passo 4: Verificar coverage novamente
```bash
curl -s "https://msmpro-production.up.railway.app/api/v1/listings/coverage?days=7" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Esperado:** `overall_coverage_pct` maior ou igual (dados recuperados do backfill)

## Teste 7: Verificar Logs (Flower Dashboard)

1. Acessar Railway → MSM_Pro → Logs
2. Procurar por:
   - "Disparando sync catch-up"
   - "sync_all_snapshots" (task acionada)

**Log esperado:**
```
[INFO] Disparando sync catch-up para 1 contas renovadas. Delay: 30s
[INFO] [tasks.py] sync_all_snapshots iniciado
[INFO] [tasks.py] Sincronizados 16 anúncios com sucesso
```

## Checklist de Validação

- [ ] Teste 1: Coverage padrão funciona
- [ ] Teste 2: Filtro de dias funciona
- [ ] Teste 3: Filtro de conta ML funciona
- [ ] Teste 4a: Validação de parâmetros (dias < 1) funciona
- [ ] Teste 4b: Validação de parâmetros (dias > 90) funciona
- [ ] Teste 4c: Conta ML inválida retorna lista vazia
- [ ] Teste 5: Autenticação é obrigatória
- [ ] Teste 6: Sync é disparado automaticamente após renovação
- [ ] Teste 7: Logs confirmam o trigger

## Possíveis Problemas e Soluções

### Problema: Sempre 100% de coverage
**Causa:** Sync está funcionando muito bem, nenhum gap detectado.
**Solução:** Aguarde alguns dias sem sincronização para ver gaps.

### Problema: Coverage 0%
**Causa:** Nenhum snapshot capturado no período.
**Solução:** Execute sync manualmente: `POST /api/v1/listings/sync`

### Problema: HTTP 422 na query
**Causa:** SQLAlchemy error na query SQL.
**Solução:** Verificar logs do Railway, possível issue com cast de data.

### Problema: Timeout ao chamar endpoint
**Causa:** Query muito lenta (muitos anúncios, muitos snapshots).
**Solução:** Usar filtro `ml_account_id` para reduzir escopo.

## Dados de Teste Sugeridos

Se precisar criar dados de teste para verificar gaps:

```python
# No console do Railway ou via script
from datetime import datetime, timedelta, timezone
from app.vendas.models import ListingSnapshot
from app.core.database import AsyncSessionLocal
import asyncio

async def create_test_snapshots():
    async with AsyncSessionLocal() as db:
        # Criar snapshots com gaps (ex: faltam dados de 2 dias)
        base_date = datetime.now(timezone.utc) - timedelta(days=30)
        for i in range(30):
            if i not in [5, 6]:  # Skip dias 5 e 6 para criar gap
                snapshot = ListingSnapshot(
                    listing_id="<uuid-do-listing>",
                    captured_at=base_date + timedelta(days=i),
                    price=99.90,
                    visits=10,
                    sales_today=2,
                    questions=0,
                    stock=100,
                    conversion_rate=0.2
                )
                db.add(snapshot)
        await db.commit()

# Depois verificar:
# GET /listings/coverage → deve mostrar 28/30 = 93.3%
```

## Próximas Validações

- [ ] Testar em staging antes de PR
- [ ] Verificar API docs atualizados em `/docs`
- [ ] Confirmar que GET /listings/coverage aparece em `/openapi.json`
- [ ] Testar multi-conta com 2+ contas ML
