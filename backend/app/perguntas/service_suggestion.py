"""Orquestra o pipeline completo de sugestão IA para perguntas Q&A."""
import hashlib
import logging
import re
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.mercadolivre.client import MLClient
from app.perguntas.classifier import classify_with_ai_fallback
from app.perguntas.context_collector import collect_context
from app.perguntas.models import QASuggestionLog
from app.perguntas.prompts import build_prompt

if TYPE_CHECKING:
    from app.perguntas.models import Question

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"  # Sonnet para qualidade
CACHE_TTL = 86400  # 24h


async def generate_suggestion(
    db: AsyncSession,
    question: "Question",
    account_token: str,
    regenerate: bool = False,
) -> dict:
    """
    Pipeline completo de sugestão IA:
    1. Classificar tipo da pergunta
    2. Coletar contexto (histórico + item info)
    3. Verificar cache Redis
    4. Gerar resposta via Claude Sonnet
    5. Sanitizar (remover dados sensíveis)
    6. Salvar log e atualizar question

    Args:
        db: AsyncSession SQLAlchemy
        question: Question model
        account_token: Token OAuth da conta ML
        regenerate: Se True, ignora cache e gera nova sugestão

    Returns:
        dict com chaves:
            - suggestion: str (resposta sugerida)
            - confidence: str (high | medium | low)
            - question_type: str (classificação)
            - cached: bool (se veio do cache)
            - latency_ms: int (tempo de processamento)
    """
    start_ms = int(time.time() * 1000)

    # 1. Classificar
    question_type = await classify_with_ai_fallback(question.text)

    # 2. Cache check (skip se regenerate=True)
    cache_key = _cache_key(question.mlb_id, question.text)
    if not regenerate:
        cached = await _get_from_cache(cache_key)
        if cached:
            return {
                "suggestion": cached,
                "confidence": "medium",
                "question_type": question_type,
                "cached": True,
                "latency_ms": int(time.time() * 1000) - start_ms,
            }

    # 3. Coletar contexto
    try:
        async with MLClient(account_token) as client:
            context = await collect_context(db, question, client)
    except Exception as exc:
        logger.warning("Falha ao coletar contexto: %s", exc)
        context = {
            "historical_qa": [],
            "item_description": "",
            "item_attributes": [],
            "item_title": question.item_title or "",
        }

    # 4. Gerar via Claude
    system_prompt, user_prompt = build_prompt(question.text, question_type, context)

    if not settings.anthropic_api_key:
        return {
            "suggestion": "Sugestão IA indisponível: ANTHROPIC_API_KEY não configurada no servidor. Configure a variável de ambiente no Railway.",
            "confidence": "low",
            "question_type": question_type,
            "cached": False,
            "latency_ms": int(time.time() * 1000) - start_ms,
        }

    try:
        suggestion_text, tokens_used = await _call_claude(system_prompt, user_prompt)
    except httpx.HTTPStatusError as e:
        logger.error(
            "Claude API HTTP error: status=%s body=%s",
            e.response.status_code,
            e.response.text[:200],
        )
        error_msg = f"Erro na API Claude (HTTP {e.response.status_code}). "
        if e.response.status_code == 401:
            error_msg += "ANTHROPIC_API_KEY inválida."
        elif e.response.status_code == 429:
            error_msg += "Limite de requisições excedido. Tente em alguns minutos."
        else:
            error_msg += "Tente novamente."
        return {
            "suggestion": error_msg,
            "confidence": "low",
            "question_type": question_type,
            "cached": False,
            "latency_ms": int(time.time() * 1000) - start_ms,
        }
    except httpx.ConnectError as e:
        logger.error("Erro de conexão com Claude API: %s", e)
        return {
            "suggestion": "Erro de conexão com a API Claude. Verifique sua conexão de internet e tente novamente.",
            "confidence": "low",
            "question_type": question_type,
            "cached": False,
            "latency_ms": int(time.time() * 1000) - start_ms,
        }
    except httpx.TimeoutException:
        logger.error("Timeout ao chamar Claude API")
        return {
            "suggestion": "Timeout ao chamar a API Claude. A requisição demorou muito tempo. Tente novamente.",
            "confidence": "low",
            "question_type": question_type,
            "cached": False,
            "latency_ms": int(time.time() * 1000) - start_ms,
        }
    except Exception as exc:
        logger.error("Erro inesperado ao gerar sugestão IA: %s", exc, exc_info=True)
        return {
            "suggestion": f"Erro inesperado ao gerar sugestão: {str(exc)[:100]}. Entre em contato com o suporte.",
            "confidence": "low",
            "question_type": question_type,
            "cached": False,
            "latency_ms": int(time.time() * 1000) - start_ms,
        }

    # 5. Sanitizar
    suggestion_text = _sanitize(suggestion_text)

    # 6. Determinar confiança
    confidence = _determine_confidence(context, question_type)

    latency = int(time.time() * 1000) - start_ms

    # 7. Salvar log
    log = QASuggestionLog(
        question_id=question.id,
        question_text=question.text,
        suggested_answer=suggestion_text,
        question_type=question_type,
        confidence=confidence,
        tokens_used=tokens_used,
        latency_ms=latency,
    )
    db.add(log)

    # 8. Atualizar question
    question.ai_suggestion_text = suggestion_text
    question.ai_suggestion_confidence = confidence
    question.ai_suggested_at = datetime.now(timezone.utc)

    await db.commit()

    # 9. Cache
    await _set_cache(cache_key, suggestion_text)

    return {
        "suggestion": suggestion_text,
        "confidence": confidence,
        "question_type": question_type,
        "cached": False,
        "latency_ms": latency,
    }


