from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

# Importa Celery app para que as tasks sejam registradas
from app.core.celery_app import celery_app  # noqa: F401

# Importa todos os modelos para garantir que o SQLAlchemy resolva os relacionamentos
import app.auth.models  # noqa: F401
import app.produtos.models  # noqa: F401
import app.vendas.models  # noqa: F401
import app.concorrencia.models  # noqa: F401
import app.alertas.models  # noqa: F401

# Importa tasks para que sejam registradas no Celery
import app.jobs.tasks  # noqa: F401

# Importa routers
from app.alertas.router import router as alertas_router
from app.auth.router import router as auth_router
from app.concorrencia.router import router as concorrencia_router
from app.produtos.router import router as produtos_router
from app.vendas.router import router as vendas_router

app = FastAPI(
    title="MSM_Pro API",
    description="Dashboard de inteligência de vendas para o Mercado Livre",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- CORS ---
# Monta lista de origens permitidas (separa por vírgula no env se necessário)
_cors_origins: list[str] = [
    settings.frontend_url,
    "http://localhost:5173",
    "http://localhost:3000",
    "https://msmprofrontend-production.up.railway.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https://.*\.up\.railway\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
API_PREFIX = "/api/v1"

app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(produtos_router, prefix=API_PREFIX)
app.include_router(vendas_router, prefix=API_PREFIX)
app.include_router(concorrencia_router, prefix=API_PREFIX)
app.include_router(alertas_router, prefix=API_PREFIX)


# --- Health Check ---
@app.get("/health", tags=["health"])
async def health_check():
    """Verifica se a API está no ar."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "environment": settings.environment,
    }


@app.get("/", tags=["root"])
async def root():
    """Rota raiz — redireciona para docs."""
    return {"message": "MSM_Pro API — acesse /docs para a documentação"}


@app.post("/api/v1/notifications", tags=["webhooks"])
async def ml_notifications(payload: dict):
    """Recebe notificações webhook do Mercado Livre."""
    # TODO: processar notificações (pedidos, perguntas, stock changes)
    return {"status": "received"}
