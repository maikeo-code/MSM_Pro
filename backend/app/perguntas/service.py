"""Service layer para sincronização, listagem e resposta de perguntas Q&A.

Responsável pela:
- Sincronização de perguntas da API ML com o banco local (upsert)
- Listagem com filtros, busca e paginação
- Envio de respostas com tracking de sucesso/erro
- Estatísticas agregadas por usuário e conta
"""

import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import MLAccount, User
from app.core.database import AsyncSessionLocal
from app.mercadolivre.client import MLClient, MLClientError
from app.perguntas.models import Question, QuestionAnswer, QASuggestionLog
from app.vendas.models import Listing

logger = logging.getLogger(__name__)


async def sync_questions_for_account(
    db: AsyncSession,
    account: MLAccount,
    statuses: list[str] | None = None,
) -> dict:
    """
    Sincroniza perguntas de uma conta ML para o banco local.
    Para cada status, busca até 50 perguntas da API ML.
    Upsert: se ml_question_id já existe, atualiza; senão, cria.

    Args:
        db: Sessão de banco de dados
        account: MLAccount a sincronizar
        statuses: Lista de status a buscar (padrão: UNANSWERED, ANSWERED)

    Returns:
        dict com chaves: synced (total), new (criadas), updated (atualizadas), errors
    """
    if statuses is None:
        statuses = ["UNANSWERED", "ANSWERED"]

    synced = 0
    new = 0
    updated = 0
    errors = 0

    if not account.access_token:
        logger.warning("Conta %s sem token de acesso", account.id)
        return {"synced": 0, "new": 0, "updated": 0, "errors": 1}

    try:
        async with MLClient(account.access_token) as client:
            for status in statuses:
                try:
                    # Busca perguntas da API ML
                    data = await client.get_received_questions(
                        status=status, offset=0, limit=50
                    )
                    questions_api = data.get("questions", [])
                    logger.info(
                        "Sincronizando %d perguntas status=%s da conta %s",
                        len(questions_api),
                        status,
                        account.id,
                    )

                    for q in questions_api:
                        try:
                            # Extrai campos principais
                            ml_question_id = q.get("id")
                            text = q.get("text", "")
                            mlb_id = q.get("item_id", "")
                            item_title = q.get("item_title")
                            date_created_str = q.get("date_created")
                            answer_data = q.get("answer", {})

                            # Parse da data
                            if date_created_str:
                                try:
                                    date_created = datetime.fromisoformat(
                                        date_created_str.replace("Z", "+00:00")
                                    )
                                except Exception:
                                    date_created = datetime.now(timezone.utc)
                            else:
                                date_created = datetime.now(timezone.utc)

                            # Extrai dados do comprador
                            buyer_data = q.get("from", {})
                            buyer_id = buyer_data.get("id")
                            buyer_nickname = buyer_data.get("nickname")

                            # Tenta encontrar listing local e buscar thumbnail
                            listing_id = None
                            thumbnail = None
                            if mlb_id:
                                result = await db.execute(
                                    select(Listing.id, Listing.thumbnail).where(Listing.mlb_id == mlb_id)
                                )
                                row = result.first()
                                if row:
                                    listing_id, thumbnail = row

                            # Se não encontrou thumbnail local, busca via API ML
                            if not thumbnail and mlb_id:
                                try:
                                    item_data = await client.get_item(mlb_id)
                                    thumbnail = item_data.get("secure_thumbnail") or item_data.get("thumbnail")
                                except Exception as e:
                                    logger.debug("Erro ao buscar thumbnail via API para %s: %s", mlb_id, e)

                            # Trata resposta (se houver)
                            answer_text = None
                            answer_date = None
                            if isinstance(answer_data, dict) and answer_data:
                                answer_text = answer_data.get("text")
                                answer_date_str = answer_data.get("date_created")
                                if answer_date_str:
                                    try:
                                        answer_date = datetime.fromisoformat(
                                            answer_date_str.replace("Z", "+00:00")
                                        )
                                    except Exception:
                                        answer_date = None

                            # Upsert: busca pergunta existente por ml_question_id
                            result = await db.execute(
                                select(Question).where(
                                    Question.ml_question_id == ml_question_id
                                )
                            )
                            question = result.scalar_one_or_none()

                            if question:
                                # UPDATE
                                question.status = status
                                question.answer_text = answer_text
                                question.answer_date = answer_date
                                if answer_text:
                                    question.answer_source = "ml_direct"
                                question.item_thumbnail = thumbnail
                                question.synced_at = datetime.now(timezone.utc)
                                question.updated_at = datetime.now(timezone.utc)
                                updated += 1
                            else:
                                # CREATE
                                question = Question(
                                    ml_question_id=ml_question_id,
                                    ml_account_id=account.id,
                                    listing_id=listing_id,
                                    mlb_id=mlb_id,
                                    item_title=item_title,
                                    item_thumbnail=thumbnail,
                                    text=text,
                                    status=status,
                                    buyer_id=buyer_id,
                                    buyer_nickname=buyer_nickname,
                                    date_created=date_created,
                                    answer_text=answer_text,
                                    answer_date=answer_date,
                                    answer_source="ml_direct" if answer_text else None,
                                    synced_at=datetime.now(timezone.utc),
                                )
                                db.add(question)
                                new += 1

                            synced += 1

                        except Exception as exc:
                            logger.error(
                                "Erro ao processar pergunta %s: %s",
                                q.get("id"),
                                exc,
                                exc_info=True,
                            )
                            errors += 1
                            continue

                except MLClientError as exc:
                    logger.error(
                        "Erro ML ao sincronizar status=%s da conta %s: %s",
                        status,
                        account.id,
                        exc,
                        exc_info=True,
                    )
                    errors += 1
                    continue

        # Commit final
        await db.commit()
        logger.info(
            "Sincronização concluída para conta %s: "
            "synced=%d, new=%d, updated=%d, errors=%d",
            account.id,
            synced,
            new,
            updated,
            errors,
        )

    except Exception as exc:
        logger.error(
            "Erro geral ao sincronizar conta %s: %s",
            account.id,
            exc,
            exc_info=True,
        )
        errors += 1

    return {"synced": synced, "new": new, "updated": updated, "errors": errors}


