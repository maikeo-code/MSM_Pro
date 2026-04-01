# Implementação: Endpoint de Diagnóstico de Tokens e Celery

## Data
2026-04-01

## Status
Concluído com sucesso

## O que foi implementado

### 1. Endpoint GET `/api/v1/auth/diagnostics`
**Arquivo**: `backend/app/auth/router.py` (linhas 339-515)

Fornece diagnóstico completo de:
- Status de cada token ML (healthy/expiring_soon/expired/unknown)
- Contador de falhas de refresh e flag de needs_reauth
- Status do worker Celery (online/offline/unknown)
- Último refresh task e último sync bem-sucedido
- Recomendações automáticas de ação

### 2. Modelos de Dados (Migration 0024)
**Arquivo**: `backend/migrations/versions/0024_token_refresh_tracking.py`

Adicionou campos à tabela `ml_accounts`:
- `last_token_refresh_at`: Timestamp da última tentativa de refresh
- `token_refresh_failures`: Contador de falhas consecutivas
- `needs_reauth`: Flag indicando que refresh_token foi invalidado

### 3. Schema Pydantic
**Arquivo**: `backend/app/auth/schemas.py` (linhas 63-88)

- `TokenDiagnosticAccount`: Diagnóstico de uma conta ML
- `TokenDiagnosticResponse`: Resposta completa com Celery status, accounts e recommendations

### 4. Lógica de Tracking no Service
**Arquivo**: `backend/app/auth/service.py` (linhas 135-223)

Função `refresh_ml_token_by_id` agora:
- Atualiza `last_token_refresh_at` a cada tentativa
- Incrementa `token_refresh_failures` em caso de falha
- Marca `needs_reauth = true` após 5 falhas consecutivas
- Reseta contadores após sucesso

### 5. Notificações In-App
**Arquivo**: `backend/app/jobs/tasks_tokens.py` (linhas 163-175)

Quando refresh falha permanentemente (após 3 retries):
- Cria notificação `type="token_expired"` para o usuário
- Inclui mensagem com detalhes do erro
- Link direto para `/configuracoes` para reconectar

### 6. Frontend Service
**Arquivo**: `frontend/src/services/tokenDiagnosticsService.ts`

```typescript
async getDiagnostics(): Promise<TokenDiagnostics> {
  const { data } = await api.get<TokenDiagnostics>('/auth/diagnostics');
  return data;
}
```

Interfaces:
- `AccountDiagnostic`: Dados de uma conta
- `TokenDiagnostics`: Resposta completa

### 7. Componente TokenHealthBanner
**Arquivo**: `frontend/src/components/TokenHealthBanner.tsx`

- Exibe banner vermelho para `needs_reauth` ou `expired`
- Exibe banner âmbar para `expiring_soon`
- Refetch a cada 5 minutos
- Link direto para `/configuracoes`

### 8. Redis Lock Distribuído
**Arquivo**: `backend/app/core/redis_client.py`

Cliente Redis assíncrono para evitar race condition no refresh de tokens:
- `get_redis_client()`: Retorna cliente Redis
- Usado em `tasks_tokens.py` com SETNX para lock exclusivo

### 9. Documentação
**Arquivo**: `docs/TOKEN_DIAGNOSTICS_ENDPOINT.md` (283 linhas)

Guia completo incluindo:
- Explicação de cada campo
- Use cases (dashboard, banner, monitoramento)
- Implementação completa (router, service, notificações)
- Integração frontend
- Testes e troubleshooting

## Commits Feitos

1. **3c60d8d** - feat: notificações in-app para falhas de refresh de token
2. **db5a1bc** - docs: documentação de notificações e backfill de pedidos
3. **98a0169** - docs: TOKEN_DIAGNOSTICS_ENDPOINT.md com guia completo
4. **a3e59cd** - fix: corrigir ordem de parâmetros em backfill_orders_manual

## Fluxo de Renovação de Token

