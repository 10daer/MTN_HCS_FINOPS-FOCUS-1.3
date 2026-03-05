"""
Regions endpoint — list HCS regions from the SC Northbound Interface.

GET /regions/
"""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_hcs_client
from app.services.source_client import HCSClient

router = APIRouter(prefix="/regions", tags=["Regions"])


@router.get(
    "/",
    summary="List HCS regions",
    description=(
        "Authenticates with HCS IAM, then queries the SC Northbound "
        "Interface for the list of available regions."
    ),
)
async def list_regions(
    client: HCSClient = Depends(get_hcs_client),
) -> dict:
    regions = await client.fetch_regions()
    return {
        "status": "ok",
        "total": len(regions),
        "regions": [r.model_dump(by_alias=True) for r in regions],
    }
