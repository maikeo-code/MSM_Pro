"""
Lógica assíncrona para sincronização de claims (reclamações e devoluções).

Funções exportadas:
  - _sync_claims_async: sincroniza claims de todas as contas ML ativas
"""
import logging

from app.atendimento.service_claims import sync_all_claims

logger = logging.getLogger(__name__)


async def _sync_claims_async() -> dict:
    """
    Sincroniza claims de TODAS as contas ML ativas.

    Utilizado pela task Celery (agendada a cada 1 hora).

    Returns:
        dict com chaves:
            - total_synced: Total de claims sincronizadas
            - new: Novas claims inseridas
            - updated: Claims atualizadas
            - accounts_processed: Número de contas processadas
            - errors: Total de erros encontrados
    """
    return await sync_all_claims()
