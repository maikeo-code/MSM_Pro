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
