from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import MLAccount, User
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- Utilitários de senha ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


# --- JWT ---

def create_access_token(user_id: UUID) -> tuple[str, int]:
    """Cria JWT e retorna (token, expires_in_seconds)."""
    expire_minutes = settings.access_token_expire_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return token, expire_minutes * 60


# --- CRUD de usuário ---

async def create_user(db: AsyncSession, email: str, password: str) -> User:
    """Cria um novo usuário com senha hasheada."""
    from fastapi import HTTPException, status

    # Verifica se email já existe
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email já cadastrado",
        )

    user = User(email=email, hashed_password=hash_password(password))
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    """Autentica usuário por email/senha. Retorna None se inválido."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# --- OAuth Mercado Livre ---

def get_ml_auth_url(state: str | None = None) -> str:
    """Monta a URL de autorização OAuth do Mercado Livre."""
    params = {
        "response_type": "code",
        "client_id": settings.ml_client_id,
        "redirect_uri": settings.ml_redirect_uri,
    }
    if state:
        params["state"] = state

    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{settings.ml_auth_url}?{query}"


async def exchange_code_for_token(code: str) -> dict:
    """Troca o código de autorização por access_token e refresh_token."""
    from fastapi import HTTPException, status

    async with httpx.AsyncClient() as client:
        response = await client.post(
            settings.ml_token_url,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.ml_client_id,
                "client_secret": settings.ml_client_secret,
                "code": code,
                "redirect_uri": settings.ml_redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Erro ao trocar código ML: {response.text}",
        )
    return response.json()


async def refresh_ml_token(account: MLAccount) -> dict:
    """Renova o access_token de uma conta ML usando o refresh_token."""
    from fastapi import HTTPException, status

    async with httpx.AsyncClient() as client:
        response = await client.post(
            settings.ml_token_url,
            data={
                "grant_type": "refresh_token",
                "client_id": settings.ml_client_id,
                "client_secret": settings.ml_client_secret,
                "refresh_token": account.refresh_token,
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


async def get_ml_user_info(access_token: str) -> dict:
    """Busca informações do usuário ML autenticado."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.ml_api_base}/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
    response.raise_for_status()
    return response.json()


async def save_ml_account(
    db: AsyncSession, user_id: UUID, token_data: dict
) -> MLAccount:
    """Salva ou atualiza conta ML no banco após OAuth."""
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token", "")
    ml_user_id = str(token_data.get("user_id", ""))
    expires_in = token_data.get("expires_in", 21600)  # 6h padrão

    token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    # Busca info do usuário ML
    user_info = await get_ml_user_info(access_token)
    nickname = user_info.get("nickname", "")
    email = user_info.get("email", None)

    # Verifica se conta já existe para este usuário
    result = await db.execute(
        select(MLAccount).where(
            MLAccount.user_id == user_id,
            MLAccount.ml_user_id == ml_user_id,
        )
    )
    account = result.scalar_one_or_none()

    if account:
        account.access_token = access_token
        account.refresh_token = refresh_token
        account.token_expires_at = token_expires_at
        account.nickname = nickname
        account.email = email
        account.is_active = True
    else:
        account = MLAccount(
            user_id=user_id,
            ml_user_id=ml_user_id,
            nickname=nickname,
            email=email,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
        )
        db.add(account)

    await db.flush()
    await db.refresh(account)
    return account
