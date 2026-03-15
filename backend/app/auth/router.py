from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service
from app.auth.models import MLAccount, User
from app.auth.schemas import MLAccountOut, MLConnectURL, Token, UserCreate, UserLogin, UserOut
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Cria um novo usuário."""
    user = await service.create_user(db, payload.email, payload.password)
    return user


@router.post("/login", response_model=Token)
async def login(
    payload: UserLogin,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Autentica e retorna JWT."""
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


@router.get("/ml/connect", response_model=MLConnectURL)
async def ml_connect(
    current_user: Annotated[User, Depends(get_current_user)],
    state: str | None = Query(default=None, description="Estado opcional para CSRF"),
):
    """Retorna a URL para autorizar conta do Mercado Livre via OAuth."""
    # Embed user_id no state para recuperar no callback
    state_value = f"{current_user.id}"
    if state:
        state_value = f"{current_user.id}:{state}"

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

    # Extrai user_id do state
    user_id_str = state.split(":")[0]
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State inválido",
        )

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
    """Lista todas as contas ML do usuário."""
    result = await db.execute(
        select(MLAccount).where(
            MLAccount.user_id == current_user.id,
            MLAccount.is_active == True,  # noqa: E712
        )
    )
    return result.scalars().all()


@router.get("/ml/accounts/{account_id}/token")
async def get_ml_account_token(
    account_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Retorna o access_token ML de uma conta (para uso com MCP server)."""
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
    if not account.access_token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token ML não disponível. Reconecte a conta.")
    return {
        "access_token": account.access_token,
        "nickname": account.nickname,
        "ml_user_id": account.ml_user_id,
        "expires_at": account.token_expires_at.isoformat() if account.token_expires_at else None,
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
