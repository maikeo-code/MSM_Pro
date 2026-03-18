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

# Importa tasks para que sejam registradas no Celery
import app.jobs.tasks  # noqa: F401

# Importa routers
from app.ads.router import router as ads_router
from app.alertas.router import router as alertas_router
from app.analise.router import router as analise_router
from app.auth.router import router as auth_router
from app.concorrencia.router import router as concorrencia_router
from app.consultor.router import router as consultor_router
from app.financeiro.router import router as financeiro_router
from app.perguntas.router import router as perguntas_router
from app.produtos.router import router as produtos_router
from app.reputacao.router import router as reputacao_router
from app.vendas.router import router as vendas_router

_is_prod = settings.environment == "production"

app = FastAPI(
    title="MSM_Pro API",
    description="Dashboard de inteligência de vendas para o Mercado Livre",
    version="1.0.0",
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
# Monta lista de origens permitidas — sem wildcards em methods/headers
_cors_origins: list[str] = [
    settings.frontend_url,
    "http://localhost:5173",
    "http://localhost:3000",
    "https://msmprofrontend-production.up.railway.app",
]
# Permite origens extras via env var CORS_ORIGINS (comma-separated)
if settings.cors_origins:
    _cors_origins.extend(
        o.strip() for o in settings.cors_origins.split(",") if o.strip()
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https://.*\.up\.railway\.app",
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


@app.post("/api/v1/notifications", tags=["webhooks"])
async def ml_notifications(request: Request):
    """Recebe notificações webhook do Mercado Livre.

    Validates the request has a valid source. Full x-signature HMAC validation
    requires the notification resource fetch pattern from ML docs.
    """
    # Basic validation: ML sends user_id and topic in query params
    user_id = request.query_params.get("user_id")
    topic = request.query_params.get("topic")
    resource = request.query_params.get("resource")

    if not user_id or not topic:
        logger.warning("Webhook rejected: missing user_id or topic")
        return JSONResponse(status_code=400, content={"detail": "Missing user_id or topic"})

    body = await request.json() if await request.body() else {}

    logger.info(
        "ML webhook received: user_id=%s topic=%s resource=%s",
        user_id, topic, resource,
    )

    # TODO: process notifications (orders, questions, stock changes)
    # For now, acknowledge receipt so ML doesn't retry
    return {"status": "received", "topic": topic}
