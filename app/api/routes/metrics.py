"""
Metrics endpoint — query raw HCS metering data from the SC Northbound Interface.

POST /metrics/
"""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_hcs_client
from app.schemas.transform_schema import MetricsQueryRequest
from app.services.source_client import HCSClient

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.post(
    "/",
    summary="Query HCS metering / CDR data",
    description=(
        "Authenticates with HCS IAM, then queries the SC Northbound "
        "Interface for cloud service call detail records (CDRs).  "
        "Returns the raw HCS metrics response."
    ),
)
async def query_metrics(
    req: MetricsQueryRequest,
    client: HCSClient = Depends(get_hcs_client),
) -> dict:
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
    return {
        "status": "ok",
        "total": len(records),
        "metrics": [r.model_dump() for r in records],
    }
