"""
Lógica assíncrona para sincronização de perguntas Q&A.

Funções exportadas:
  - _sync_questions_async: sincroniza perguntas de todas as contas ML ativas
"""
import logging

from app.perguntas.service import sync_all_questions

logger = logging.getLogger(__name__)


async def _sync_questions_async() -> dict:
    """
    Sincroniza perguntas de TODAS as contas ML ativas.

    Utilizado pela task Celery diária (ou a cada 15 minutos se configurado).

    Returns:
        dict com chaves:
            - total_synced: Total de perguntas sincronizadas
            - new: Novas perguntas inseridas
            - updated: Perguntas atualizadas
            - accounts_processed: Número de contas processadas
            - errors: Total de erros encontrados
    """
    return await sync_all_questions()
