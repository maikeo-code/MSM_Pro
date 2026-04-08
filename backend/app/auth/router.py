import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service
from app.auth.models import MLAccount, User, UserPreference
from app.auth.oauth_state import generate_oauth_state, verify_oauth_state
from app.auth.schemas import (
    MLAccountOut,
    MLConnectURL,
    Token,
    TokenDiagnosticAccount,
    TokenDiagnosticResponse,
    UserCreate,
    UserLogin,
    UserOut,
    UserPreferenceOut,
    UserPreferenceUpdate,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rate_limit import (
    limiter,
    rate_limit_auth_login,
    rate_limit_auth_register,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(rate_limit_auth_register())
async def register(
    request: Request,
    payload: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Cria um novo usuário.

    Proteção:
    - Rate limiting: 3 requests/hour per IP
    - Se REGISTRATION_OPEN=false, requer invite_code válido
    - Se REGISTRATION_OPEN=true (default), registros abertos para todos
    """
    # Verificar se registros estão abertos
    if not settings.registration_open:
        # Se fechado, requer invite_code
        if not payload.invite_code:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Registros estão fechados. Contate o administrador.",
            )
        # TODO: Validar invite_code contra tabela de invite_codes (implementar futuramente)
        # Por enquanto, aceitar qualquer invite_code não vazio quando REGISTRATION_OPEN=false

    user = await service.create_user(db, payload.email, payload.password)
    return user


@router.post("/login", response_model=Token)
@limiter.limit(rate_limit_auth_login())
async def login(
    request: Request,
    payload: UserLogin,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Autentica e retorna JWT.

    Proteção:
    - Rate limiting: 5 requests/minute per IP
    """
    user = await service.authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha inválidos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo",
        )
    token, expires_in = service.create_access_token(user.id)
    return Token(
        access_token=token,
        expires_in=expires_in,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Retorna dados do usuário autenticado."""
    return current_user


@router.post("/refresh", response_model=Token)
async def refresh_jwt(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Renova o JWT do usuário se ainda válido. Retorna novo token com 30 dias."""
    token, expires_in = service.create_access_token(current_user.id)
    return Token(
        access_token=token,
        expires_in=expires_in,
        user=UserOut.model_validate(current_user),
    )


@router.get("/ml/connect", response_model=MLConnectURL)
async def ml_connect(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Retorna a URL para autorizar conta do Mercado Livre via OAuth."""
    state_value = generate_oauth_state(current_user.id)
    auth_url = service.get_ml_auth_url(state=state_value)
    return MLConnectURL(auth_url=auth_url)


@router.get("/ml/callback")
async def ml_callback(
    code: str = Query(..., description="Código de autorização retornado pelo ML"),
    state: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Callback OAuth do Mercado Livre.
    Troca o code por tokens e salva no banco.
    """
    if not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State inválido ou ausente",
        )

    # Verify CSRF state (HMAC signature + TTL)
    user_id = verify_oauth_state(state)

    # Verifica se usuário existe
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    # Troca code por token
    token_data = await service.exchange_code_for_token(code)

    # Salva/atualiza conta ML
    account = await service.save_ml_account(db, user_id, token_data)
    await db.commit()

    # Dispara backfill de pedidos automaticamente após OAuth callback
    # Estima ~7 dias de gap como padrão (pode ter mais, mas 7 é reasonable)
    from app.jobs.tasks import backfill_orders_after_reconnect
    logger.info(
        f"Conta ML reconectada (OAuth callback): {account.nickname}. "
        f"Agendando backfill de 7 dias..."
    )
    backfill_orders_after_reconnect.apply_async(
        args=[str(account.id), 7],
        countdown=10,  # delay 10s para permitir propagação
    )

    from fastapi.responses import RedirectResponse
    return RedirectResponse(
        url=f"{settings.frontend_url}/configuracoes?ml_connected=1",
        status_code=302,
    )


@router.get("/ml/accounts", response_model=list[MLAccountOut])
async def list_ml_accounts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Lista todas as contas ML do usuário com metadados enriquecidos.

    Retorna: id, nickname, email, token_expires_at, ativo, contagem de anuncios ativos.
    """
    from sqlalchemy import func

    from app.vendas.models import Listing

    result = await db.execute(
        select(MLAccount).where(
            MLAccount.user_id == current_user.id,
            MLAccount.is_active == True,  # noqa: E712
        )
    )
    accounts = result.scalars().all()

    # Enriquece cada conta com dados adicionais
    enriched_accounts = []
    for account in accounts:
        # Conta anuncios ativos
        listings_result = await db.execute(
            select(func.count(Listing.id)).where(
                Listing.ml_account_id == account.id,
                Listing.status == "active",
            )
        )
        active_listings = listings_result.scalar() or 0

        enriched_accounts.append(
            MLAccountOut(
                id=account.id,
                ml_user_id=account.ml_user_id,
                nickname=account.nickname,
                email=account.email,
                token_expires_at=account.token_expires_at,
                is_active=account.is_active,
                created_at=account.created_at,
                active_listings_count=active_listings,
                last_sync_at=None,  # pode ser implementado com sync_logs no futuro
            )
        )

    return enriched_accounts


@router.post("/ml/accounts/{account_id}/refresh")
async def refresh_ml_account_token(
    account_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Força renovação imediata do token de uma conta ML."""
    result = await db.execute(
        select(MLAccount).where(
            MLAccount.id == account_id,
            MLAccount.user_id == current_user.id,
            MLAccount.is_active == True,  # noqa: E712
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta não encontrada")

    new_token = await service.refresh_ml_token_by_id(account.id)
    if not new_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Falha ao renovar token. Tente reconectar a conta.",
        )

    # Reload account to get updated expiry
    await db.refresh(account)
    return {
        "status": "ok",
        "nickname": account.nickname,
        "token_expires_at": account.token_expires_at.isoformat() if account.token_expires_at else None,
    }


@router.get("/ml/tokens-health")
async def ml_tokens_health(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Retorna status de saúde dos tokens de todas as contas ML do usuário."""
    from datetime import datetime, timezone

    result = await db.execute(
        select(MLAccount).where(
            MLAccount.user_id == current_user.id,
            MLAccount.is_active == True,  # noqa: E712
        )
    )
    accounts = result.scalars().all()

    now = datetime.now(timezone.utc)
    items = []
    for acc in accounts:
        expires_at = acc.token_expires_at
        if expires_at:
            remaining = (expires_at - now).total_seconds()
            if remaining < 0:
                token_status = "expired"
            elif remaining < 3600:
                token_status = "expiring_soon"
            else:
                token_status = "healthy"
        else:
            remaining = None
            token_status = "unknown"

        items.append({
            "account_id": str(acc.id),
            "nickname": acc.nickname,
            "token_status": token_status,
            "token_expires_at": expires_at.isoformat() if expires_at else None,
            "remaining_seconds": int(remaining) if remaining else None,
            "has_refresh_token": bool(acc.refresh_token),
        })

    all_healthy = all(i["token_status"] == "healthy" for i in items)
    return {
        "overall": "healthy" if all_healthy else "degraded",
        "accounts": items,
    }


@router.delete("/ml/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ml_account(
    account_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Remove (desativa) uma conta ML do usuário."""
    result = await db.execute(
        select(MLAccount).where(
            MLAccount.id == account_id,
            MLAccount.user_id == current_user.id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta não encontrada")

    account.is_active = False
    await db.commit()


@router.get("/diagnostics", response_model=TokenDiagnosticResponse)
async def ml_diagnostics(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Retorna diagnóstico completo de saúde dos tokens ML e Celery.

    Inclui:
    - Status de cada token ML (healthy/expiring_soon/expired)
    - Último refresh bem-sucedido
    - Contador de falhas de refresh
    - Status do Celery (online/offline)
    - Recomendações de ação
    """
    from datetime import datetime, timezone as tz
    from app.core.celery_app import celery_app
    from app.core.models import SyncLog

    now = datetime.now(tz.utc)
    recommendations = []

    # 1. Verificar status do Celery
    celery_status = "unknown"
    try:
        inspector = celery_app.control.inspect()
        active = inspector.active()
        if active is not None and len(active) > 0:
            celery_status = "online"
        else:
            celery_status = "offline"
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Erro ao verificar Celery: {e}")
        celery_status = "unknown"

    # 2. Obter último token refresh task
    last_token_refresh_task = None
    try:
        result = await db.execute(
            select(SyncLog)
            .where(SyncLog.task_name == "refresh_expired_tokens")
            .order_by(SyncLog.started_at.desc())
            .limit(1)
        )
        last_sync_log = result.scalar_one_or_none()
        if last_sync_log:
            last_token_refresh_task = last_sync_log.started_at
    except Exception:
        pass

    # 3. Processar cada conta ML
    result = await db.execute(
        select(MLAccount).where(
            MLAccount.user_id == current_user.id,
            MLAccount.is_active == True,  # noqa: E712
        )
    )
    accounts = result.scalars().all()

    diagnostic_accounts = []
    for account in accounts:
        # Determinar status do token
        expires_at = account.token_expires_at
        token_status = "unknown"
        remaining_hours = None
        if expires_at:
            remaining_secs = (expires_at - now).total_seconds()
            remaining_hours = remaining_secs / 3600
            if remaining_secs < 0:
                token_status = "expired"
            elif remaining_secs < 3600:  # 1 hora
                token_status = "expiring_soon"
            else:
                token_status = "healthy"

        # Obter último sync bem-sucedido
        last_successful_sync = None
        try:
            sync_result = await db.execute(
                select(SyncLog)
                .where(
                    SyncLog.ml_account_id == account.id,
                    SyncLog.task_name == "sync_all_snapshots",
                    SyncLog.status == "success",
                )
                .order_by(SyncLog.finished_at.desc())
                .limit(1)
            )
            last_sync = sync_result.scalar_one_or_none()
            if last_sync and last_sync.finished_at:
                last_successful_sync = last_sync.finished_at
        except Exception:
            pass

        # Calcular dias desde último sync
        days_since_last_sync = None
        data_gap_warning = None
        if last_successful_sync:
            days_diff = (now - last_successful_sync).days
            days_since_last_sync = days_diff
            if days_diff > 2:
                data_gap_warning = f"Sem sincronização há {days_diff} dias"

        # Status do último refresh attempt
        last_refresh_success = True
        if account.last_token_refresh_at:
            # Se token_refresh_failures > 0, o último attempt falhou
            last_refresh_success = account.token_refresh_failures == 0

        diagnostic_accounts.append(
            TokenDiagnosticAccount(
                id=account.id,
                nickname=account.nickname,
                token_status=token_status,
                token_expires_at=expires_at,
                remaining_hours=remaining_hours,
                has_refresh_token=bool(account.refresh_token),
                last_successful_sync=last_successful_sync,
                last_refresh_attempt=account.last_token_refresh_at,
                last_refresh_success=last_refresh_success,
                days_since_last_sync=days_since_last_sync,
                data_gap_warning=data_gap_warning,
                refresh_failure_count=account.token_refresh_failures,
                needs_reauth=account.needs_reauth,
            )
        )

        # Gerar recomendações
        if account.needs_reauth:
            recommendations.append(
                f"Reconectar conta '{account.nickname}' — "
                f"refresh token expirou ou foi invalidado ({account.token_refresh_failures} falhas)"
            )
        elif token_status == "expired":
            recommendations.append(
                f"Token da conta '{account.nickname}' expirou — "
                f"refresh será feito automaticamente nas próximas 2h"
            )
        elif token_status == "expiring_soon":
            recommendations.append(
                f"Token da conta '{account.nickname}' expira em menos de 1h — "
                f"será renovado automaticamente"
            )

        if data_gap_warning:
            recommendations.append(
                f"Conta '{account.nickname}': {data_gap_warning} — "
                f"verifique se Celery está ativo"
            )

    # Adicionar recomendações sobre Celery
    if celery_status == "offline":
        recommendations.insert(0, "Celery worker offline — sincronizações não estão acontecendo")
    elif celery_status == "unknown":
        recommendations.insert(0, "Status do Celery desconhecido — verifique logs de erro")

    return TokenDiagnosticResponse(
        celery_status=celery_status,
        last_token_refresh_task=last_token_refresh_task,
        accounts=diagnostic_accounts,
        recommendations=recommendations,
    )


@router.get("/preferences", response_model=UserPreferenceOut)
async def get_preferences(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Retorna as preferências do usuário autenticado."""
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == current_user.id)
    )
    pref = result.scalar_one_or_none()
    if not pref:
        return UserPreferenceOut()
    return pref


@router.put("/preferences", response_model=UserPreferenceOut)
async def update_preferences(
    data: UserPreferenceUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Atualiza as preferências do usuário (ex: conta ML ativa)."""
    # Se active_ml_account_id foi informado, verificar que pertence ao usuário
    if data.active_ml_account_id is not None:
        account_result = await db.execute(
            select(MLAccount).where(
                MLAccount.id == data.active_ml_account_id,
                MLAccount.user_id == current_user.id,
                MLAccount.is_active == True,  # noqa: E712
            )
        )
        if not account_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conta ML não encontrada ou inativa",
            )

    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == current_user.id)
    )
    pref = result.scalar_one_or_none()
    if not pref:
        pref = UserPreference(user_id=current_user.id)
        db.add(pref)
    pref.active_ml_account_id = data.active_ml_account_id
    await db.commit()
    await db.refresh(pref)
    return pref


@router.post("/ml/accounts/{account_id}/backfill-orders")
async def backfill_orders_manual(
    account_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=7, ge=1, le=30, description="Dias a fazer backfill (1-30)"),
):
    """
    Dispara backfill manual de pedidos para uma conta ML específica.

    Útil quando:
    - Uma conta ficou desconectada e o backfill automático não foi acionado
    - Usuário quer recuperar manualmente dados de pedidos históricos

    Args:
        account_id: UUID da conta ML
        days: Número de dias a fazer backfill (1-30, padrão 7)

    Retorna:
        Status da task agendada
    """
    # Verifica se conta pertence ao usuário
    result = await db.execute(
        select(MLAccount).where(
            MLAccount.id == account_id,
            MLAccount.user_id == current_user.id,
            MLAccount.is_active == True,  # noqa: E712
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conta ML não encontrada ou inativa",
        )

    # Dispara task Celery de backfill
    from app.jobs.tasks import backfill_orders_after_reconnect

    logger.info(
        f"Backfill manual solicitado por {current_user.email} "
        f"para conta {account.nickname} ({days} dias)"
    )

    task = backfill_orders_after_reconnect.apply_async(
        args=[str(account.id), days],
        countdown=5,  # delay 5s
    )

    return {
        "status": "backfill_scheduled",
        "account_id": str(account.id),
        "nickname": account.nickname,
        "days": days,
        "task_id": task.id,
        "message": f"Backfill de {days} dias agendado. Verifique o status em alguns minutos.",
    }


@router.post("/debug/trigger-health-check")
async def trigger_health_check(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Dispara o health check de sync imediatamente (sem esperar o cron)."""
    from app.jobs.tasks import check_sync_health
    task = check_sync_health.apply_async(countdown=2)
    return {"status": "scheduled", "task_id": task.id}


@router.post("/debug/trigger-task/{task_name}")
async def trigger_celery_task(
    task_name: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Dispara qualquer Celery task agendada por nome (sem esperar o cron).
    Apenas tasks da whitelist podem ser disparadas.
    """
    whitelist = {
        "sync_orders",
        "sync_questions",
        "sync_all_snapshots",
        "sync_competitor_snapshots",
        "sync_reputation",
        "sync_ads",
        "evaluate_alerts",
        "refresh_expired_tokens",
        "check_sync_health",
        "send_daily_intel_report",
    }
    if task_name not in whitelist:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task não permitida. Whitelist: {sorted(whitelist)}",
        )

    from app.jobs import tasks as tasks_module
    task_func = getattr(tasks_module, task_name, None)
    if task_func is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_name}' não encontrada no módulo tasks.",
        )

    result = task_func.apply_async(countdown=1)
    return {"status": "scheduled", "task_name": task_name, "task_id": result.id}


@router.get("/debug/smtp-status")
async def smtp_status(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Retorna se SMTP está configurado e mostra host/user (sem a senha)."""
    from app.core.email import is_smtp_configured
    return {
        "configured": is_smtp_configured(),
        "smtp_host": settings.smtp_host,
        "smtp_port": settings.smtp_port,
        "smtp_user": settings.smtp_user,
        "smtp_from": settings.smtp_from,
        "smtp_to": settings.smtp_to,
        "has_password": bool(settings.smtp_pass),
    }


@router.post("/debug/send-test-email")
async def send_test_email(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Envia email de teste para o usuário autenticado."""
    from app.core.email import is_smtp_configured, send_alert_email
    if not is_smtp_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMTP não configurado. Defina SMTP_HOST, SMTP_USER, SMTP_PASS no Railway.",
        )
    ok = send_alert_email(
        to=current_user.email,
        subject="[MSM_Pro] Teste de configuração SMTP",
        body="Se você está lendo isso, o SMTP está funcionando.\n\nEste email foi disparado manualmente via POST /auth/debug/send-test-email.",
    )
    return {"sent": ok, "to": current_user.email}
