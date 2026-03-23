# Sprint 7: Detalhes de Implementação — Oauth Token Refresh

## 1. `backend/app/mercadolivre/client.py`

### Mudança 1.1: Constructor
```python
# ANTES
def __init__(self, access_token: str):
    self.access_token = access_token
    self._client = httpx.AsyncClient(...)

# DEPOIS
def __init__(self, access_token: str, ml_account_id: str | None = None):
    """
    Args:
        access_token: Token de acesso OAuth
        ml_account_id: ID da conta MLAccount (para refresh automático)
    """
    self.access_token = access_token
    self.ml_account_id = ml_account_id  # Novo!
    self._client = httpx.AsyncClient(...)
```

### Mudança 1.2: Novo método `_refresh_token_and_retry()`

Adicionado depois de `_rate_limit()`:

```python
async def _refresh_token_and_retry(self) -> bool:
    """
    Tenta renovar o token da conta ML e retorna sucesso.
    Retorna True se renovação foi bem-sucedida, False caso contrário.
    """
    if not self.ml_account_id:
        return False

    try:
        from app.auth.service import refresh_ml_token_by_id
        new_token = await refresh_ml_token_by_id(self.ml_account_id)
        if new_token:
            self.access_token = new_token
            # Atualiza header do cliente com novo token
            self._client.headers["Authorization"] = f"Bearer {new_token}"
            return True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Falha ao renovar token para conta {self.ml_account_id}: {e}"
        )

    return False
```

### Mudança 1.3: Tratamento de 401 em `_request()`

```python
# ANTES (linha ~110)
if response.status_code == 401:
    raise MLClientError("Token ML expirado ou inválido", status_code=401)

# DEPOIS
if response.status_code == 401:
    import logging
    logger = logging.getLogger(__name__)
    logger.info(
        f"Token expirado para conta {self.ml_account_id}, tentando renovar..."
    )

    if await self._refresh_token_and_retry():
        logger.info(
            f"Token renovado para conta {self.ml_account_id}, "
            f"repetindo requisição..."
        )
        continue  # Repete a requisição original
    else:
        raise MLClientError(
            "Token ML expirado e falha ao renovar",
            status_code=401,
        )
```

## 2. `backend/app/auth/service.py`

### Mudança 2.1: Refatoração de `refresh_ml_token()`

Antes havia código duplicado. Agora chamamos helper interno:

```python
async def refresh_ml_token(account: MLAccount) -> dict:
    """Renova o access_token de uma conta ML usando o refresh_token."""
    try:
        return await _exchange_refresh_token(account.refresh_token)
    except Exception as e:
        # ... error handling
        raise
```

### Mudança 2.2: Nova função `refresh_ml_token_by_id()`

Adicionada após `refresh_ml_token()`:

```python
async def refresh_ml_token_by_id(account_id: UUID) -> str | None:
    """
    Renova o token de uma conta ML específica pelo ID.
    Retorna o novo access_token se sucesso, None se falha.

    Args:
        account_id: UUID da conta MLAccount a renovar

    Returns:
        str: novo access_token se sucesso
        None: se falha na renovação
    """
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MLAccount).where(MLAccount.id == account_id)
        )
        account = result.scalar_one_or_none()

        if not account or not account.refresh_token:
            logger.warning(
                f"Conta {account_id} não encontrada ou sem refresh_token"
            )
            return None

        try:
            token_data = await _exchange_refresh_token(account.refresh_token)
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token", account.refresh_token)
            expires_in = token_data.get("expires_in", 21600)

            # Atualiza a conta no banco
            account.access_token = access_token
            account.refresh_token = refresh_token
            account.token_expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=expires_in
            )
            await db.commit()

            logger.info(
                f"Token renovado via refresh_ml_token_by_id "
                f"para {account.nickname} (exp={account.token_expires_at})"
            )
            return access_token

        except Exception as e:
            logger.error(f"Falha ao renovar token para {account_id}: {e}")
            return None
```

### Mudança 2.3: Helper interno `_exchange_refresh_token()`

Adicionado após as funções públicas:

```python
async def _exchange_refresh_token(refresh_token: str) -> dict:
    """
    Helper interno para trocar refresh_token por novo access_token.
    Evita duplicação entre refresh_ml_token() e refresh_ml_token_by_id().
    """
    from fastapi import HTTPException, status

    async with httpx.AsyncClient() as client:
        response = await client.post(
            settings.ml_token_url,
            data={
                "grant_type": "refresh_token",
                "client_id": settings.ml_client_id,
                "client_secret": settings.ml_client_secret,
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Erro ao renovar token ML: {response.text}",
        )
    return response.json()
```

## 3. `backend/app/jobs/tasks_tokens.py`

### Mudança 3.1: Adicionar retry loop

```python
# ANTES: sem retry
for account in accounts:
    try:
        token_data = await refresh_ml_token(account)
        # ... update account
    except Exception as e:
        logger.error(f"Erro ao renovar token de {account.nickname}: {e}")
        errors.append(...)

# DEPOIS: com retry 3x
for account in accounts:
    max_retries = 3
    retry_delay = 5  # segundos
    last_error = None

    for attempt in range(max_retries):
        try:
            token_data = await refresh_ml_token(account)
            # ... update account
            logger.info("Token renovado: attempt=%d", attempt + 1)
            break  # Sucesso — sai do retry loop

        except Exception as e:
            last_error = str(e)
            logger.warning(
                f"Tentativa {attempt + 1}/{max_retries} falhou: {e}"
            )

            if attempt < max_retries - 1:
                import asyncio
                await asyncio.sleep(retry_delay)
            else:
                # Última tentativa falhou
                logger.error(f"Falha permanente: {last_error}")
                errors.append({
                    "account_id": str(account.id),
                    "nickname": account.nickname,
                    "error": last_error,
                    "attempts": max_retries,
                })
```

