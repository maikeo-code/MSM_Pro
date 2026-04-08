"""
Health check independente do pipeline de sincronização.

Objetivo: detectar quando o sistema está silenciosamente quebrado.
Se nenhum listing_snapshot foi criado nas últimas 24h E há contas ML
ativas, algo está errado (Celery worker travado, bug de event loop,
token expirado sem alertar, etc.) — notifica o usuário imediatamente.

Esta task NÃO depende do refresh de token nem da API do Mercado Livre.
É uma verificação puramente local no banco, então funciona mesmo quando
todo o resto do pipeline está quebrado.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.auth.models import MLAccount, User
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.email import is_smtp_configured, send_alert_email
from app.core.models import SyncLog
from app.notifications.service import create_notification
from app.vendas.models import ListingSnapshot, Order

logger = logging.getLogger(__name__)


async def _check_sync_health_async() -> dict:
    """
    Verifica se o pipeline de sincronização está saudável.

    Critério: nas últimas 24h, deve haver pelo menos 1 listing_snapshot
    para cada conta ML ativa. Caso contrário, cria notificação de alerta
    para o usuário dono da conta.
    """
    async with AsyncSessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        # 1. Conta total de snapshots nas últimas 24h
        total_snaps_q = await db.execute(
            select(func.count(ListingSnapshot.id)).where(
                ListingSnapshot.captured_at >= cutoff
            )
        )
        total_snaps = total_snaps_q.scalar() or 0

        # 2. Contas ML ativas
        accounts_q = await db.execute(
            select(MLAccount).where(MLAccount.is_active == True)  # noqa: E712
        )
        accounts = accounts_q.scalars().all()
        active_count = len(accounts)

        result = {
            "snapshots_last_24h": total_snaps,
            "active_accounts": active_count,
            "healthy": True,
            "alerts_created": 0,
        }

        # 3. Se há contas ativas mas zero snapshots → ALERTA GLOBAL
        if active_count > 0 and total_snaps == 0:
            result["healthy"] = False
            logger.error(
                "SYNC HEALTH CHECK FALHOU: %d contas ativas, 0 snapshots em 24h",
                active_count,
            )

            # Notificar TODOS os donos de conta ML ativa
            user_ids_seen: set = set()
            user_emails: list[str] = []
            for acc in accounts:
                if acc.user_id in user_ids_seen:
                    continue
                user_ids_seen.add(acc.user_id)

                await create_notification(
                    db,
                    user_id=acc.user_id,
                    type="sync_failed",
                    title="Sincronização não está rodando",
                    message=(
                        "Detectamos que nenhuma sincronização foi concluída "
                        "nas últimas 24 horas. Os dados de vendas, preços e "
                        "estoque podem estar desatualizados. Verifique se as "
                        "contas do Mercado Livre estão conectadas ou contate "
                        "o suporte."
                    ),
                    action_url="/configuracoes",
                )
                result["alerts_created"] += 1

                # Coleta email do dono para notificação por SMTP
                user_row = await db.execute(
                    select(User).where(User.id == acc.user_id)
                )
                user_obj = user_row.scalar_one_or_none()
                if user_obj and user_obj.email:
                    user_emails.append(user_obj.email)

            await db.commit()

            # Email fallback independente do frontend
            if is_smtp_configured() and user_emails:
                body = (
                    "MSM_Pro detectou que o pipeline de sincronização com o "
                    "Mercado Livre NÃO concluiu nenhum snapshot nas últimas "
                    f"24 horas (contas ativas: {active_count}).\n\n"
                    "Possíveis causas:\n"
                    "  • Worker do Celery travado ou crashando silenciosamente\n"
                    "  • Token OAuth expirado (reconecte a conta)\n"
                    "  • API do Mercado Livre fora do ar\n\n"
                    "Ação recomendada: abra o dashboard em "
                    f"{settings.frontend_url} → Configurações → Contas ML "
                    "e verifique o status de cada conta. Se tudo parecer OK "
                    "lá, reinicie o serviço backend no Railway."
                )
                for email in user_emails:
                    try:
                        sent = send_alert_email(
                            to=email,
                            subject="[MSM_Pro] Sincronização não rodou em 24h",
                            body=body,
                        )
                        if sent:
                            result["alerts_created"] += 0  # já contado
                            logger.info("Email de health check enviado para %s", email)
                    except Exception as exc:
                        logger.error("Falha ao enviar health email para %s: %s", email, exc)
            elif not is_smtp_configured():
                logger.warning(
                    "Health check detectou falha mas SMTP não configurado — "
                    "apenas notificação in-app criada."
                )
        else:
            logger.info(
                "Sync health OK: %d snapshots em 24h para %d contas",
                total_snaps,
                active_count,
            )

        return result


async def _runtime_watcher_async() -> dict:
    """
    Verificação multi-dimensional do pipeline (a cada 2h via Celery beat).

    Diferente do _check_sync_health_async (que só vê snapshots), este
    olha 6 dimensões ao mesmo tempo:
    1. snapshots novos nas últimas 24h
    2. orders novos nas últimas 24h
    3. last_token_refresh_at recente (proxy de "task de tokens rodou")
    4. contas com needs_reauth=True
    5. contas com token_refresh_failures > 0
    6. taxa de falha em sync_logs nas últimas 6h

    Cria UMA notificação por anomalia detectada (não spam).
    """
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_12h = now - timedelta(hours=12)
    cutoff_6h = now - timedelta(hours=6)

    anomalies: list[dict] = []

    async with AsyncSessionLocal() as db:
        # 1. snapshots
        snaps_q = await db.execute(
            select(func.count(ListingSnapshot.id)).where(
                ListingSnapshot.captured_at >= cutoff_24h
            )
        )
        snaps_24h = snaps_q.scalar() or 0

        # 2. orders
        orders_q = await db.execute(
            select(func.count(Order.id)).where(Order.created_at >= cutoff_24h)
        )
        orders_24h = orders_q.scalar() or 0

        # 3. contas e tokens
        accounts_q = await db.execute(
            select(MLAccount).where(MLAccount.is_active == True)  # noqa: E712
        )
        accounts = accounts_q.scalars().all()
        active_count = len(accounts)

        accounts_needing_reauth = [a for a in accounts if a.needs_reauth]
        accounts_with_failures = [
            a for a in accounts
            if (a.token_refresh_failures or 0) > 0 and not a.needs_reauth
        ]

        # 4. last_token_refresh_at congelado >12h
        # Quando o cron de refresh está rodando, esse campo deveria atualizar
        # pelo menos 1x a cada execução de _refresh_expired_tokens_async (a cada 30min).
        # Tolerância: se >12h sem refresh em todas as contas, é anomalia.
        stale_refresh = [
            a for a in accounts
            if a.last_token_refresh_at
            and a.last_token_refresh_at < cutoff_12h
        ]

        # 5. taxa de falha em sync_logs últimas 6h
        sync_logs_q = await db.execute(
            select(SyncLog.status, func.count(SyncLog.id))
            .where(SyncLog.started_at >= cutoff_6h)
            .group_by(SyncLog.status)
        )
        sync_status_counts = {row[0]: row[1] for row in sync_logs_q.all()}
        total_logs = sum(sync_status_counts.values())
        failed_logs = sync_status_counts.get("failed", 0)
        failure_rate = (failed_logs / total_logs * 100) if total_logs > 0 else 0

        # ── Avaliar anomalias ──
        if active_count > 0 and snaps_24h == 0:
            anomalies.append({
                "code": "no_snapshots_24h",
                "severity": "critical",
                "title": "Sem snapshots de listings em 24h",
                "detail": f"{active_count} contas ativas, 0 snapshots. Pipeline travado.",
            })

        if active_count > 0 and orders_24h == 0:
            anomalies.append({
                "code": "no_orders_24h",
                "severity": "high",
                "title": "Sem pedidos novos em 24h",
                "detail": "Pode ser baixo volume real, ou sync_orders quebrado.",
            })

        if accounts_needing_reauth:
            anomalies.append({
                "code": "needs_reauth",
                "severity": "critical",
                "title": f"{len(accounts_needing_reauth)} conta(s) precisam reconectar",
                "detail": ", ".join(a.nickname for a in accounts_needing_reauth),
            })

        if accounts_with_failures:
            anomalies.append({
                "code": "token_failures",
                "severity": "medium",
                "title": f"{len(accounts_with_failures)} conta(s) com falhas de refresh",
                "detail": ", ".join(
                    f"{a.nickname} ({a.token_refresh_failures})"
                    for a in accounts_with_failures
                ),
            })

        if stale_refresh and len(stale_refresh) == active_count:
            anomalies.append({
                "code": "stale_token_refresh",
                "severity": "high",
                "title": "Cron de refresh de tokens parece parado",
                "detail": "Nenhuma conta teve refresh nas últimas 12h. "
                          "Esperado: a cada 30min.",
            })

        if total_logs >= 3 and failure_rate >= 50:
            anomalies.append({
                "code": "high_failure_rate",
                "severity": "high",
                "title": f"{failure_rate:.0f}% das tasks falharam nas últimas 6h",
                "detail": f"{failed_logs} falhas de {total_logs} execuções. Verifique logs.",
            })

        result = {
            "checked_at": now.isoformat(),
            "snapshots_24h": snaps_24h,
            "orders_24h": orders_24h,
            "active_accounts": active_count,
            "needs_reauth": len(accounts_needing_reauth),
            "stale_refresh": len(stale_refresh),
            "sync_logs_6h": sync_status_counts,
            "anomalies": anomalies,
            "healthy": len(anomalies) == 0,
        }

        if not anomalies:
            logger.info("[runtime-watcher] OK — todos os indicadores verdes")
            return result

        logger.warning(
            "[runtime-watcher] %d anomalias detectadas: %s",
            len(anomalies),
            [a["code"] for a in anomalies],
        )

        # Cria UMA notificação consolidada por usuário
        user_ids_seen: set = set()
        user_emails: list[str] = []
        for acc in accounts:
            if acc.user_id in user_ids_seen:
                continue
            user_ids_seen.add(acc.user_id)

            critical_count = sum(1 for a in anomalies if a["severity"] == "critical")
            high_count = sum(1 for a in anomalies if a["severity"] == "high")
            title = (
                f"{critical_count} crítico(s) + {high_count} alto(s) detectados"
                if critical_count
                else f"{len(anomalies)} anomalia(s) no pipeline"
            )
            msg_lines = [a["title"] + ": " + a["detail"] for a in anomalies]

            await create_notification(
                db,
                user_id=acc.user_id,
                type="runtime_anomaly",
                title=title,
                message="\n".join(msg_lines),
                action_url="/configuracoes",
            )

            user_row = await db.execute(select(User).where(User.id == acc.user_id))
            user_obj = user_row.scalar_one_or_none()
            if user_obj and user_obj.email:
                user_emails.append(user_obj.email)

        await db.commit()

        # Email só para anomalias de severidade critical ou high
        critical_or_high = [
            a for a in anomalies if a["severity"] in ("critical", "high")
        ]
        if critical_or_high and is_smtp_configured() and user_emails:
            body_lines = [
                "O runtime-watcher do MSM_Pro detectou anomalias no pipeline:",
                "",
            ]
            for a in critical_or_high:
                body_lines.append(f"  [{a['severity'].upper()}] {a['title']}")
                body_lines.append(f"    {a['detail']}")
                body_lines.append("")
            body_lines.extend([
                "Ação recomendada: abra o dashboard em "
                f"{settings.frontend_url}/configuracoes",
                "",
                "Esta verificação roda a cada 2 horas.",
            ])
            body = "\n".join(body_lines)
            for email in user_emails:
                try:
                    send_alert_email(
                        to=email,
                        subject=f"[MSM_Pro] {len(critical_or_high)} anomalia(s) no pipeline",
                        body=body,
                    )
                except Exception as exc:
                    logger.error("Falha ao enviar email runtime-watcher para %s: %s", email, exc)

        return result
