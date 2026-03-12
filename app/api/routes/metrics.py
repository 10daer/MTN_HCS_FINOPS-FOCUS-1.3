"""
Metrics endpoint — query raw HCS metering data from the SC Northbound Interface.

POST /metrics/

Streams results as NDJSON (one JSON object per line) so the server never
holds the entire dataset in memory and clients can start processing
records immediately.
"""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_hcs_client
from app.schemas.transform_schema import MetricsQueryRequest
from app.services.source_client import HCSClient

router = APIRouter(prefix="/metrics", tags=["Metrics"])


async def _stream_metrics(
    client: HCSClient, req: MetricsQueryRequest
) -> AsyncIterator[str]:
    """Yield one NDJSON line per metric record, page by page."""
    async for page in client.fetch_metrics_pages(
        region_code=req.region_code,
        domain_id=req.domain_id,
        start_time=req.start_time,
        end_time=req.end_time,
        resource_type_code=req.resource_type_code,
        period=req.period,
        time_zone=req.time_zone,
        locale=req.locale,
        limit=req.limit,
    ):
        for record in page:
            yield json.dumps(record.model_dump()) + "\n"


@router.post(
    "/",
    summary="Query HCS metering / CDR data",
    description=(
        "Authenticates with HCS IAM, then queries the SC Northbound "
        "Interface for cloud service call detail records (CDRs).  "
        "Streams the raw HCS metrics response as NDJSON (one JSON "
        "object per line)."
    ),
)
async def query_metrics(
    req: MetricsQueryRequest,
    client: HCSClient = Depends(get_hcs_client),
) -> StreamingResponse:
    return StreamingResponse(
        _stream_metrics(client, req),
        media_type="application/x-ndjson",
    )
