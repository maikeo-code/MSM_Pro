# Mecanismo de Backfill com Sync Automático após Renovação de Token ML

## Objetivo
Quando o token OAuth do Mercado Livre expira e é renovado, disparar automaticamente uma sincronização de dados (sync catch-up) para recuperar informações perdidas dos dias sem conexão.

## Implementação

### 1. Trigger de Sync Automático (tasks_tokens.py)

Após renovar tokens com sucesso, a task `_refresh_expired_tokens_async()` dispara um sync imediato:

```python
# Dispara sync catch-up imediato para contas com token renovado
if refreshed:
    from app.jobs.tasks import sync_all_snapshots
    logger.info(
        "Disparando sync catch-up para %d contas renovadas. Delay: 30s",
        len(refreshed),
    )
    # Agenda sync com delay de 30s para permitir propagação do token
    sync_all_snapshots.apply_async(countdown=30)
```

**Detalhes:**
- Localização: `/backend/app/jobs/tasks_tokens.py` (linhas 100-113)
- Trigger: após `await db.commit()` confirmar a renovação
- Delay: 30 segundos (para garantir propagação do token renovado)
- Task disparada: `sync_all_snapshots` (Celery task existente)

### 2. Endpoint de Cobertura de Dados (router.py)

Novo endpoint para verificar se há gaps de dados:

**Endpoint:** `GET /api/v1/listings/coverage`

**Parâmetros:**
- `days` (query, padrão 30): número de dias a verificar (1-90)
- `ml_account_id` (query, opcional): filtrar por conta ML específica

**Resposta:**
```json
{
  "period_days": 30,
  "overall_coverage_pct": 95.5,
  "listings": [
    {
      "mlb_id": "MLB-123456789",
      "title": "Produto A",
      "days_with_data": 28,
      "expected_days": 30,
      "coverage_pct": 93.3
    },
    {
      "mlb_id": "MLB-987654321",
      "title": "Produto B",
      "days_with_data": 30,
      "expected_days": 30,
      "coverage_pct": 100.0
    }
  ]
}
```

**Localização:** `/backend/app/vendas/router.py` (linhas 268-362)

### 3. Schema Pydantic (schemas.py)

Dois novos schemas para validação:

```python
class DataCoverageItemOut(BaseModel):
    """Item de cobertura para um anúncio específico."""
    mlb_id: str
    title: str
    days_with_data: int
    expected_days: int
    coverage_pct: float

class DataCoverageOut(BaseModel):
    """Resposta de cobertura de dados dos últimos N dias."""
    period_days: int
    overall_coverage_pct: float
    listings: list[DataCoverageItemOut]
```

**Localização:** `/backend/app/vendas/schemas.py` (linhas 508-525)

## Fluxo Completo

```
Token ML expira
    |
    v
[Celery Task] refresh_expired_tokens (a cada 4h)
    |
    +-> Tenta renovar cada token expirado
    |
    +-> Sucesso? Dispara sync_all_snapshots (countdown=30s)
    |
    v
[30s depois]
    |
    v
[Celery Task] sync_all_snapshots (task existente)
    |
    +-> Importa snapshots de TODOS os anúncios
    +-> Recupera dados dos dias sem conexão
    +-> Atualiza banco com histórico completo
```

## Teste Manual

### 1. Verificar cobertura atual
```bash
curl -s https://msmpro-production.up.railway.app/api/v1/listings/coverage \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | python3 -m json.tool
```

### 2. Verificar cobertura dos últimos 60 dias
```bash
curl -s "https://msmpro-production.up.railway.app/api/v1/listings/coverage?days=60" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### 3. Verificar cobertura de uma conta ML específica
```bash
curl -s "https://msmpro-production.up.railway.app/api/v1/listings/coverage?ml_account_id=<uuid>" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

## Logs da Renovação

Quando tokens são renovados com sucesso, você verá no Flower/logs:

```
Renovação concluída: 2 sucesso, 0 erros
Disparando sync catch-up para 2 contas renovadas. Delay: 30s
[30s depois...]
sync_all_snapshots iniciado (triggered by token refresh)
```

## Requisitos Cumpridos

- [x] Modificar `tasks_tokens.py` para disparar sync após renovação
- [x] Adicionar endpoint `GET /listings/coverage` para verificar gaps
- [x] Retorna cobertura por anúncio (dias com dados vs esperado)
- [x] Suporta filtro de período (1-90 dias)
- [x] Suporta filtro opcional de conta ML
- [x] Schemas Pydantic corretamente tipados
- [x] Query SQLAlchemy otimizada com DISTINCT para contar dias únicos
- [x] Ordenação por coverage (menor primeiro para destacar problemas)

## Arquivos Modificados

1. **backend/app/jobs/tasks_tokens.py**
   - Adicionado trigger de sync após renovação bem-sucedida
   - Linha 100-113: código de disparo

2. **backend/app/vendas/router.py**
   - Adicionado import do schema `DataCoverageOut`
   - Adicionado endpoint `GET /listings/coverage`
   - Linha 268-362: implementação completa

3. **backend/app/vendas/schemas.py**
   - Adicionados schemas `DataCoverageItemOut` e `DataCoverageOut`
   - Linha 508-525: definições de schema

## Deploy

Para aplicar em produção:

```bash
cd msm_pro
git add backend/app/jobs/tasks_tokens.py backend/app/vendas/router.py backend/app/vendas/schemas.py
git commit -m "feat: adicionar mecanismo de backfill com sync automático após renovação de token ML"
git push origin main
# Railway fará auto-deploy automaticamente
```

## Monitoramento

A saúde do backfill pode ser verificada em:

1. **Logs do Celery** (Flower): `https://railway.app` → logs de tasks
2. **Endpoint de coverage**: `/api/v1/listings/coverage` mostra estado atual
3. **Alertas**: Se coverage_pct < 80% para algum anúncio, há possivelmente um problema

## Notas

- O sync usa a task existente `sync_all_snapshots`, garantindo consistência
- Delay de 30s evita race conditions com propagação de token
- Query usa `COUNT(DISTINCT captured_at::date)` para contar dias únicos
- Compatível com multi-conta ML
- Zero breaking changes em APIs existentes
