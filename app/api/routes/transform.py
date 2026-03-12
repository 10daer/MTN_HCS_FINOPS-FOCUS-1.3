"""
Transform endpoint — trigger HCS fetch + FOCUS transform pipeline.

POST /transform/

Streams results as NDJSON (one JSON object per line) so the server never
holds the entire dataset in memory.
"""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_hcs_client
from app.mappers.focus_mapper import FocusMapper
from app.schemas.transform_schema import MetricsQueryRequest
from app.services.source_client import HCSClient

router = APIRouter(prefix="/transform", tags=["Transform"])


async def _stream_focus_records(
    client: HCSClient, req: MetricsQueryRequest
) -> AsyncIterator[str]:
    """Fetch HCS pages, map each to FOCUS, and yield one NDJSON line per record."""
    mapper = FocusMapper()
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
        focus_records = mapper.map_many(page)
        for record in focus_records:
            yield json.dumps(record.model_dump(), default=str) + "\n"


@router.post(
    "/",
    summary="Fetch HCS metrics & transform to FOCUS format",
    description=(
        "Authenticates with HCS IAM, queries the SC Northbound Interface "
        "for metering data, maps it into the FOCUS specification, and "
        "streams the transformed records as NDJSON (one JSON object per line)."
    ),
)
async def transform_data(
    req: MetricsQueryRequest,
    client: HCSClient = Depends(get_hcs_client),
) -> StreamingResponse:
    return StreamingResponse(
        _stream_focus_records(client, req),
        media_type="application/x-ndjson",
    )