async def sync_all_questions() -> dict:
    """
    Sincroniza perguntas de TODAS as contas ML ativas.
    Usado pela Celery task diária.

    Returns:
        dict com chaves: total_synced, accounts_processed, errors
    """
    db = AsyncSessionLocal()
    total_synced = 0
    total_new = 0
    total_updated = 0
    total_errors = 0
    accounts_processed = 0

    try:
        # Busca todas as contas ativas
        result = await db.execute(
            select(MLAccount).where(
                MLAccount.is_active == True,  # noqa: E712
                MLAccount.access_token.isnot(None),
            )
        )
        accounts = result.scalars().all()
        logger.info("Sincronizando perguntas de %d contas", len(accounts))

        for account in accounts:
            try:
                stats = await sync_questions_for_account(db, account)
                total_synced += stats.get("synced", 0)
                total_new += stats.get("new", 0)
                total_updated += stats.get("updated", 0)
                total_errors += stats.get("errors", 0)
                accounts_processed += 1
            except Exception as exc:
                logger.error(
                    "Erro ao sincronizar conta %s: %s",
                    account.id,
                    exc,
                    exc_info=True,
                )
                total_errors += 1

        logger.info(
            "Sync concluída: synced=%d, new=%d, updated=%d, errors=%d, accounts=%d",
            total_synced,
            total_new,
            total_updated,
            total_errors,
            accounts_processed,
        )

    except Exception as exc:
        logger.error("Erro geral no sync de todas as perguntas: %s", exc, exc_info=True)
        total_errors += 1
    finally:
        await db.close()

    return {
        "total_synced": total_synced,
        "new": total_new,
        "updated": total_updated,
        "accounts_processed": accounts_processed,
        "errors": total_errors,
    }


