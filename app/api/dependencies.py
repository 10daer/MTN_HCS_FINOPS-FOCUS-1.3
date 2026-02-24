"""
Shared FastAPI dependencies — injected into route handlers.
"""

from fastapi import Depends, Request

from app.services.source_client import HCSClient
from app.services.transform_service import TransformService


def get_hcs_client(request: Request) -> HCSClient:
    """Provide an initialised HCSClient backed by the shared httpx client."""
    return HCSClient(http_client=request.app.state.http_client)


def get_transform_service(
    hcs_client: HCSClient = Depends(get_hcs_client),
) -> TransformService:
    """Provide a TransformService with its dependencies wired up."""
    return TransformService(hcs_client=hcs_client)
