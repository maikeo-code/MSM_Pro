from fastapi import APIRouter

from app.intel.analytics.router import router as analytics_router
from app.intel.pricing.router import router as pricing_router

intel_router = APIRouter()
intel_router.include_router(analytics_router)
intel_router.include_router(pricing_router)
