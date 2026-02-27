"""
Transform endpoint — trigger HCS fetch + FOCUS transform pipeline.
"""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_transform_service
from app.schemas.focus_schema import FocusResponse
from app.schemas.transform_schema import MetricsTransformRequest
from app.services.transform_service import TransformService

router = APIRouter(prefix="/transform", tags=["Transform"])


@router.post(
    "/",
    response_model=FocusResponse,
    summary="Fetch HCS metrics & transform to FOCUS format",
    description=(
        "Authenticates with HCS IAM, queries the SC Northbound Interface "
        "for metering data, maps it into the FOCUS specification, and "
        "returns the transformed records."
    ),
)
async def transform_data(
    req: MetricsTransformRequest,
    service: TransformService = Depends(get_transform_service),
) -> FocusResponse:
    return await service.transform(
        region_code=req.region_code,
        domain_id=req.domain_id,
        start_time=req.start_time,
        end_time=req.end_time,
        resource_type_code=req.resource_type_code,
        tenant_name=req.tenant_name,
        tenant_id=req.tenant_id,
        vdc_name=req.vdc_name,
        vdc_id=req.vdc_id,
    )