async def list_questions_from_db(
    db: AsyncSession,
    user_id: UUID,
    status: str | None = None,
    ml_account_id: UUID | None = None,
    mlb_id: str | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Question], int]:
    """
    Lista perguntas do banco local com filtros.

    Args:
        db: Sessão de banco
        user_id: UUID do usuário
        status: Filtro de status (UNANSWERED, ANSWERED, etc)
        ml_account_id: Filtro de conta ML (opcional)
        mlb_id: Filtro de anúncio específico (opcional)
        search: Busca em text ou buyer_nickname (ILIKE)
        offset: Paginação
        limit: Limite de resultados

    Returns:
        tuple com (lista de Question objects, total de registros)
    """
    # Base query: perguntas das contas do usuário
    base_query = select(Question).join(
        MLAccount, Question.ml_account_id == MLAccount.id
    )

    # Filtro de usuário (obrigatório)
    filters = [MLAccount.user_id == user_id]

    # Filtros opcionais
    if status:
        filters.append(Question.status == status)

    if ml_account_id:
        filters.append(Question.ml_account_id == ml_account_id)

    if mlb_id:
        filters.append(Question.mlb_id == mlb_id)

    if search:
        search_pattern = f"%{search}%"
        filters.append(
            or_(
                Question.text.ilike(search_pattern),
                Question.buyer_nickname.ilike(search_pattern),
            )
        )

    # Aplica filtros
    query = base_query.where(and_(*filters))

    # Count total (sem offset/limit)
    count_result = await db.execute(
        select(func.count(Question.id)).where(and_(*filters)).select_from(Question)
    )
    total = count_result.scalar() or 0

    # Busca paginada, ordenada por data mais recente
    query = query.order_by(desc(Question.date_created))
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    questions = result.scalars().all()

    return questions, total


async def answer_question_and_track(
    db: AsyncSession,
    question_id: UUID,
    text: str,
    account: MLAccount,
    source: str = "manual",
    template_id: UUID | None = None,
    suggestion_was_edited: bool = False,
) -> dict:
    """
    Responde uma pergunta via API ML e registra no banco.

    Args:
        db: Sessão de banco
        question_id: UUID da pergunta local
        text: Texto da resposta
        account: MLAccount que fará a resposta
        source: Origem (manual, ai, template)
        template_id: ID do template (se source=template)
        suggestion_was_edited: Se a sugestão IA foi editada antes de usar

    Returns:
        dict com status, message e response (ou error_message)
    """
    try:
        # Busca pergunta
        result = await db.execute(
            select(Question).where(Question.id == question_id)
        )
        question = result.scalar_one_or_none()

        if not question:
            return {
                "status": "error",
                "message": "Pergunta não encontrada",
                "error_code": "NOT_FOUND",
            }

        # Valida propriedade: pergunta deve pertencer à conta
        if question.ml_account_id != account.id:
            return {
                "status": "error",
                "message": "Pergunta não pertence a esta conta",
                "error_code": "FORBIDDEN",
            }

        # Envia resposta via API ML
        try:
            async with MLClient(account.access_token) as client:
                response = await client.answer_question(
                    question.ml_question_id, text
                )
        except MLClientError as exc:
            # Falha no envio — registra tentativa com erro
            logger.error(
                "Erro ML ao responder pergunta %s (ml_id=%s): %s",
                question_id,
                question.ml_question_id,
                exc,
            )
            qa = QuestionAnswer(
                question_id=question_id,
                text=text,
                status="failed",
                source=source,
                template_id=template_id,
                error_message=str(exc),
                created_at=datetime.now(timezone.utc),
            )
            db.add(qa)
            await db.commit()

            return {
                "status": "error",
                "message": f"Falha ao enviar resposta: {str(exc)}",
                "error_code": "ML_API_ERROR",
            }

        # Sucesso: atualiza pergunta e registra resposta
        now = datetime.now(timezone.utc)
        question.answer_text = text
        question.answer_date = now
        question.answer_source = source
        question.status = "ANSWERED"
        question.updated_at = now

        # Registra resposta em QuestionAnswer
        qa = QuestionAnswer(
            question_id=question_id,
            text=text,
            status="sent",
            source=source,
            template_id=template_id,
            sent_at=now,
            created_at=now,
        )
        db.add(qa)

        # Atualiza suggestion log se era IA
        if source == "ai" and question.ai_suggested_at:
            result_log = await db.execute(
                select(QASuggestionLog).where(
                    QASuggestionLog.question_id == question_id,
                    QASuggestionLog.suggested_answer == question.ai_suggestion_text,
                )
            )
            suggestion_log = result_log.scalar_one_or_none()
            if suggestion_log:
                suggestion_log.was_used = True
                if suggestion_was_edited:
                    suggestion_log.was_edited = True

        await db.commit()

        logger.info(
            "Resposta enviada para pergunta %s (ml_id=%s) via %s",
            question_id,
            question.ml_question_id,
            source,
        )

        return {
            "status": "success",
            "message": "Resposta enviada com sucesso",
            "response": response,
        }

    except Exception as exc:
        logger.error(
            "Erro geral ao responder pergunta %s: %s",
            question_id,
            exc,
            exc_info=True,
        )
        return {
            "status": "error",
            "message": f"Erro ao processar resposta: {str(exc)}",
            "error_code": "INTERNAL_ERROR",
        }


