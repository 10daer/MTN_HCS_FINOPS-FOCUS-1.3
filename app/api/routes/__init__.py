"""
Route aggregation for API v1.
"""

from fastapi import APIRouter

from app.api.routes.transform import router as transform_router

router = APIRouter()
router.include_router(transform_router)
