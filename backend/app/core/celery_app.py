"""
Configuração central do Celery para MSM_Pro.
Define broker, backend, beat schedule e configurações gerais.
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# Instância principal do Celery
celery_app = Celery(
    "msm_pro",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Configurações gerais
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_soft_time_limit=300,  # 5 minutos soft limit
    task_time_limit=600,  # 10 minutos hard limit
)

# Beat Schedule — tarefas agendadas
celery_app.conf.beat_schedule = {
    # Sincroniza snapshots de todos os anúncios ativos diariamente às 06:00 BRT (09:00 UTC)
    "sync-all-snapshots-daily": {
        "task": "app.jobs.tasks.sync_all_snapshots",
        "schedule": crontab(hour=9, minute=0),
        "options": {
            "expires": 3600,  # Task expira em 1h se não executar
            "retry": True,
            "retry_policy": {
                "max_retries": 3,
                "interval_start": 10,
                "interval_step": 20,
                "interval_max": 200,
            },
        },
    },
    # Sincronização horária para anúncios com mudança recente de preço
    "sync-recent-snapshots-hourly": {
        "task": "app.jobs.tasks.sync_recent_snapshots",
        "schedule": crontab(minute=0),  # A cada hora
        "options": {
            "expires": 3600,
        },
    },
    # Renova tokens ML que vão expirar nas próximas 3 horas
    # Roda a cada 30 minutos para garantir que nunca perca a janela de renovação
    # (antes rodava 1x/hora no minuto 30, agora rodará nos minutos 0 e 30)
    # Inclui lock distribuído para evitar race condition entre workers
    "refresh-expired-tokens": {
        "task": "app.jobs.tasks.refresh_expired_tokens",
        "schedule": crontab(minute="*/30"),  # A cada 30 minutos (minutos 0, 30)
        "options": {
            "expires": 1800,  # 30 minutos (deve terminar antes da próxima execução)
            "retry": True,
            "retry_policy": {
                "max_retries": 3,
                "interval_start": 5,
                "interval_step": 10,
                "interval_max": 60,
            },
        },
    },
    # Sincroniza preços dos concorrentes às 07:00 BRT (10:00 UTC) — depois do sync principal
    "sync-competitor-snapshots-daily": {
        "task": "app.jobs.tasks.sync_competitor_snapshots",
        "schedule": crontab(hour=10, minute=0),
        "options": {
            "expires": 3600,
        },
    },
    # Sincroniza reputacao do vendedor as 06:30 BRT (09:30 UTC)
    "sync-reputation-daily": {
        "task": "app.jobs.tasks.sync_reputation",
        "schedule": crontab(hour=9, minute=30),
        "options": {
            "expires": 3600,
        },
    },
    # Avalia condições de alerta a cada 2 horas
    "evaluate-alerts-bihourly": {
        "task": "app.jobs.tasks.evaluate_alerts",
        "schedule": crontab(minute=0, hour="*/2"),
        "options": {
            "expires": 7200,
        },
    },
    # Sincroniza pedidos individuais a cada 2 horas
    "sync-orders-every-2h": {
        "task": "app.jobs.tasks.sync_orders",
        "schedule": crontab(minute=0, hour="*/2"),
        "options": {
            "expires": 7200,
        },
    },
    # Sincroniza campanhas de ads diariamente as 10:30 UTC (07:30 BRT)
    "sync-ads-daily": {
        "task": "app.jobs.tasks.sync_ads",
        "schedule": crontab(minute=30, hour=10),
        "options": {
            "expires": 3600,
        },
    },
    # Envia digest semanal todo domingo as 20:00 BRT (23:00 UTC)
    # day_of_week=0 = domingo no Celery (isoweekday: 0=segunda no Python, mas Celery usa 0=domingo)
    "send-weekly-digest": {
        "task": "app.jobs.tasks.send_weekly_digest",
        "schedule": crontab(hour=23, minute=0, day_of_week=0),
        "options": {
            "expires": 3600,
        },
    },
    # Envia relatorio diario de inteligencia de precos as 08:00 BRT (11:00 UTC)
    "send-daily-intel-report": {
        "task": "app.jobs.tasks.send_daily_intel_report",
        "schedule": crontab(hour=11, minute=0),
        "options": {
            "expires": 3600,
        },
    },
    # Sincroniza perguntas recebidas a cada 15 minutos
    "sync-questions-every-15min": {
        "task": "app.jobs.tasks.sync_questions",
        "schedule": crontab(minute="*/15"),
        "options": {
            "expires": 900,  # 15 minutos
        },
    },
}