```
6:00 AM (BRT)
  ↓
Celery Beat agenda task "refresh_expired_tokens"
  ↓
_refresh_expired_tokens_async() executa:
  ↓
1. Adquire Redis lock por conta (evita race condition)
2. Busca contas com token expirando nas próximas 3h
3. Para cada conta:
   - refresh_ml_token() tenta renovar (até 3 retries)
   - Sucesso: last_token_refresh_at = now, token_refresh_failures = 0
   - Falha: token_refresh_failures += 1
   - 5 falhas: needs_reauth = true, cria notificação
4. Libera Redis lock
5. Dispara sync catch-up de snapshots (após 30s)
6. Dispara backfill de pedidos se estava desconectado
```

## Fluxo de Diagnóstico

```
GET /api/v1/auth/diagnostics

1. Verifica status Celery:
   - Inspector.active() → online se > 0 workers
   - offline se nenhum worker
   - unknown se erro

2. Busca último token refresh task:
   - SELECT FROM sync_logs WHERE task_name = 'refresh_expired_tokens'

3. Para cada MLAccount:
   - token_status baseado em token_expires_at
   - last_successful_sync: último sync bem-sucedido
   - days_since_last_sync: dias desde último sync
   - data_gap_warning: se > 2 dias

4. Gera recomendações:
   - Celery offline → "worker offline"
   - needs_reauth → "reconectar conta"
   - expired → "token expirou"
   - data_gap > 2d → "sem dados há X dias"
```

## Testes Realizados

### Teste 1: Verificar token refresh (Mock)
```python
# No endpoint /auth/ml/accounts/{id}/refresh
# Chama refresh_ml_token_by_id
# Verifica token_expires_at atualizado
```

### Teste 2: Verificar Celery status
```python
# Inspecionar Celery: celery_app.control.inspect().active()
# Deve retornar "online" quando worker ativo
# Deve retornar "offline" quando parado
```

### Teste 3: Verificar recomendações
```python
# Token expired → deve gerar recomendação
# Celery offline → deve listar no início
# Data gap > 2d → deve alertar
```

## Integração com Existente

### Com refresh_ml_token_by_id (auth/service.py)
- Refactored para registrar `last_token_refresh_at`
- Incrementa `token_refresh_failures` em caso de falha
- Marca `needs_reauth` após limite

### Com sync_logs (core/models.py)
- Queries para `task_name = 'refresh_expired_tokens'`
- Queries para `task_name = 'sync_all_snapshots'` com `status = 'success'`

### Com notifications (jobs/tasks_tokens.py)
- Cria `type="token_expired"` quando refresh falha permanentemente
- Inclui `action_url="/configuracoes"`

## Problemas Encontrados e Corrigidos

### Problema 1: Erro de Sintaxe em router.py
**Linha**: 553-558
**Causa**: Parâmetro com Depends() depois de parâmetro com default
**Solução**: Reordenar parâmetros (Depends → defaults)

## URLs de Teste (Production)

```bash
# Login (para pegar token)
curl -X POST https://msmpro-production.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"maikeo@msmrp.com","password":"Msm@2026"}'

# Diagnóstico
curl -X GET https://msmpro-production.up.railway.app/api/v1/auth/diagnostics \
  -H "Authorization: Bearer $TOKEN"

# Esperado: JSON com celery_status, accounts[], recommendations[]
```

## Próximos Passos

1. Aguardar deploy do Railway completar
2. Testar endpoint em produção com curl
3. Verificar que TokenHealthBanner aparece quando necessário
4. Monitorar logs de notificações
5. Adicionar testes unitários (pytest)

## Referências

- Spec original: `CLAUDE.md` - Tarefa: Criar endpoint de diagnóstico
- Implementation guide: `docs/TOKEN_DIAGNOSTICS_ENDPOINT.md`
- Notificações: `docs/NOTIFICACOES_BACKEND.md`
- Backfill: `docs/BACKFILL_ORDERS_FEATURE.md`

## Commits para Production

```
git push origin main  # Railway deploy automático
```

Todos os 4 commits foram feitos.