async def get_question_stats(
    db: AsyncSession,
    user_id: UUID,
    ml_account_id: UUID | None = None,
) -> dict:
    """
    Retorna estatísticas de perguntas para o usuário.

    Args:
        db: Sessão de banco
        user_id: UUID do usuário
        ml_account_id: Filtro de conta (opcional)

    Returns:
        dict com total, unanswered, answered, urgent, avg_response_time_hours, by_account
    """
    try:
        # Base query
        base_where = [
            Question.ml_account_id.in_(
                select(MLAccount.id).where(MLAccount.user_id == user_id)
            )
        ]

        if ml_account_id:
            base_where.append(Question.ml_account_id == ml_account_id)

        # Total de perguntas
        total_result = await db.execute(
            select(func.count(Question.id)).where(and_(*base_where))
        )
        total = total_result.scalar() or 0

        # Não respondidas
        unanswered_result = await db.execute(
            select(func.count(Question.id)).where(
                and_(
                    *base_where,
                    Question.status == "UNANSWERED",
                )
            )
        )
        unanswered = unanswered_result.scalar() or 0

        # Respondidas
        answered_result = await db.execute(
            select(func.count(Question.id)).where(
                and_(
                    *base_where,
                    Question.status == "ANSWERED",
                )
            )
        )
        answered = answered_result.scalar() or 0

        # Urgentes (não respondidas há > 24h)
        cutoff_date = datetime.now(timezone.utc) - timedelta(hours=24)
        urgent_result = await db.execute(
            select(func.count(Question.id)).where(
                and_(
                    *base_where,
                    Question.status == "UNANSWERED",
                    Question.date_created < cutoff_date,
                )
            )
        )
        urgent = urgent_result.scalar() or 0

        # Tempo médio de resposta (para perguntas respondidas)
        avg_response_time = None
        if answered > 0:
            # Calcula diferença em segundos, converte para horas
            result = await db.execute(
                select(
                    func.avg(
                        (func.extract("epoch", Question.answer_date) -
                         func.extract("epoch", Question.date_created)) / 3600
                    )
                ).where(
                    and_(
                        *base_where,
                        Question.status == "ANSWERED",
                        Question.answer_date.isnot(None),
                    )
                )
            )
            avg_response_time = result.scalar()
            if avg_response_time:
                avg_response_time = float(avg_response_time)

        # Agregação por conta
        by_account = {}
        accounts_result = await db.execute(
            select(
                MLAccount.nickname,
                func.count(Question.id),
            )
            .join(Question, MLAccount.id == Question.ml_account_id)
            .where(and_(*base_where))
            .group_by(MLAccount.id, MLAccount.nickname)
        )
        for nickname, count in accounts_result.all():
            by_account[nickname] = count

        return {
            "total": total,
            "unanswered": unanswered,
            "answered": answered,
            "urgent": urgent,
            "avg_response_time_hours": avg_response_time,
            "by_account": by_account,
        }

    except Exception as exc:
        logger.error(
            "Erro ao calcular estatísticas para user %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        return {
            "total": 0,
            "unanswered": 0,
            "answered": 0,
            "urgent": 0,
            "avg_response_time_hours": None,
            "by_account": {},
        }


async def get_questions_by_listing(
    db: AsyncSession,
    user_id: UUID,
    mlb_id: str,
) -> list[Question]:
    """
    Retorna histórico de Q&A de um anúncio específico.

    Args:
        db: Sessão de banco
        user_id: UUID do usuário
        mlb_id: ID do anúncio (ex: MLB1234567890)

    Returns:
        Lista de Question objects ordenadas por data crescente
    """
    try:
        result = await db.execute(
            select(Question)
            .join(
                MLAccount,
                Question.ml_account_id == MLAccount.id,
            )
            .where(
                MLAccount.user_id == user_id,
                Question.mlb_id == mlb_id,
            )
            .order_by(Question.date_created)
        )
        questions = result.scalars().all()
        return questions

    except Exception as exc:
        logger.error(
            "Erro ao buscar perguntas do anúncio %s: %s",
            mlb_id,
            exc,
            exc_info=True,
        )
        return []