async def _call_claude(system: str, user: str) -> tuple[str, int]:
    """
    Chama Claude API e retorna (texto, tokens_usados).

    Args:
        system: System prompt
        user: User prompt

    Returns:
        (texto_resposta, tokens_usados)

    Raises:
        Exception se a chamada falhar
    """
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 500,
        "temperature": 0.2,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(ANTHROPIC_API_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        text = data["content"][0]["text"]
        tokens = data.get("usage", {}).get("output_tokens", 0)
        return text, tokens


def _sanitize(text: str) -> str:
    """Remove dados sensíveis da sugestão."""
    # Remover telefones
    text = re.sub(
        r'\(?\d{2}\)?\s*\d{4,5}[-.\s]?\d{4}',
        '[telefone removido]',
        text
    )
    # Remover emails
    text = re.sub(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        '[email removido]',
        text
    )
    # Remover URLs
    text = re.sub(r'https?://\S+', '[link removido]', text)
    # Remover WhatsApp mentions
    text = re.sub(
        r'\b(whatsapp|whats|zap|wpp)\b',
        '[removido]',
        text,
        flags=re.IGNORECASE
    )
    # Limitar a 2000 chars
    return text[:2000].strip()


def _determine_confidence(context: dict, question_type: str) -> str:
    """
    Determina nível de confiança baseado no contexto disponível.

    Args:
        context: Dict retornado por collect_context()
        question_type: Tipo da pergunta

    Returns:
        "high" | "medium" | "low"
    """
    # Se tem Q&A idêntico anterior → high
    if context.get("historical_qa"):
        return "high"
    # Se tem descrição e atributos → medium
    if context.get("item_description") and context.get("item_attributes"):
        return "medium"
    # Sem contexto → low
    return "low"


def _cache_key(mlb_id: str, question_text: str) -> str:
    """
    Gera chave de cache para a sugestão.
    Usa hash MD5 do texto normalizado para evitar colisões.
    """
    text_hash = hashlib.md5(
        question_text.lower().strip().encode()
    ).hexdigest()[:12]
    return f"qa:suggestion:{mlb_id}:{text_hash}"


async def _get_from_cache(key: str) -> str | None:
    """
    Busca sugestão no cache Redis.

    Args:
        key: Chave de cache gerada por _cache_key()

    Returns:
        Texto da sugestão se encontrada, None caso contrário
    """
    import redis.asyncio as aioredis

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        return await r.get(key)
    except Exception:
        return None
    finally:
        try:
            await r.aclose()
        except Exception:
            pass


async def _set_cache(key: str, value: str) -> None:
    """
    Salva sugestão no cache Redis com TTL de 24h.

    Args:
        key: Chave de cache gerada por _cache_key()
        value: Texto da sugestão
    """
    import redis.asyncio as aioredis

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await r.set(key, value, ex=CACHE_TTL)
    except Exception as exc:
        logger.debug("Falha ao salvar cache: %s", exc)
    finally:
        try:
            await r.aclose()
        except Exception:
            pass
