# Endpoint de Diagnóstico de Tokens e Celery

## Overview
Endpoint GET `/api/v1/auth/diagnostics` fornece visibilidade completa sobre a saúde dos tokens OAuth do Mercado Livre e o status do worker Celery.

**Endpoint:** `GET /api/v1/auth/diagnostics`
**Autenticação:** Requer JWT válido
**Rate limit:** 5 requests/minute (auth limiter)

## Resposta

```json
{
  "celery_status": "online|offline|unknown",
  "last_token_refresh_task": "2026-04-01T10:30:00Z",
  "accounts": [
    {
      "id": "uuid",
      "nickname": "MSM_PRIME",
      "token_status": "healthy|expiring_soon|expired|unknown",
      "token_expires_at": "2026-04-01T16:00:00Z",
      "remaining_hours": 5.5,
      "has_refresh_token": true,
      "last_successful_sync": "2026-04-01T09:00:00Z",
      "last_refresh_attempt": "2026-04-01T10:30:00Z",
      "last_refresh_success": true,
      "days_since_last_sync": 0,
      "data_gap_warning": null,
      "refresh_failure_count": 0,
      "needs_reauth": false
    }
  ],
  "recommendations": [
    "Celery worker offline — sincronizações não estão acontecendo",
    "Conta 'Backup' token expira em menos de 1h — será renovado automaticamente"
  ]
}
```

## Campos Explicados

### celery_status
- `online`: Worker Celery está ativo e processando tasks
- `offline`: Nenhum worker conectado ao broker
- `unknown`: Erro ao consultar status (verificar logs)

### last_token_refresh_task
Timestamp do último refresh task executado. Usado para diagnosticar se `refresh_expired_tokens` está sendo agendado corretamente.

### accounts[].token_status
- `healthy`: Token ainda válido por > 1 hora
- `expiring_soon`: Token válido por 0-1 hora (será renovado automaticamente)
- `expired`: Token já expirou (necessita reauth)
- `unknown`: Token expire time não foi setado

### accounts[].remaining_hours
Horas restantes até expiração do token. `None` se status é `unknown`.

### accounts[].last_successful_sync
Timestamp do último `sync_all_snapshots` bem-sucedido. Permite detectar data gaps quando falta sincronização.

### accounts[].last_refresh_attempt
Timestamp da última tentativa de refresh (bem-sucedida ou falhada).

### accounts[].last_refresh_success
`true` se última tentativa foi bem-sucedida (token_refresh_failures = 0).
`false` se última tentativa falhou (token_refresh_failures > 0).

### accounts[].days_since_last_sync
Dias decorridos desde o último sync bem-sucedido. Alerta se > 2 dias.

### accounts[].refresh_failure_count
Contador de falhas consecutivas de refresh. Se ≥ 5, `needs_reauth` é marcado `true`.

### accounts[].needs_reauth
`true` quando refresh_token foi invalidado após ≥ 5 falhas. Usuário deve reconectar a conta no OAuth.

### recommendations[]
Array de strings com ações sugeridas. Inclui:
- Status do Celery se offline/unknown
- Contas com needs_reauth marcado
- Tokens expired ou expiring_soon
- Data gaps > 2 dias

## Use Cases

### 1. Dashboard de Saúde do Sistema
Exibir no painel administrativo:
```javascript
const diagnostics = await tokenDiagnosticsService.getDiagnostics();

if (diagnostics.celery_status === 'offline') {
  showAlert('Celery worker offline - sincronizações paradas');
}

diagnostics.accounts.forEach(acc => {
  if (acc.needs_reauth) {
    showAlert(`Conta "${acc.nickname}" precisa reconectar`);
  }
  if (acc.days_since_last_sync > 2) {
    showWarning(`Sem dados de "${acc.nickname}" há ${acc.days_since_last_sync} dias`);
  }
});
```

### 2. Componente TokenHealthBanner
Exibir banner ao usuário mostrando contas problemáticas:
```typescript
// frontend/src/components/TokenHealthBanner.tsx
const problematicAccounts = diagnostics.accounts.filter(
  acc => acc.needs_reauth || acc.token_status === 'expired'
);
```

### 3. Script de Monitoramento
Executar via cron a cada 5 minutos:
```bash
curl -s https://app.example.com/api/v1/auth/diagnostics \
  -H "Authorization: Bearer $ADMIN_TOKEN" | \
  jq -r '.recommendations[]' | \
  xargs -I {} send_slack_message "{}"
```

### 4. Verificar Causa de Falta de Dados
Quando usuário relata "vendas não aparecem":
1. Verificar `last_successful_sync` — se > 2 dias, há data gap
2. Verificar `token_status` — se `expired`, token expirou
3. Verificar `celery_status` — se `offline`, nada sincronizou
4. Ler `data_gap_warning` para mensagem pronta

