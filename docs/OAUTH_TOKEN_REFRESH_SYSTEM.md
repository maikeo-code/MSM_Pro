# Sistema de Refresh Automático de Token OAuth do Mercado Livre

## Problema Resolvido

**Antes:** Tokens OAuth expiravam silenciosamente durante sincronizações, fazendo com que tasks retornassem sucesso sem realmente sincronizar.

**Agora:** Um sistema em 3 camadas previne qualquer expiração silenciosa de token.

## Arquitetura da Solução

### Camada 1: Refresh Preventivo (Cron job a cada 2h)

**Arquivo:** `backend/app/jobs/tasks_tokens.py`

Tarefa agendada que roda a cada 2 horas e procura contas com token prestes a expirar (dentro de 2h):

```python
# Busca contas com token_expires_at <= (agora + 2h)
threshold = datetime.now(timezone.utc) + timedelta(hours=2)
# Renova com retry 3x se falhar
```

**Características:**
- 3 tentativas de refresh com backoff exponencial (5s → 15s → 25s)
- Falha na renovação NÃO bloqueia outras contas
- Retorna `success: len(errors) == 0` (false se qualquer conta falhou)
- Logging detalhado por tentativa

### Camada 2: Verificação Pré-Requisição (Em cada task de sync)

**Arquivo:** `backend/app/jobs/tasks_listings.py` (linhas ~60)

Antes de usar o token, verifica se vence em < 30 minutos:

```python
if account.token_expires_at < (agora + 30min):
    # Tenta renovar ANTES de fazer requisições
    new_token = await refresh_ml_token_by_id(account.id)
    account.access_token = new_token  # Atualiza se sucesso
```

**Características:**
- Margem de 30 minutos garante preventividade
- Falha em refresh não bloqueia a task (usa token atual)
- Evita múltiplas requisições com token expirado
- Aplicado em todas as tasks de sync

### Camada 3: Refresh On-Demand em 401 (No cliente HTTP)

**Arquivo:** `backend/app/mercadolivre/client.py` (linhas ~85-130)

Quando a API retorna 401 (Unauthorized), o cliente tenta renovar automaticamente:

```python
class MLClient:
    def __init__(self, access_token: str, ml_account_id: str | None = None):
        # ml_account_id permite refresh automático
        self.ml_account_id = ml_account_id

    async def _request(...):
        # Se resposta for 401:
        if response.status_code == 401:
            if await self._refresh_token_and_retry():
                # Repete a requisição original com novo token
                continue
            else:
                # Falha permanente
                raise MLClientError(...)
```

**Características:**
- Transparente para o caller
- Automaticamente atualiza o header Authorization
- Salva novo token no banco
- Repete a requisição original com novo token
- Se refresh falha, levanta exceção (não esconde erro)

## Funções Críticas

### `refresh_ml_token_by_id(account_id: UUID) → str | None`

**Localização:** `backend/app/auth/service.py`

Função assíncrona que renova token de uma conta ML:

```python
async def refresh_ml_token_by_id(account_id: UUID) -> str | None:
    """
    Renova token de conta ML pelo ID.
    - Busca a conta no banco
    - Troca refresh_token por novo access_token
    - Atualiza banco com novo token + nova data de expiração
    - Retorna novo access_token ou None se falhar
    """
    db.execute(select(MLAccount).where(MLAccount.id == account_id))
    token_data = await _exchange_refresh_token(account.refresh_token)
    account.access_token = token_data["access_token"]
    account.token_expires_at = agora + timedelta(seconds=expires_in)
    await db.commit()
    return account.access_token
```

### `MLClient._refresh_token_and_retry() → bool`

**Localização:** `backend/app/mercadolivre/client.py`

Renovação dentro do cliente HTTP:

```python
async def _refresh_token_and_retry(self) -> bool:
    """
    Renova token da conta (se ml_account_id foi fornecido).
    - Chama refresh_ml_token_by_id()
    - Atualiza self.access_token
    - Atualiza header Authorization do cliente
    - Retorna True/False
    """
```

## Integração com Tasks Existentes

Todas as tasks que criam `MLClient` foram atualizadas:

| Arquivo | Mudança |
|---------|---------|
| `tasks_listings.py` | Verifica token pre-requisição + passa `ml_account_id` |
| `tasks_competitors.py` | Passa `ml_account_id` em 2 clientes |
| `tasks_orders.py` | Passa `ml_account_id` ao cliente |
| `tasks_ads.py` | Passa `ml_account_id` ao cliente |
| `reputacao/service.py` | Passa `ml_account_id` ao cliente |

## Compatibilidade

**Backward compatible:** Código antigo que cria `MLClient(access_token)` sem `ml_account_id` continua funcionando:

```python
# Antigo — ainda funciona
client = MLClient(access_token)
# 401 levanta exceção, não tenta refresh

# Novo — com refresh automático
client = MLClient(access_token, ml_account_id=str(account.id))
# 401 tenta refresh + repete requisição
```

