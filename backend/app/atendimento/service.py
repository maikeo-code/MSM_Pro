"""
Serviço de Atendimento Unificado.

Agrega perguntas, reclamações, mensagens pós-venda e devoluções de todas as
contas ML ativas do usuário numa lista única, ordenada por data decrescente.
O módulo de perguntas existente (app.perguntas) não é modificado — este módulo
é um wrapper de agregação.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import MLAccount
from app.core.config import settings
from app.mercadolivre.client import MLClient, MLClientError
from app.atendimento.schemas import (
    AISuggestionOut,
    AtendimentoItem,
    AtendimentoListOut,
    AtendimentoStatsOut,
)

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL_HAIKU = "claude-haiku-4-20250514"


# ---------------------------------------------------------------------------
# Helpers de parsing
# ---------------------------------------------------------------------------

def _parse_dt(value: str | None) -> datetime:
    """Converte string ISO 8601 (com ou sem timezone) para datetime UTC."""
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        # ML retorna com timezone explícito na maioria dos casos
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return datetime.min.replace(tzinfo=timezone.utc)


def _requires_action(type_: str, status: str) -> bool:
    """Retorna True se o item precisa de ação do vendedor."""
    status_lower = status.lower()
    if type_ == "pergunta":
        return status_lower in ("unanswered", "under_review")
    if type_ in ("reclamacao", "devolucao"):
        return status_lower in ("open", "opened", "claim_open")
    if type_ == "mensagem":
        return status_lower in ("unread", "pending")
    return False


# ---------------------------------------------------------------------------
# Parsers por tipo
# ---------------------------------------------------------------------------

def _parse_questions(questions: list[dict], account: MLAccount) -> list[AtendimentoItem]:
    """Converte perguntas ML em AtendimentoItem."""
    items: list[AtendimentoItem] = []
    for q in questions:
        status = str(q.get("status", "")).lower()
        text = q.get("text") or ""
        from_user = q.get("from") or {}
        item_data = q.get("item_id") or q.get("item", {})
        item_id = str(item_data) if isinstance(item_data, (str, int)) else str(item_data.get("id", ""))
        item_title = None
        if isinstance(item_data, dict):
            item_title = item_data.get("title")

        item = AtendimentoItem(
            id=str(q.get("id", "")),
            type="pergunta",
            status=status,
            date_created=_parse_dt(q.get("date_created")),
            text=text,
            from_user=from_user if isinstance(from_user, dict) else {},
            item_id=item_id or None,
            item_title=item_title,
            item_thumbnail=None,
            order_id=None,
            last_message=None,
            requires_action=_requires_action("pergunta", status),
            account_id=str(account.id),
            account_nickname=account.nickname,
        )
        items.append(item)
    return items


def _parse_claims(
    claims: list[dict],
    claim_type: str,
    account: MLAccount,
    seen_ids: set[str] | None = None,
) -> list[AtendimentoItem]:
    """
    Converte claims/devoluções ML em AtendimentoItem.

    Args:
        claims: Lista de claims do ML
        claim_type: "reclamacao" ou "devolucao"
        account: Conta ML
        seen_ids: Set para deduplicação entre múltiplas buscas (ex: múltiplos statuses)
    """
    if seen_ids is None:
        seen_ids = set()

    items: list[AtendimentoItem] = []
    for c in claims:
        claim_id = str(c.get("id", ""))

        # Deduplicação
        if claim_id in seen_ids:
            continue
        seen_ids.add(claim_id)

        status = str(c.get("status", "")).lower()
        # Claims têm "reason_id" como texto da reclamação
        text = c.get("reason_id") or c.get("subject") or c.get("description") or "Sem descrição"
        # Comprador pode estar em "players" ou "buyer"
        buyer = None
        players = c.get("players", [])
        if isinstance(players, list):
            for p in players:
                if isinstance(p, dict) and p.get("role") == "complainant":
                    buyer = {"id": p.get("user_id"), "nickname": p.get("user_id")}
                    break
        if not buyer:
            buyer_raw = c.get("buyer", {})
            if buyer_raw:
                buyer = {"id": buyer_raw.get("id"), "nickname": buyer_raw.get("nickname")}

        resource = c.get("resource", {}) or {}
        item_id = str(resource.get("item_id", "")) or None
        order_id = str(resource.get("order_id", "")) if resource.get("order_id") else None

        item = AtendimentoItem(
            id=claim_id,
            type=claim_type,
            status=status,
            date_created=_parse_dt(c.get("date_created")),
            text=text,
            from_user=buyer,
            item_id=item_id,
            item_title=None,
            item_thumbnail=None,
            order_id=order_id,
            last_message=None,
            requires_action=_requires_action(claim_type, status),
            account_id=str(account.id),
            account_nickname=account.nickname,
        )
        items.append(item)
    return items


def _parse_message_packs(packs: list[dict], account: MLAccount) -> list[AtendimentoItem]:
    """Converte message packs ML em AtendimentoItem."""
    items: list[AtendimentoItem] = []
    for p in packs:
        status = str(p.get("status", "read")).lower()
        # Último texto disponível
        last_msg = p.get("last_message") or {}
        text = ""
        if isinstance(last_msg, dict):
            text = last_msg.get("text", "") or ""
        elif isinstance(last_msg, str):
            text = last_msg

        from_user = p.get("from") or p.get("buyer") or {}
        order_id = str(p.get("order_id", "")) if p.get("order_id") else None
        pack_id = str(p.get("id", "") or p.get("pack_id", ""))

        item = AtendimentoItem(
            id=pack_id,
            type="mensagem",
            status=status,
            date_created=_parse_dt(p.get("date_created") or p.get("last_updated")),
            text=text or "Conversa pós-venda",
            from_user=from_user if isinstance(from_user, dict) else {},
            item_id=None,
            item_title=None,
            item_thumbnail=None,
            order_id=order_id,
            last_message=text or None,
            requires_action=_requires_action("mensagem", status),
            account_id=str(account.id),
            account_nickname=account.nickname,
        )
        items.append(item)
    return items


# ---------------------------------------------------------------------------
# Função principal de agregação
# ---------------------------------------------------------------------------

async def get_all_atendimentos(
    db: AsyncSession,
    user: object,
    status_filter: Optional[str] = None,
    type_filter: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
) -> AtendimentoListOut:
    """
    Agrega perguntas, reclamações, mensagens e devoluções de todas as contas
    ML ativas do usuário.

    Args:
        db: Sessão async do banco.
        user: Objeto User autenticado.
        status_filter: Filtrar por status (ex: "unanswered", "open").
        type_filter: Filtrar por tipo ("pergunta", "reclamacao", "mensagem", "devolucao").
        offset: Offset para paginação.
        limit: Quantidade de itens por página.

    Returns:
        AtendimentoListOut com lista unificada e contadores por tipo.
    """
    result = await db.execute(
        select(MLAccount).where(
            MLAccount.user_id == user.id,
            MLAccount.is_active == True,  # noqa: E712
        )
    )
    accounts = result.scalars().all()

    all_items: list[AtendimentoItem] = []
    by_type: dict[str, int] = {
        "perguntas": 0,
        "reclamacoes": 0,
        "mensagens": 0,
        "devolucoes": 0,
    }
    seen_claim_ids: set[str] = set()  # Deduplicação de claims (ao buscar múltiplos statuses)

    for account in accounts:
        if not account.access_token:
            continue

        ml_user_id = account.ml_user_id

        async with MLClient(account.access_token) as client:
            # --- Perguntas ---
            if type_filter is None or type_filter == "pergunta":
                q_status = status_filter.upper() if status_filter else "UNANSWERED"
                # Normaliza status para perguntas (ML usa maiúsculas)
                if q_status.lower() in ("open", "unanswered"):
                    q_status = "UNANSWERED"
                elif q_status.lower() in ("answered", "closed"):
                    q_status = "ANSWERED"
                try:
                    q_data = await client.get_received_questions(
                        status=q_status, limit=50
                    )
                    questions = q_data.get("questions", [])
                    parsed_q = _parse_questions(questions, account)
                    all_items.extend(parsed_q)
                    by_type["perguntas"] += len(parsed_q)
                except Exception as exc:
                    logger.error(
                        "Atendimento: falha ao buscar perguntas conta=%s user=%s: %s",
                        account.id,
                        user.id,
                        exc,
                    )

            # --- Reclamações ---
            if type_filter is None or type_filter == "reclamacao":
                # Se status_filter especificado, buscar apenas aquele
                # Caso contrário, buscar múltiplos statuses relevantes
                claim_statuses_to_search = [status_filter] if status_filter else [
                    "open",
                    "opened",
                    "waiting_for_seller_response",
                ]

                for cl_status in claim_statuses_to_search:
                    try:
                        cl_data = await client.get_claims(
                            seller_id=str(ml_user_id),
                            status=cl_status,
                            limit=50,
                        )
                        claims_raw = cl_data.get("data", cl_data.get("results", []))
                        # Excluir devoluções desta lista (filtramos por claim_type != "return")
                        claims_only = [
                            c for c in claims_raw
                            if c.get("claim_type", "").lower() != "return"
                        ]
                        parsed_cl = _parse_claims(claims_only, "reclamacao", account, seen_claim_ids)
                        all_items.extend(parsed_cl)
                        by_type["reclamacoes"] += len(parsed_cl)

                        logger.info(
                            "Atendimento: carregadas reclamacoes status=%s conta=%s total=%d",
                            cl_status,
                            account.id,
                            len(parsed_cl),
                        )
                    except Exception as exc:
                        logger.error(
                            "Atendimento: falha ao buscar reclamacoes status=%s conta=%s user=%s: %s",
                            cl_status,
                            account.id,
                            user.id,
                            exc,
                        )

            # --- Devoluções ---
            if type_filter is None or type_filter == "devolucao":
                try:
                    ret_data = await client.get_returns(
                        seller_id=str(ml_user_id),
                        limit=50,
                    )
                    returns_raw = ret_data.get("data", ret_data.get("results", []))
                    parsed_ret = _parse_claims(returns_raw, "devolucao", account, seen_claim_ids)
                    all_items.extend(parsed_ret)
                    by_type["devolucoes"] += len(parsed_ret)

                    logger.info(
                        "Atendimento: carregadas devolucoes conta=%s total=%d",
                        account.id,
                        len(parsed_ret),
                    )
                except Exception as exc:
                    logger.error(
                        "Atendimento: falha ao buscar devolucoes conta=%s user=%s: %s",
                        account.id,
                        user.id,
                        exc,
                    )

            # --- Mensagens pós-venda ---
            if type_filter is None or type_filter == "mensagem":
                try:
                    msg_data = await client.get_message_packs(
                        seller_id=str(ml_user_id),
                        limit=50,
                    )
                    # A API ML pode retornar em 'results', 'data', ou direto como lista
                    packs_raw = msg_data.get("results", msg_data.get("data", []))
                    if isinstance(msg_data, list):
                        packs_raw = msg_data

                    # Filtrar por status se solicitado
                    if status_filter and status_filter.lower() in ("unread", "pending"):
                        packs_raw = [
                            p for p in packs_raw
                            if str(p.get("status", "")).lower() in ("unread", "pending")
                        ]

                    parsed_msg = _parse_message_packs(packs_raw, account)
                    all_items.extend(parsed_msg)
                    by_type["mensagens"] += len(parsed_msg)

                    logger.info(
                        "Atendimento: carregadas mensagens conta=%s total=%d",
                        account.id,
                        len(parsed_msg),
                    )
                except Exception as exc:
                    logger.error(
                        "Atendimento: falha ao buscar mensagens conta=%s user=%s: %s",
                        account.id,
                        user.id,
                        exc,
                    )

    # Ordena por data_created decrescente (mais recente primeiro)
    all_items.sort(key=lambda x: x.date_created, reverse=True)

    # Enriquecer items com thumbnails dos listings locais
    if all_items:
        from app.vendas.models import Listing

        # Coletar todos os item_ids (mlb_ids) únicos
        mlb_ids = {item.item_id for item in all_items if item.item_id}

        if mlb_ids:
            # Buscar thumbnails em batch (1 query)
            listing_result = await db.execute(
                select(Listing.mlb_id, Listing.thumbnail).where(
                    Listing.mlb_id.in_(mlb_ids)
                )
            )
            thumbnail_map = {row.mlb_id: row.thumbnail for row in listing_result.all()}

            # Popular thumbnail em cada item
            for item in all_items:
                if item.item_id and item.item_id in thumbnail_map:
                    item.item_thumbnail = thumbnail_map[item.item_id]

    total = len(all_items)
    paginated = all_items[offset: offset + limit]

    return AtendimentoListOut(
        total=total,
        items=paginated,
        by_type=by_type,
    )


async def get_atendimento_stats(
    db: AsyncSession,
    user: object,
) -> AtendimentoStatsOut:
    """
    Retorna contadores por tipo e status de atendimento, sem paginação.
    Útil para badges e alertas no dashboard.
    """
    result = await get_all_atendimentos(db=db, user=user, limit=500)

    by_status: dict[str, int] = {}
    for item in result.items:
        by_status[item.status] = by_status.get(item.status, 0) + 1

    requires_action_count = sum(1 for it in result.items if it.requires_action)

    return AtendimentoStatsOut(
        total=result.total,
        requires_action=requires_action_count,
        by_type=result.by_type,
        by_status=by_status,
    )


# ---------------------------------------------------------------------------
# Responder item
# ---------------------------------------------------------------------------

async def respond_to_item(
    db: AsyncSession,
    user: object,
    item_type: str,
    item_id: str,
    text: str,
    account_id: UUID,
) -> dict:
    """
    Roteia a resposta para a API correta dependendo do tipo do item.

    Args:
        db: Sessão async do banco.
        user: Objeto User autenticado.
        item_type: "pergunta" | "reclamacao" | "mensagem" | "devolucao"
        item_id: ID do item (string).
        text: Texto da resposta.
        account_id: UUID da conta ML que responderá.

    Returns:
        Dict com success e message.

    Raises:
        ValueError: Se item_type inválido ou conta não encontrada.
        MLClientError: Se a API ML retornar erro.
    """
    # Valida a conta ML do usuário
    result = await db.execute(
        select(MLAccount).where(
            MLAccount.id == account_id,
            MLAccount.user_id == user.id,
        )
    )
    account = result.scalar_one_or_none()

    if not account or not account.access_token:
        raise ValueError("Conta ML não encontrada ou sem token ativo.")

    async with MLClient(account.access_token) as client:
        if item_type == "pergunta":
            await client.answer_question(int(item_id), text)
            return {"success": True, "message": "Pergunta respondida com sucesso."}

        elif item_type in ("reclamacao", "devolucao"):
            await client.send_claim_message(int(item_id), text)
            return {"success": True, "message": "Mensagem enviada para a reclamação."}

        elif item_type == "mensagem":
            seller_id = str(account.ml_user_id)
            await client.send_message(pack_id=item_id, text=text, seller_id=seller_id)
            return {"success": True, "message": "Mensagem enviada com sucesso."}

        else:
            raise ValueError(f"Tipo de item inválido: {item_type}")


# ---------------------------------------------------------------------------
# Sugestão IA (Claude Haiku)
# ---------------------------------------------------------------------------

async def get_ai_suggestion(
    db: AsyncSession,
    user: object,
    item_type: str,
    item_id: str,
    account_id: UUID,
) -> AISuggestionOut:
    """
    Gera sugestão de resposta via Claude Haiku com base em respostas anteriores similares.

    Estratégia:
    1. Busca o texto atual do item (pergunta ou reclamação).
    2. Busca as últimas 20 perguntas respondidas como exemplos few-shot.
    3. Chama Claude Haiku com o contexto montado.
    4. Retorna sugestão + confidence + IDs base usados.
    """
    if not settings.anthropic_api_key:
        return AISuggestionOut(
            suggestion="IA não configurada: ANTHROPIC_API_KEY ausente.",
            confidence=0.0,
            based_on=[],
        )

    # Busca a conta ML para ter o token
    result = await db.execute(
        select(MLAccount).where(
            MLAccount.id == account_id,
            MLAccount.user_id == user.id,
        )
    )
    account = result.scalar_one_or_none()

    if not account or not account.access_token:
        return AISuggestionOut(
            suggestion="Conta ML não encontrada.",
            confidence=0.0,
            based_on=[],
        )

    current_text = ""
    example_qa: list[dict] = []
    based_on_ids: list[str] = []

    async with MLClient(account.access_token) as client:
        # Texto do item atual
        try:
            if item_type == "pergunta":
                # Busca perguntas respondidas como exemplos
                answered_data = await client.get_received_questions(
                    status="ANSWERED", limit=20
                )
                answered = answered_data.get("questions", [])
                for q in answered:
                    q_text = q.get("text", "")
                    ans = q.get("answer", {})
                    ans_text = ans.get("text", "") if isinstance(ans, dict) else ""
                    if q_text and ans_text:
                        example_qa.append({"pergunta": q_text, "resposta": ans_text})
                        based_on_ids.append(str(q.get("id", "")))

                # Busca o texto da pergunta atual (nas não respondidas)
                unans_data = await client.get_received_questions(
                    status="UNANSWERED", limit=50
                )
                for q in unans_data.get("questions", []):
                    if str(q.get("id", "")) == item_id:
                        current_text = q.get("text", "")
                        break

            elif item_type in ("reclamacao", "devolucao"):
                # Para claims, busca o detalhe diretamente
                try:
                    detail = await client.get_claim_detail(int(item_id))
                    current_text = (
                        detail.get("reason_id")
                        or detail.get("subject")
                        or detail.get("description")
                        or "Reclamação sem descrição detalhada"
                    )
                except MLClientError:
                    current_text = "Detalhe da reclamação indisponível."

        except MLClientError as exc:
            logger.warning(
                "AI suggestion: falha ao buscar contexto item_type=%s item_id=%s: %s",
                item_type,
                item_id,
                exc,
            )
            current_text = "Contexto indisponível."

    if not current_text:
        current_text = f"Item de atendimento ID {item_id} do tipo {item_type}."

    # Monta prompt para Claude Haiku
    examples_text = ""
    if example_qa:
        pairs = []
        for ex in example_qa[:10]:  # Limita a 10 exemplos para economizar tokens
            pairs.append(
                f"Cliente: {ex['pergunta'][:200]}\nResposta: {ex['resposta'][:300]}"
            )
        examples_text = "\n\n".join(pairs)

    system_prompt = (
        "Você é um especialista em atendimento ao cliente para vendedores do Mercado Livre. "
        "Analise a pergunta/reclamação do cliente e gere uma resposta profissional, "
        "empática e objetiva em português brasileiro. "
        "Use os exemplos de respostas anteriores como referência de tom e formato."
    )

    user_prompt = f"""Item de atendimento atual ({item_type}):
{current_text}