## Tabelas Usadas

### ml_accounts
- `id`: UUID da conta
- `token_expires_at`: Quando token expira
- `last_token_refresh_at`: Quando último refresh foi tentado
- `token_refresh_failures`: Contador de falhas
- `needs_reauth`: Flag se precisa reconectar

### sync_logs
- Queries `task_name = 'refresh_expired_tokens'` para `last_token_refresh_task`
- Queries `task_name = 'sync_all_snapshots' AND status = 'success'` para `last_successful_sync`

## Implementação Backend

### router.py (`/api/v1/auth/diagnostics`)
```python
@router.get("/diagnostics", response_model=TokenDiagnosticResponse)
async def ml_diagnostics(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # 1. Verifica status Celery via celery_app.control.inspect()
    # 2. Busca último refresh task em sync_logs
    # 3. Para cada MLAccount:
    #    - Calcula token_status baseado em token_expires_at
    #    - Busca último sync bem-sucedido em sync_logs
    #    - Calcula dias desde sync
    #    - Gera recomendações
    return TokenDiagnosticResponse(...)
```

### service.py
Lógica de refresh com tracking em `refresh_ml_token_by_id`:
```python
# Ao sucesso:
account.last_token_refresh_at = datetime.now(timezone.utc)
account.token_refresh_failures = 0
account.needs_reauth = False

# Ao falha:
account.token_refresh_failures += 1
account.last_token_refresh_at = datetime.now(timezone.utc)
if account.token_refresh_failures >= 5:
    account.needs_reauth = True
```

### Notificações (tasks_tokens.py)
Quando refresh falha permanentemente (após 3 retries):
```python
await create_notification(
    db,
    user_id=account.user_id,
    type="token_expired",
    title=f"Conta '{account.nickname}' desconectada",
    message=f"Não foi possível renovar token após {max_retries} tentativas...",
    action_url="/configuracoes",
)
```

## Frontend Integration

### tokenDiagnosticsService.ts
```typescript
async getDiagnostics(): Promise<TokenDiagnostics> {
  const { data } = await api.get<TokenDiagnostics>('/auth/diagnostics');
  return data;
}
```

### TokenHealthBanner.tsx
```typescript
const { data: diagnostics } = useQuery({
  queryKey: ['token-diagnostics'],
  queryFn: () => tokenDiagnosticsService.getDiagnostics(),
  refetchInterval: 300000, // 5 minutos
});
```

## Testes

### Teste 1: Verificar endpoint existe
```bash
curl -X GET https://api.example.com/api/v1/auth/diagnostics \
  -H "Authorization: Bearer $TOKEN"
```

### Teste 2: Verificar campos obrigatórios
```python
def test_diagnostics_response_schema():
    response = client.get(
        "/api/v1/auth/diagnostics",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    
    assert "celery_status" in data
    assert "accounts" in data
    assert "recommendations" in data
    
    for account in data["accounts"]:
        assert "id" in account
        assert "token_status" in account
        assert "token_expires_at" in account
```

### Teste 3: Verificar recomendações corretas
```python
def test_recommendations_generated():
    # Simular conta com token expirado
    account.token_expires_at = datetime.now(utc) - timedelta(hours=1)
    
    response = client.get(
        "/api/v1/auth/diagnostics",
        headers={"Authorization": f"Bearer {token}"}
    )
    data = response.json()
    
    # Deve gerar recomendação para token expirado
    assert any("expirou" in r for r in data["recommendations"])
```

## Troubleshooting

### "celery_status": "offline"
Não há worker Celery ativo. Verificar:
1. `docker ps | grep celery` (local) ou Railway logs (produção)
2. Redis está ativo? `redis-cli ping`
3. Variáveis de ambiente CELERY_BROKER_URL corretas?

### "token_status": "expired" mas sync funciona
Possível que:
1. Token foi renovado mas `token_expires_at` não foi atualizado no banco
2. Timezone desincronizado entre servidor e Railway

### Todas as contas "needs_reauth": true
Possível que:
1. Refresh task está falhando (checar logs)
2. Refresh_token do ML foi invalidado (usuário desconectou no ML)

## Performance

- Query `sync_logs` com index em `(task_name, ml_account_id, finished_at DESC)` é O(1)
- Celery inspector é em-memória, < 10ms
- Total: < 100ms para usuário com 5+ contas

## Versão

- Implementado: Sprint 10 (2026-04-01)
- Campos adicionados em migration 0024
- Endpoint: GET `/api/v1/auth/diagnostics`
- Response schema: TokenDiagnosticResponse
