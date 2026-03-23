"""
Lógica assíncrona para avaliação de alertas configurados.

Funções exportadas:
  - _evaluate_alerts_async: avalia todas as alert_configs ativas e dispara notificações
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def _evaluate_alerts_async():
    """
    Busca todos os alert_configs ativos, avalia cada condição e,
    se disparada, cria AlertEvent e envia email se canal = 'email'.
    """
    from app.alertas.models import AlertConfig
    from app.alertas.service import evaluate_single_alert
    from app.auth.models import User
    from app.core.email import send_alert_email

    # Import local para evitar circular import
    from app.jobs.tasks_competitors import _check_competitor_stockout

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AlertConfig).where(AlertConfig.is_active == True)  # noqa: E712
        )
        configs = result.scalars().all()

        logger.info(f"Avaliando {len(configs)} alertas ativos")

        triggered, skipped, errors_count = 0, 0, 0

        for config in configs:
            try:
                event = await evaluate_single_alert(db, config)

                if event is None:
                    skipped += 1
                    continue

                triggered += 1

                # Envia email se canal = 'email'
                if config.channel == "email":
                    # Busca o email do usuário
                    user_result = await db.execute(
                        select(User).where(User.id == config.user_id)
                    )
                    user = user_result.scalar_one_or_none()
                    if user and user.email:
                        sent = send_alert_email(
                            to=user.email,
                            subject=f"MSM_Pro — Alerta: {config.alert_type}",
                            body=event.message,
                        )
                        if sent:
                            event.sent_at = datetime.now(timezone.utc)

            except Exception as e:
                logger.error(f"Erro ao avaliar alerta {config.id}: {e}")
                errors_count += 1

        # Detectar stock-out de concorrentes (independente — com try/except separado)
        try:
            stockout_triggered = await _check_competitor_stockout(db)
            triggered += stockout_triggered
        except Exception as e:
            logger.error(f"Erro ao verificar competitor stockout: {e}")
            # Continua mesmo se stockout falhar — não afeta alertas configurados

        await db.commit()
        logger.info(
            f"Avaliação concluída: {triggered} disparados, "
            f"{skipped} sem condição, {errors_count} erros"
        )
        return {
            "success": True,
            "triggered": triggered,
            "skipped": skipped,
            "errors": errors_count,
        }
