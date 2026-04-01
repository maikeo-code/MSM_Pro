import hashlib
import hmac
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

# Importa Celery app para que as tasks sejam registradas
from app.core.celery_app import celery_app  # noqa: F401

# Importa todos os modelos para garantir que o SQLAlchemy resolva os relacionamentos
import app.auth.models  # noqa: F401
import app.produtos.models  # noqa: F401
import app.vendas.models  # noqa: F401
import app.concorrencia.models  # noqa: F401
import app.alertas.models  # noqa: F401
import app.reputacao.models  # noqa: F401
import app.ads.models  # noqa: F401
import app.intel.models  # noqa: F401
import app.financeiro.models  # noqa: F401
import app.atendimento.models  # noqa: F401
import app.notifications.models  # noqa: F401

# Importa tasks para que sejam registradas no Celery
import app.jobs.tasks  # noqa: F401

# Importa routers
from app.atendimento.router import router as atendimento_router
from app.ads.router import router as ads_router
from app.alertas.router import router as alertas_router
from app.analise.router import router as analise_router
from app.auth.router import router as auth_router
from app.concorrencia.router import router as concorrencia_router
from app.consultor.router import router as consultor_router
from app.financeiro.router import router as financeiro_router
from app.intel.router import intel_router
from app.notifications.router import router as notifications_router
from app.perguntas.router import router as perguntas_router
from app.produtos.router import router as produtos_router
from app.reputacao.router import router as reputacao_router
from app.vendas.router import router as vendas_router

_is_prod = settings.environment == "production"