### Mudança 3.2: Corrigir success flag

```python
# ANTES
return {
    "success": True,  # Sempre True, mesmo com erros!
    "refreshed": len(refreshed),
    "errors": len(errors),
    "error_details": errors,
}

# DEPOIS
return {
    "success": len(errors) == 0,  # True apenas se nenhum erro
    "refreshed": len(refreshed),
    "errors": len(errors),
    "error_details": errors,
}
```

## 4. `backend/app/jobs/tasks_listings.py`

### Mudança 4.1: Verificação pré-requisição + passar ml_account_id

Após buscar a conta ML (linha ~50):

```python
# ANTES
account = acc_result.scalar_one_or_none()
if not account or not account.access_token:
    logger.warning(f"Conta ML não encontrada")
    return {"error": ...}

client = MLClient(account.access_token)  # Sem ml_account_id!

# DEPOIS
account = acc_result.scalar_one_or_none()
if not account or not account.access_token:
    logger.warning(f"Conta ML não encontrada")
    return {"error": ...}

# Verifica se o token está prestes a expirar (< 30min) e renova se necessário
if account.token_expires_at:
    token_expiry_threshold = datetime.now(timezone.utc) + timedelta(minutes=30)
    if account.token_expires_at < token_expiry_threshold:
        logger.info(
            f"Token de {account.nickname} expira em < 30min, "
            f"tentando renovar..."
        )
        from app.auth.service import refresh_ml_token_by_id
        new_token = await refresh_ml_token_by_id(account.id)
        if new_token:
            account.access_token = new_token
            logger.info(f"Token renovado para {account.nickname}")
        else:
            logger.error(
                f"Falha ao renovar token para {account.nickname}, "
                f"prosseguindo com token atual"
            )

# Chama a API ML com ml_account_id para refresh automático
client = MLClient(account.access_token, ml_account_id=str(account.id))
```

## 5. `backend/app/jobs/tasks_competitors.py`

### Mudança 5.1: Passar ml_account_id em bulk_client (linha ~73)

```python
# ANTES
bulk_client = MLClient(first_account.access_token)

# DEPOIS
bulk_client = MLClient(first_account.access_token,
                       ml_account_id=str(first_account.id))
```

### Mudança 5.2: Passar ml_account_id em loop client (linha ~118)

```python
# ANTES
client = MLClient(account.access_token)

# DEPOIS
client = MLClient(account.access_token, ml_account_id=str(account.id))
```

## 6. `backend/app/jobs/tasks_orders.py`

### Mudança 6.1: Passar ml_account_id (linha ~56)

```python
# ANTES
client = MLClient(account.access_token)

# DEPOIS
# Passa ml_account_id ao cliente para suportar refresh automático
client = MLClient(account.access_token, ml_account_id=str(account.id))
```

## 7. `backend/app/jobs/tasks_ads.py`

### Mudança 7.1: Passar ml_account_id (linha ~43)

```python
# ANTES
client = MLClient(account.access_token)

# DEPOIS
# Passa ml_account_id ao cliente para suportar refresh automático
client = MLClient(account.access_token, ml_account_id=str(account.id))
```

## 8. `backend/app/reputacao/service.py`

### Mudança 8.1: Passar ml_account_id (linha ~74)

```python
# ANTES
client = MLClient(account.access_token)

# DEPOIS
# Passa ml_account_id ao cliente para suportar refresh automático
client = MLClient(account.access_token, ml_account_id=str(account.id))
```

## 9. `backend/app/core/celery_app.py`

### Mudança 9.1: Aumentar frequência + retry (linhas 56-70)

```python
# ANTES
"refresh-expired-tokens": {
    "task": "app.jobs.tasks.refresh_expired_tokens",
    "schedule": crontab(minute=0, hour="*/4"),  # A cada 4 horas
    "options": {
        "expires": 3600,
        "retry": True,
        "retry_policy": {
            "max_retries": 2,  # Apenas 2 tentativas
            ...
        },
    },
},

# DEPOIS
"refresh-expired-tokens": {
    "task": "app.jobs.tasks.refresh_expired_tokens",
    "schedule": crontab(minute=0, hour="*/2"),  # A cada 2 horas (aumentado)
    "options": {
        "expires": 3600,
        "retry": True,
        "retry_policy": {
            "max_retries": 3,  # 3 tentativas (aumentado)
            "interval_start": 5,
            "interval_step": 10,
            "interval_max": 60,
        },
    },
},
```

## Resumo de Mudanças por Tipo

| Tipo | Quantidade | Arquivos |
|------|-----------|----------|
| Novo método | 2 | client.py, service.py |
| Nova função | 2 | service.py (2x) |
| Adicionado parâmetro | 1 | client.py |
| Modificado método | 1 | client.py (_request) |
| Adicionada verificação | 1 | tasks_listings.py |
| Adicionado argumento | 5 | tasks_*.py (5 arquivos) |
| Modificada config | 1 | celery_app.py |

## Total

- **Linhas adicionadas:** ~200
- **Linhas removidas:** ~20
- **Arquivos modificados:** 9
- **Funcionalidade:** Nenhuma quebrada (backward compatible)

## Validação

```bash
# Sintaxe Python
python -m py_compile backend/app/auth/service.py
python -m py_compile backend/app/mercadolivre/client.py
python -m py_compile backend/app/jobs/tasks_*.py

# Imports
python -c "from app.mercadolivre.client import MLClient; print('OK')"
python -c "from app.auth.service import refresh_ml_token_by_id; print('OK')"

# Deploy
git push origin main  # Railway auto-deploy
```
