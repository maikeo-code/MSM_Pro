import sys

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


def _is_celery_context() -> bool:
    """
    Detecta se o processo atual é um worker/beat do Celery.
    Em Celery, cada task Celery roda em um event loop NOVO (via run_async),
    e o pool de conexões do SQLAlchemy async fica preso ao primeiro loop —
    causando 'Future attached to a different loop'. Usar NullPool elimina o
    problema porque cada conexão é fresca.
    """
    argv0 = (sys.argv[0] if sys.argv else "") or ""
    return "celery" in argv0.lower()


def _build_engine():
    """Cria o engine assíncrono com parâmetros adequados ao driver."""
    url = settings.database_url
    # SQLite não suporta pool_size/max_overflow/pool_timeout/pool_recycle
    if url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool
        return create_async_engine(
            url,
            echo=settings.debug,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    # Em contexto Celery, usar NullPool para evitar reuso de conexões entre loops.
    if _is_celery_context():
        from sqlalchemy.pool import NullPool
        return create_async_engine(
            url,
            echo=settings.debug,
            poolclass=NullPool,
        )
    return create_async_engine(
        url,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=1800,
    )


# Engine async
engine = _build_engine()

# Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base declarativa para todos os modelos SQLAlchemy."""
    pass


async def get_db() -> AsyncSession:
    """Dependency injection do FastAPI para obter sessão de banco."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
