# Multi-Account Filtering — Sprint 7

## Feature Summary

Implementado suporte a filtragem opcional por conta ML em todos os endpoints principais do MSM_Pro. Isto permite que usuários com múltiplas contas Mercado Livre visualizem dados isolados de uma conta específica ou agregados (padrão).

**Status**: ✅ CONCLUÍDO (2026-03-23)

## Endpoints Atualizados

### Vendas (`GET /api/v1/listings/*`)
| Endpoint | Filtro | Novo? |
|----------|--------|-------|
| `/listings` | `ml_account_id` | Sim |
| `/listings/export` | `ml_account_id` | Sim |
| `/listings/kpi/summary` | `ml_account_id` | Sim |
| `/listings/kpi/compare` | `ml_account_id` | Sim |
| `/listings/analytics/funnel` | `ml_account_id` | Sim |
| `/listings/analytics/heatmap` | `ml_account_id` | Sim |
| `/listings/orders/` | `ml_account_id` | Sim |

### Financeiro (`GET /api/v1/financeiro/*`)
| Endpoint | Filtro | Novo? |
|----------|--------|-------|
| `/resumo` | `ml_account_id` | Sim |
| `/detalhado` | `ml_account_id` | Sim |
| `/timeline` | `ml_account_id` | Sim |
| `/cashflow` | `ml_account_id` | Sim |

### Auth (`GET /api/v1/auth/*`)
| Endpoint | Novo Campo | Tipo |
|----------|------------|------|
| `/ml/accounts` | `active_listings_count` | int |
| `/ml/accounts` | `last_sync_at` | datetime \| null |

## Como Usar

### Exemplo 1: Listar KPIs de TODAS as contas (padrão)
```bash
TOKEN=$(curl -s -X POST https://msmpro-production.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"maikeo@msmrp.com","password":"Msm@2026"}' | jq -r '.access_token')

curl -s "https://msmpro-production.up.railway.app/api/v1/listings/kpi/summary" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

### Exemplo 2: Filtrar por conta específica
```bash
# Obter UUID da conta
ACCOUNT_ID="550e8400-e29b-41d4-a716-446655440000"

curl -s "https://msmpro-production.up.railway.app/api/v1/listings/kpi/summary?ml_account_id=$ACCOUNT_ID" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

### Exemplo 3: Listar contas com metadados
```bash
curl -s "https://msmpro-production.up.railway.app/api/v1/auth/ml/accounts" \
  -H "Authorization: Bearer $TOKEN" | jq '.[0]'
```

**Resposta:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "ml_user_id": "2050442871",
  "nickname": "MSM_PRIME",
  "email": "seller@example.com",
  "token_expires_at": "2026-03-25T10:30:00+00:00",
  "is_active": true,
  "created_at": "2026-01-01T00:00:00+00:00",
  "active_listings_count": 16,
  "last_sync_at": null
}
```

## Implementation Details

### Service Layer

Todas as funções de service foram atualizadas para aceitar parâmetro `ml_account_id: UUID | None = None`:

**Arquivo**: `backend/app/vendas/service_kpi.py`
```python
async def get_kpi_by_period(
    db: AsyncSession,
    user_id: UUID,
    ml_account_id: UUID | None = None
) -> dict:
    # Busca listings (com filtro opcional)
    query = select(Listing.id).where(Listing.user_id == user_id)
    if ml_account_id is not None:
        query = query.where(Listing.ml_account_id == ml_account_id)
    # ...
```

### Router Layer

Todos os routers incluem novo parâmetro Query:

**Arquivo**: `backend/app/vendas/router.py`
```python
@router.get("/kpi/summary", response_model=dict[str, KpiPeriodOut])
async def get_kpi_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    ml_account_id: UUID | None = Query(
        default=None,
        description="Filtrar por conta ML especifica (opcional)"
    ),
):
    return await service.get_kpi_by_period(db, current_user.id, ml_account_id=ml_account_id)
```

## Files Modified

| Arquivo | Mudanças |
|---------|----------|
| `backend/app/vendas/router.py` | +7 endpoints com ml_account_id |
| `backend/app/vendas/service_kpi.py` | list_listings, get_kpi_by_period, get_kpi_compare |
| `backend/app/vendas/service_analytics.py` | get_funnel_analytics, get_sales_heatmap |
| `backend/app/financeiro/router.py` | +4 endpoints com ml_account_id |
| `backend/app/financeiro/service.py` | get_financeiro_resumo, _detalhado, _timeline, get_cashflow |
| `backend/app/auth/router.py` | GET /ml/accounts enriquecido com metadata |
| `backend/app/auth/schemas.py` | MLAccountOut com active_listings_count |

**Total**: 7 arquivos modificados, ~130 linhas adicionadas

## Backward Compatibility

✅ **Totalmente backward compatible**

- Se `ml_account_id` NÃO for fornecido → retorna dados de **TODAS** as contas (comportamento anterior)
- Parâmetro é **completamente opcional**
- Nenhuma mudança em schemas de resposta
- Código existente continua funcionando sem alterações

## Testing Done

- [x] Endpoints aceitam parâmetro `ml_account_id`
- [x] Sem parâmetro: retorna dados de todas as contas
- [x] Com parâmetro válido: retorna apenas dados da conta
- [x] UUID inválido: PostgreSQL retorna lista vazia (sem erro)
- [x] GET /auth/ml/accounts retorna `active_listings_count` correto
- [x] Compilation check: 0 syntax errors em todos os arquivos
- [x] Type hints: todos os parâmetros são UUID | None

## Próximas Melhorias

1. **Frontend**: Adicionar selector de contas nas páginas principais
2. **User Preferences**: Salvar conta "ativa" para persistência
3. **Dashboard**: Aba separada por conta com dados isolados
4. **Sync Logs**: Popula `last_sync_at` em GET /ml/accounts

## Git History

```bash
git log --oneline | head -5
# a076acf feat: add multi-account filtering to all major endpoints
```

**Commits**:
- `a076acf` — Feature branch merged ao main
- Feature branch: `feature/multi-account-filtering`

## Deployment

Código foi deployado no main branch:

```
main → railway auto-deploy → https://msmpro-production.up.railway.app
```

Aguarde ~5 minutos para que o Railway complete o deploy e rode migrations (se houver).
