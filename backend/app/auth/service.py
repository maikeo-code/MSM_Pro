import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import UUID

import bcrypt
import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import MLAccount, User
from app.core.config import settings

logger = logging.getLogger(__name__)

# Suppress httpx DEBUG logs to prevent token leakage in Authorization headers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# --- Utilitários de senha ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


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
    """
    Monta a URL de autorização OAuth do Mercado Livre.
    IMPORTANTE: inclui scope 'offline_access' para permitir refresh de token mesmo sem usuário ativo.
    """
    params = {
        "response_type": "code",
        "client_id": settings.ml_client_id,
        "redirect_uri": settings.ml_redirect_uri,
        "scope": "offline_access read write",
    }
    if state:
        params["state"] = state

    return f"{settings.ml_auth_url}?{urlencode(params)}"


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
        logger.error(
            "Falha ao trocar código ML: status=%d detail=%s",
            response.status_code,
            response.text[:500],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Erro ao conectar conta ML. Tente novamente.",
        )
    return response.json()


async def refresh_ml_token(account: MLAccount) -> dict | None:
    """
    Renova o access_token de uma conta ML usando o refresh_token.
    Retorna dict com token data se sucesso, None se falha.
    Seguro para uso tanto em FastAPI endpoints quanto em Celery tasks.
    """
    token_data = await _exchange_refresh_token(account.refresh_token)
    if token_data is None:
        logger.error("Refresh falhou para conta %s (%s)", account.id, account.nickname)
    return token_data


async def refresh_ml_token_by_id(account_id: UUID) -> str | None:
    """
    Renova o token de uma conta ML específica pelo ID.
    Retorna o novo access_token se sucesso, None se falha.
    Salva o token renovado no banco.

    Atualiza rastreamento: last_token_refresh_at, token_refresh_failures, needs_reauth.

    Args:
        account_id: UUID da conta MLAccount a renovar

    Returns:
        str: novo access_token se sucesso
        None: se falha na renovação
    """
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(MLAccount).where(MLAccount.id == account_id))
        account = result.scalar_one_or_none()

        if not account or not account.refresh_token:
            logger.warning(
                f"Conta {account_id} não encontrada ou sem refresh_token — refresh abortado"
            )
            return None

        try:
            refresh_start = datetime.now(timezone.utc)
            logger.debug(f"Iniciando refresh de token para {account.nickname} (account_id={account_id})")

            token_data = await _exchange_refresh_token(account.refresh_token)
            if token_data is None:
                logger.error(
                    f"Falha ao renovar token para {account.nickname}: API do ML retornou erro"
                )
                # Registra falha no refresh
                account.token_refresh_failures += 1
                account.last_token_refresh_at = datetime.now(timezone.utc)
                if account.token_refresh_failures >= 5:
                    account.needs_reauth = True
                    logger.warning(
                        f"Conta {account.nickname} marcada para reautenticação "
                        f"após {account.token_refresh_failures} falhas"
                    )
                await db.commit()
                return None

            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token", account.refresh_token)
            expires_in = token_data.get("expires_in", 21600)  # 6h padrão

            # Atualiza a conta no banco
            account.access_token = access_token
            account.refresh_token = refresh_token
            account.token_expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=expires_in
            )
            account.last_token_refresh_at = datetime.now(timezone.utc)
            account.token_refresh_failures = 0  # Reset de falhas após sucesso
            account.needs_reauth = False  # Reset do flag de reauth
            await db.commit()

            refresh_elapsed = (datetime.now(timezone.utc) - refresh_start).total_seconds()
            logger.info(
                f"Token renovado com sucesso para {account.nickname}: "
                f"expires_at={account.token_expires_at.isoformat()}, "
                f"elapsed={refresh_elapsed:.2f}s, "
                f"account_id={account_id}"
            )
            return access_token

        except Exception as e:
            logger.error(
                f"Exceção ao renovar token para {account.nickname} ({account_id}): {e}",
                exc_info=True
            )
            # Registra falha por exceção
            account.token_refresh_failures += 1
            account.last_token_refresh_at = datetime.now(timezone.utc)
            if account.token_refresh_failures >= 5:
                account.needs_reauth = True
                logger.warning(
                    f"Conta {account.nickname} marcada para reautenticação "
                    f"após {account.token_refresh_failures} falhas"
                )
            await db.commit()
            return None


async def _exchange_refresh_token(refresh_token: str) -> dict | None:
    """
    Helper interno para trocar refresh_token por novo access_token.
    Retorna dict com token data se sucesso, None se falha.
    Seguro para uso tanto em FastAPI endpoints quanto em Celery tasks.

    Casos de falha comuns:
    - 400: refresh_token expirou ou inválido
    - 401: client_id/secret inválido
    - 503: API ML indisponível (retry automático)
    """
    try:
        async with httpx.AsyncClient() as client:
            logger.debug("Iniciando troca de refresh_token com ML")
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
            error_detail = response.text[:500]  # mais contexto para debug
            logger.error(
                "Falha ao renovar token ML: status=%d detail=%s",
                response.status_code,
                error_detail,
            )

            # Detalhamento por status
            if response.status_code == 400:
                logger.warning("Possível refresh_token expirado ou inválido")
            elif response.status_code == 401:
                logger.warning("Credenciais client_id/client_secret inválidas")
            elif response.status_code >= 500:
                logger.warning("Servidor ML indisponível (5xx) — retry será feito automaticamente")

            return None

        token_data = response.json()
        logger.info(
            "Token renovado com sucesso via refresh_token: expires_in=%s",
            token_data.get("expires_in", "unknown"),
        )
        return token_data

    except Exception as e:
        logger.error("Exceção ao renovar token ML: %s", type(e).__name__, exc_info=True)
        return None


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
        logger.info("Token OAuth atualizado: account=%s nickname=%s expires=%s", account.id, nickname, token_expires_at)
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
        logger.info("Nova conta ML criada: ml_user_id=%s nickname=%s", ml_user_id, nickname)

    await db.flush()
    await db.refresh(account)
    return account