app = FastAPI(
    title="MSM_Pro API",
    description="Dashboard de inteligência de vendas para o Mercado Livre",
    version="1.0.1",  # Versão bumped para forçar rebuild
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions — log details, return safe 500 response."""
    logger.error(
        "Unhandled error on %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# --- CORS ---
# HARDENING: Whitelist explícito de origens — sem regex wildcards (removido r"https://.*\.up\.railway\.app")
_cors_origins: list[str] = [
    settings.frontend_url,
    "http://localhost:5173",
    "http://localhost:3000",
    "https://msmprofrontend-production.up.railway.app",
]
# Permite origens extras via env var CORS_ORIGINS (comma-separated)
# Ex: CORS_ORIGINS="https://custom.com,https://another.com"
if settings.cors_origins:
    _cors_origins.extend(
        o.strip() for o in settings.cors_origins.split(",") if o.strip()
    )
logger.info(f"CORS origins allowed: {_cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # HARDENING: Removed allow_origin_regex (was r"https://.*\.up\.railway\.app")
    # Now using explicit whitelist only — see HARDENING_CORS.md
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)

# --- Routers ---
API_PREFIX = "/api/v1"

app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(produtos_router, prefix=API_PREFIX)
app.include_router(vendas_router, prefix=API_PREFIX)
app.include_router(analise_router, prefix=API_PREFIX)
app.include_router(concorrencia_router, prefix=API_PREFIX)
app.include_router(alertas_router, prefix=API_PREFIX)
app.include_router(consultor_router, prefix=API_PREFIX)
app.include_router(reputacao_router, prefix=API_PREFIX)
app.include_router(ads_router, prefix=API_PREFIX)
app.include_router(financeiro_router, prefix=API_PREFIX)
app.include_router(perguntas_router, prefix=API_PREFIX)
app.include_router(atendimento_router, prefix=API_PREFIX, tags=["Atendimento"])
app.include_router(intel_router, prefix=API_PREFIX)
app.include_router(notifications_router, prefix=API_PREFIX)


# --- Health Check ---
@app.get("/health", tags=["health"])
async def health_check():
    """Verifica se a API está no ar."""
    return {
        "status": "ok",
        "version": "1.0.0",
    }


@app.get("/", tags=["root"])
async def root():
    """Rota raiz — redireciona para docs."""
    return {
        "message": "MSM_Pro API — acesse /docs para a documentação",
        "timestamp": "2026-03-16T20:30:00Z",
        "version_check": "v2-with-acos"
    }


def _verify_ml_signature(body: bytes, x_signature: str | None) -> tuple[bool, str]:
    """Verifica a assinatura HMAC-SHA256 do webhook do Mercado Livre.

    Args:
        body: conteúdo bruto do corpo da requisição
        x_signature: valor do header X-Signature enviado pelo ML

    Returns:
        (válido: bool, razão: str)
        - (True, "ok") se a assinatura é válida
        - (False, "sem_secret") se ML_CLIENT_SECRET não está configurado (fallback dev)
        - (False, "sem_header") se X-Signature não está presente
        - (False, "assinatura_invalida") se a assinatura não corresponde
    """
    # Sem secret configurado = fallback para desenvolvimento
    if not settings.ml_client_secret:
        logger.warning(
            "Webhook: ML_CLIENT_SECRET não configurado — aceitando sem validação (dev mode)"
        )
        return True, "fallback_dev_mode"

    # Header obrigatório em produção
    if not x_signature:
        logger.warning("Webhook rejeitado: header X-Signature ausente")
        return False, "sem_header"

    # Calcular HMAC-SHA256 do body com client_secret como chave
    expected_signature = hmac.new(
        settings.ml_client_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    # Comparação time-safe (evita timing attacks)
    if hmac.compare_digest(x_signature, expected_signature):
        return True, "ok"

    logger.warning(
        "Webhook rejeitado: assinatura inválida — esperava %s",
        expected_signature[:16] + "...",
    )
    return False, "assinatura_invalida"


@app.post("/api/v1/webhooks/notifications", tags=["webhooks"])
async def ml_notifications(request: Request):
    """Recebe notificações webhook do Mercado Livre.

    Validações aplicadas:
    1. Verifica assinatura X-Signature (HMAC-SHA256) — rejeita 401 se inválida
    2. user_id e topic devem estar presentes nos query params.
    3. user_id (ml_user_id) deve existir em ml_accounts (evita processar
       notificações de contas desconhecidas).
    4. Rate limiting: ignora notificações duplicadas para o mesmo
       user_id+topic nos últimos 30s (usa Redis; fallback in-memory).
    5. Loga resource e user_id para auditoria.
    """
    from sqlalchemy import select as sa_select

    from app.auth.models import MLAccount
    from app.core.database import AsyncSessionLocal

    # ── 0. Verificar assinatura HMAC antes de qualquer outra coisa ────────────
    raw_body = await request.body()
    x_signature = request.headers.get("X-Signature")

    is_valid, reason = _verify_ml_signature(raw_body, x_signature)
    if not is_valid:
        if reason == "sem_header":
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing X-Signature header"},
            )
        else:  # assinatura_invalida
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid X-Signature"},
            )

    # ── 1. Parâmetros obrigatórios ─────────────────────────────────────────
    user_id = request.query_params.get("user_id")
    topic = request.query_params.get("topic")
    resource = request.query_params.get("resource", "")

    if not user_id or not topic:
        logger.warning(
            "Webhook rejeitado: parametros ausentes user_id=%s topic=%s",
            user_id, topic,
        )
        return JSONResponse(status_code=400, content={"detail": "Missing user_id or topic"})

    logger.info(
        "ML webhook recebido: user_id=%s topic=%s resource=%s",
        user_id, topic, resource,
    )

    # ── 2. Validar que o ml_user_id existe no banco ────────────────────────
    async with AsyncSessionLocal() as db:
        acc_result = await db.execute(
            sa_select(MLAccount.id).where(
                MLAccount.ml_user_id == user_id,
                MLAccount.is_active == True,  # noqa: E712
            ).limit(1)
        )
        if acc_result.scalar_one_or_none() is None:
            logger.warning(
                "Webhook rejeitado: ml_user_id=%s nao encontrado em ml_accounts",
                user_id,
            )
            # Retorna 200 para o ML não retentar em loop — mas não processa.
            return JSONResponse(
                status_code=200,
                content={"status": "ignored", "reason": "unknown_user"},
            )

    # ── 3. Rate limiting (30s por user_id+topic) ──────────────────────────
    rate_key = f"wh_rl:{user_id}:{topic}"
    _rate_limited = False

    try:
        import redis as _redis_lib
        _r = _redis_lib.from_url(settings.redis_url, decode_responses=True)
        # SET key 1 NX EX 30 → retorna None se já existe (já foi processado)
        result = _r.set(rate_key, "1", nx=True, ex=30)
        if result is None:
            _rate_limited = True
        _r.close()
    except Exception as _redis_err:
        # Fallback: in-memory dict com TTL manual
        import time as _time
        _now = _time.monotonic()
        # Limpa entradas expiradas (>30s)
        _expired = [k for k, ts in _webhook_rate_cache.items() if _now - ts > 30]
        for k in _expired:
            _webhook_rate_cache.pop(k, None)
        if rate_key in _webhook_rate_cache:
            _rate_limited = True
        else:
            _webhook_rate_cache[rate_key] = _now
        logger.debug("Webhook rate-limit via in-memory (Redis indisponivel: %s)", _redis_err)

    if _rate_limited:
        logger.info(
            "Webhook ignorado (rate-limit 30s): user_id=%s topic=%s",
            user_id, topic,
        )
        return JSONResponse(
            status_code=200,
            content={"status": "ignored", "reason": "rate_limited"},
        )

    # ── 4. Processar por tópico ───────────────────────────────────────────
    if topic in ("orders_v2", "orders"):
        from app.jobs.tasks import sync_orders
        sync_orders.delay()
        logger.info(
            "Webhook: sync_orders enfileirado — user_id=%s resource=%s",
            user_id, resource,
        )
    elif topic == "questions":
        logger.info(
            "Webhook: nova pergunta registrada — user_id=%s resource=%s",
            user_id, resource,
        )
    elif topic == "items":
        from app.jobs.tasks import sync_recent_snapshots
        sync_recent_snapshots.delay()
        logger.info(
            "Webhook: sync_recent_snapshots enfileirado — user_id=%s resource=%s",
            user_id, resource,
        )
    else:
        logger.info(
            "Webhook: topico nao tratado topic=%s user_id=%s resource=%s",
            topic, user_id, resource,
        )

    return {"status": "processed", "topic": topic}


# Cache in-memory para rate-limiting de webhook (fallback sem Redis)
_webhook_rate_cache: dict[str, float] = {}