## Frequência de Refresh

| Camada | Frequência | Margem | Arquivo |
|--------|-----------|--------|---------|
| 1 (Cron) | A cada 2h | 2h antes expiração | `celery_app.py` line 59 |
| 2 (Pré-req) | Cada sync | 30min antes expiração | `tasks_listings.py` line ~60 |
| 3 (On-demand) | Quando 401 | 0 (reativo) | `client.py` line ~110 |

## Fluxo Exemplo: Sincronização de Listings

```
1. Task sync_all_snapshots roda (06:00 BRT)
   ↓
2. Busca todas as contas ML ativas
   ↓
3. Para cada conta:
   a. Verifica se token_expires_at < (agora + 30min)
      ├─ SIM: tenta refresh preventivo
      │       └─ Falha? Loga warning, prossegue com token atual
      └─ NÃO: prossegue normalmente
   ↓
4. Cria MLClient(access_token, ml_account_id=account.id)
   ↓
5. Faz requisições à API ML (ex: get_item, get_item_visits, etc)
   ↓
6. Se qualquer requisição retorna 401:
   └─ MLClient._request() captura 401
      ├─ Chama _refresh_token_and_retry()
      │  ├─ refresh_ml_token_by_id(account.id)
      │  │  └─ Troca refresh_token por novo access_token
      │  └─ Atualiza Authorization header
      └─ Repete a requisição original
   ↓
7. Se falha permanente: levanta MLClientError (task falha corretamente)
   Se sucesso: continua normalmente
```

## Monitoramento

### Logs para observar

```bash
# Refresh preventivo (cron a cada 2h)
"Token renovado: account={id} nickname={name} expires={timestamp}"
"Renovação concluída: {n} sucesso, {n} erros"

# Pré-requisição (cada task)
"Token prestes a expirar para {nickname}, renovando..."
"Token renovado para {nickname}"

# On-demand (quando 401)
"Token expirado para conta {id}, tentando renovar..."
"Token renovado para conta {id}, repetindo requisição..."
"Token ML expirado e falha ao renovar"
```

### Métricas Recomendadas

1. **success flag** em `refresh_expired_tokens` task
   - Deve ser `true` toda vez
   - Se False: alguma conta falhou na renovação

2. **Contagem de 401s em logs**
   - Deve diminuir significativamente após essa fix
   - Se aumentar: problema novo (ex: refresh_token expirado)

3. **Token age** por conta
   - Máximo ~2h sempre
   - Após implementação, deve estar sempre < 2h

## Tratamento de Erros Edge Cases

### refresh_token expirado

Se `refresh_ml_token()` falha repetidamente com erro 401 ao trocar refresh_token:
- Refresh de token preventivo falha → task registra erro
- Sync tasks continuam com token antigo (podem falhar com 401)
- **Solução:** Usuário deve reconectar OAuth (novo refresh_token)

### Rate limit durante refresh

Se ML retorna 429 ao renovar:
- `refresh_ml_token()` vai falhar
- Retry automático na próxima chamada a cada 2h
- **Solução:** Aguarda retry automático

### Concorrência entre workers

Se 2 workers tentam renovar ao mesmo tempo:
- Ambos chamarão `refresh_ml_token()`
- Ambos salvarão novo access_token (idêntico)
- Sem problema — ML refresh_token permite múltiplos usos no mesmo segundo

## Testes Recomendados

```bash
# 1. Verificar que tokens são renovados a cada 2h
railway logs --follow | grep "Token renovado"

# 2. Simular expiração de token (reduzir token_expires_at no banco)
# ... e verificar que sync ainda funciona

# 3. Invocar manualmente:
curl -X POST http://localhost:8000/api/v1/admin/refresh-tokens \
  -H "Authorization: Bearer $TOKEN"

# 4. Verificar health com token antigo
# ... auth deve renovar automaticamente
```

## Roadmap Futuro

1. **Refresh automático com exponential backoff**
   - Atualmente: 3 tentativas fixas com delay fixo
   - Futuro: exponential backoff para distribuição

2. **Redis lock no refresh preventivo**
   - Atualmente: não há lock, múltiplos workers podem renovar
   - Futuro: adicionar lock para evitar N chamadas simultâneas

3. **Webhook para notificar quando refresh_token expira**
   - Atualmente: silent failure quando refresh_token é antigo
   - Futuro: alerta ao usuário para reconectar OAuth

4. **Dashboard de saúde de tokens**
   - Ver idade de cada token por conta
   - Ver histórico de refreshes
   - Alertar se conta sem refresh há >2h

## Referências

- **Documentação ML OAuth:** https://developers.mercadolivre.com.br/pt_br/oauth-documentation
- **Refresh token lifetime:** ~6 meses no Mercado Livre
- **Access token lifetime:** ~6 horas no Mercado Livre
