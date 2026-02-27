"""
Route aggregation for API v1.
"""

from fastapi import APIRouter

from app.api.routes.metrics import router as metrics_router
from app.api.routes.regions import router as regions_router
from app.api.routes.transform import router as transform_router
from app.api.routes.vdcs import router as vdcs_router

router = APIRouter()
router.include_router(regions_router)
router.include_router(vdcs_router)
router.include_router(metrics_router)
