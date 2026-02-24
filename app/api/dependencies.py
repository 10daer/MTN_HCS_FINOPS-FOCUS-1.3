"""
Shared FastAPI dependencies — injected into route handlers.
"""

from fastapi import Depends

from app.services.source_client import HCSClient
from app.services.transform_service import TransformService


def get_hcs_client() -> HCSClient:
    """Provide a fresh HCSClient (uses curl subprocess internally)."""
    return HCSClient()


def get_transform_service(
    hcs_client: HCSClient = Depends(get_hcs_client),
) -> TransformService:
    """Provide a TransformService with its dependencies wired up."""
    return TransformService(hcs_client=hcs_client)
