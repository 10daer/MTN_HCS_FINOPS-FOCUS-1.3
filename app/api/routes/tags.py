"""
Tags endpoints — HCS Tag Management APIs.

Covers:
  14.2  POST /tags/resources/action   — Query resources associated with a tag
  14.3  GET  /tags/predefined         — Query predefined tags (new)
  14.5  GET  /tags/                   — Query tag list
  14.6  POST /tags/                   — Create or delete tags in batches
  14.7  POST /tags/authen             — Verify tag permissions on resources
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.api.dependencies import get_hcs_client
from app.schemas.tag_schema import (
    QueryResourceTagsRequest,
    QueryResourceTagsResponse,
    PreDefineTagsResponse,
    ListTagsResponse,
    BatchTagRequest,
    VerifyTagPermissionsRequest,
)
from app.services.source_client import HCSClient

router = APIRouter(prefix="/tags", tags=["Tags"])


# ── 14.2  Query resources associated with a tag ───────────────────────


@router.post(
    "/resources/action",
    summary="Query resources associated with a tag",
    description=(
        "Query the list of resources bound to a tag. Supports filter, "
        "count, and accurate_query actions."
    ),
    response_model=QueryResourceTagsResponse,
)
async def query_resource_tags(
    req: QueryResourceTagsRequest,
    client: HCSClient = Depends(get_hcs_client),
) -> QueryResourceTagsResponse:
    return await client.query_resource_tags(req.model_dump(exclude_none=True))


# ── 14.3  Query predefined tags (new) ─────────────────────────────────


@router.get(
    "/predefined",
    summary="Query predefined tags (new)",
    description=(
        "Query predefined tags with optional fuzzy search by key/value, "
        "pagination, and sorting."
    ),
    response_model=PreDefineTagsResponse,
)
async def list_predefined_tags(
    key: str | None = Query(default=None, description="Tag key (fuzzy, case-insensitive)"),
    value: str | None = Query(default=None, description="Tag value (fuzzy, case-insensitive)"),
    limit: int | None = Query(default=None, ge=0, le=1000, description="Page size (0-1000)"),
    marker: str | None = Query(default=None, description="Paging location marker"),
    order_field: str | None = Query(
        default=None, description="Sort field: update_time | key | value"
    ),
    order_method: str | None = Query(
        default=None, description="Sort direction: asc | desc"
    ),
    client: HCSClient = Depends(get_hcs_client),
) -> PreDefineTagsResponse:
    return await client.fetch_predefined_tags(
        key=key,
        value=value,
        limit=limit,
        marker=marker,
        order_field=order_field,
        order_method=order_method,
    )


# ── 14.5  Query list of tags ──────────────────────────────────────────


@router.get(
    "/",
    summary="Query tag list",
    description=(
        "Query the tag list with optional filtering by key/value, "
        "pagination, and sorting."
    ),
    response_model=ListTagsResponse,
)
async def list_tags(
    key: str | None = Query(default=None, description="Tag key filter"),
    value: str | None = Query(default=None, description="Tag value filter"),
    start: str | None = Query(default=None, description="Pagination start position"),
    limit: str | None = Query(default=None, description="Max items per page"),
    order_field: str | None = Query(
        default=None, description="Sort field: key | value | update_time"
    ),
    order_method: str | None = Query(
        default=None, description="Sort direction: asc | desc"
    ),
    client: HCSClient = Depends(get_hcs_client),
) -> ListTagsResponse:
    return await client.fetch_tags(
        key=key,
        value=value,
        start=start,
        limit=limit,
        order_field=order_field,
        order_method=order_method,
    )


# ── 14.6  Create or delete tags in batches ─────────────────────────────


@router.post(
    "/",
    summary="Create or delete tags in batches",
    description="Create or delete tags in batches. Action can be 'create' or 'delete'.",
    status_code=204,
)
async def batch_create_delete_tags(
    req: BatchTagRequest,
    client: HCSClient = Depends(get_hcs_client),
) -> Response:
    await client.batch_create_delete_tags(
        action=req.action,
        tags=[t.model_dump(exclude_none=True) for t in req.tags],
    )
    return Response(status_code=204)


# ── 14.7  Verify tag permissions ───────────────────────────────────────


@router.post(
    "/authen",
    summary="Verify tag permissions on resources",
    description=(
        "Verify the permissions on resources before they are associated "
        "to or disassociated from tags."
    ),
    status_code=200,
)
async def verify_tag_permissions(
    req: VerifyTagPermissionsRequest,
    client: HCSClient = Depends(get_hcs_client),
) -> dict:
    await client.verify_tag_permissions(req.model_dump(exclude_none=True))
    return {"status": "ok"}
