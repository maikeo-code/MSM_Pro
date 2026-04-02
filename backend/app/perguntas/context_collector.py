"""Coleta contexto enriquecido para sugestões de resposta IA."""
import asyncio
import logging
from typing import TYPE_CHECKING

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.mercadolivre.client import MLClient, MLClientError

if TYPE_CHECKING:
    from app.perguntas.models import Question

logger = logging.getLogger(__name__)


async def collect_context(
    db: AsyncSession,
    question: "Question",
    client: MLClient,
) -> dict:
    """
    Coleta contexto enriquecido para uma pergunta, em paralelo:
    1. Q&A histórico do mesmo anúncio (banco local, top 5 do mesmo tipo)
    2. Descrição e atributos do item (API ML)

    Returns dict com keys: historical_qa, item_description, item_attributes, item_title
    """
    results = await asyncio.gather(
        _get_historical_qa(db, question),
        _get_item_info(client, question.mlb_id, question.item_title or ""),
        return_exceptions=True,
    )

    historical_qa = results[0] if not isinstance(results[0], Exception) else []
    item_info = results[1] if not isinstance(results[1], Exception) else {}

    return {
        "historical_qa": historical_qa,
        "item_description": item_info.get("description", ""),
        "item_attributes": item_info.get("attributes", []),
        "item_title": item_info.get("title", question.item_title or ""),
    }


async def _get_historical_qa(
    db: AsyncSession,
    question: "Question",
    limit: int = 5,
) -> list[dict]:
    """Busca perguntas respondidas anteriores do mesmo anúncio."""
    from app.perguntas.models import Question as Q

    stmt = (
        select(Q)
        .where(
            Q.mlb_id == question.mlb_id,
            Q.status == "ANSWERED",
            Q.answer_text.isnot(None),
            Q.id != question.id,
        )
        .order_by(desc(Q.date_created))
        .limit(limit)
    )
    result = await db.execute(stmt)
    questions = result.scalars().all()

    return [
        {
            "pergunta": q.text,
            "resposta": q.answer_text,
        }
        for q in questions
    ]


async def _get_item_info(client: MLClient, mlb_id: str, title_fallback: str = "") -> dict:
    """Busca info do item via API ML (descrição + atributos)."""
    try:
        # Busca dados básicos do item
        item = await client.get_item(mlb_id)

        # Busca descrição separadamente
        description = ""
        try:
            desc_data = await client._request(
                "GET",
                f"/items/{mlb_id}/description",
            )
            # A resposta pode vir como dict com keys: text, plain_text, etc.
            description = (
                desc_data.get("plain_text", "")
                or desc_data.get("text", "")
                or ""
            )
        except (MLClientError, Exception):
            # Se falhar, continua com descrição vazia
            pass

        # Extrair atributos
        attributes = []
        for attr in item.get("attributes", []):
            name = attr.get("name", "")
            value = attr.get("value_name", "")
            if name and value:
                attributes.append(f"{name}: {value}")

        return {
            "title": item.get("title", "") or title_fallback,
            "description": description[:2000],  # limitar tamanho
            "attributes": attributes[:20],
        }
    except Exception as exc:
        logger.warning("Falha ao buscar info do item %s: %s", mlb_id, exc)
        return {
            "title": title_fallback,
            "description": "",
            "attributes": [],
        }
