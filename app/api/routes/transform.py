"""
Transform endpoint — trigger HCS fetch + FOCUS transform pipeline.

POST /transform/
"""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_hcs_client
from app.mappers.focus_mapper import FocusMapper
from app.schemas.focus_schema import FocusRecord, FocusResponse
from app.schemas.transform_schema import MetricsQueryRequest
from app.services.source_client import HCSClient

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
    req: MetricsQueryRequest,
    client: HCSClient = Depends(get_hcs_client),
) -> FocusResponse:
    records = await client.fetch_metrics(
        region_code=req.region_code,
        domain_id=req.domain_id,
        start_time=req.start_time,
        end_time=req.end_time,
        resource_type_code=req.resource_type_code,
        period=req.period,
        time_zone=req.time_zone,
        locale=req.locale,
        limit=req.limit,
    )

    mapper = FocusMapper()
    focus_records: list[FocusRecord] = mapper.map_many(records)

    return FocusResponse(
        status="ok",
        total_count=len(focus_records),
        records=focus_records,
        metadata={
            "region_code": req.region_code,
            "domain_id": req.domain_id,
            "resource_type_code": req.resource_type_code or "all",
            "period": req.period,
            "start_time": req.start_time,
            "end_time": req.end_time,
        },
    )