"""

    if examples_text:
        user_prompt += f"""Exemplos de respostas anteriores desta conta para referência:
{examples_text}

"""

    user_prompt += "Gere uma resposta adequada para o item de atendimento acima:"

    payload = {
        "model": ANTHROPIC_MODEL_HAIKU,
        "max_tokens": 500,
        "temperature": 0.4,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            resp = await http_client.post(ANTHROPIC_API_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            suggestion_text = data["content"][0]["text"]

        # Confidence baseada em quantos exemplos temos (heurística simples)
        confidence = min(0.5 + len(example_qa) * 0.025, 0.95)

        return AISuggestionOut(
            suggestion=suggestion_text,
            confidence=round(confidence, 2),
            based_on=based_on_ids[:10],
        )

    except httpx.HTTPStatusError as e:
        logger.error("AI suggestion: erro HTTP Anthropic: %s", e)
        return AISuggestionOut(
            suggestion="Erro ao consultar IA. Tente novamente.",
            confidence=0.0,
            based_on=[],
        )
    except (httpx.RequestError, KeyError, IndexError) as e:
        logger.error("AI suggestion: erro de conexão ou parsing: %s", e)
        return AISuggestionOut(
            suggestion="Erro ao consultar IA. Tente novamente.",
            confidence=0.0,
            based_on=[],
        )
