"""
VDCs endpoint — list HCS VDCs (tenants) from the SC Northbound Interface.

GET /vdcs/
"""

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_hcs_client
from app.services.source_client import HCSClient

router = APIRouter(prefix="/vdcs", tags=["VDCs"])


@router.get(
    "/",
    summary="List HCS VDCs (tenants)",
    description=(
        "Authenticates with HCS IAM, then queries the SC Northbound "
        "Interface for the VDC / tenant list.  Supports optional filters."
    ),
)
async def list_vdcs(
    limit: int = Query(default=1000, ge=1, le=1000, description="Page size"),
    level: int | None = Query(default=None, ge=1, le=5,
                              description="VDC level (1-5)"),
    is_domain: str | None = Query(
        default=None, description="'1' = tenants only, '0' = non-tenants"),
    client: HCSClient = Depends(get_hcs_client),
) -> dict:
    vdcs = await client.fetch_vdcs(
        level=level,
        is_domain=is_domain,
        limit=limit,
    )
    return {
        "status": "ok",
        "total": len(vdcs),
        "vdcs": [v.model_dump() for v in vdcs],
    }
