"""
Redis client singleton para operações distribuídas.

Funções:
  - get_redis_client(): retorna instância Redis aioredis
  - Usado para locks, caches, pub/sub

Connection pooling:
  - Cada chamada cria uma nova conexão (simples)
  - Alternativa: usar ConnectionPool reutilizável (future optimization)
"""
import logging

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_redis_client() -> aioredis.Redis:
    """
    Retorna cliente Redis assíncrono.

    Returns:
        aioredis.Redis: cliente configurado com URL da env
    """
    return aioredis.from_url(settings.redis_url, decode_responses=True)
