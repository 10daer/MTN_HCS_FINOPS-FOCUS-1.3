"""
Pydantic schemas for the HCS ManageOne Tag Management APIs.
"""

from typing import Optional

from pydantic import BaseModel, Field


# ── Shared tag sub-objects ─────────────────────────────────────────────


class TagKeyValue(BaseModel):
    """A simple key/value tag pair used across multiple endpoints."""

    key: str = Field(..., max_length=36, description="Tag key (max 36 chars)")
    value: str = Field(..., max_length=43, description="Tag value (max 43 chars)")


class TagReq(BaseModel):
    """Tag filter object for resource queries (14.2)."""

    id: Optional[str] = Field(default=None, description="Tag ID (max 36 bytes)")
    key: Optional[str] = Field(default=None, max_length=36, description="Tag key")
    value: Optional[str] = Field(default=None, max_length=43, description="Tag value")


class TagRep(BaseModel):
    """Tag in a resource query response."""

    key: Optional[str] = Field(default=None, description="Tag key")
    value: Optional[str] = Field(default=None, description="Tag value")
    operate_time: Optional[str] = Field(
        default=None, description="Operation time (yyyy-MM-dd HH:mm:ss)"
    )


# ── 14.2  Query resources associated with a tag ───────────────────────


class QueryResourceTagsRequest(BaseModel):
    """Request body for POST /rest/tag/v3.0/tags/resources/action."""

    tags: Optional[list[TagReq]] = Field(
        default=None, description="Tags filter (AND). Cannot combine with tags_any."
    )
    tags_any: Optional[list[TagReq]] = Field(
        default=None, description="Tags filter (OR). Cannot combine with tags."
    )
    project_id: str = Field(..., max_length=36, description="Project ID (required)")
    region_id: Optional[str] = Field(default=None, max_length=36, description="Region ID")
    cloud_infra_id: Optional[str] = Field(
        default=None, max_length=36, description="Resource pool ID"
    )
    resource_id: Optional[str] = Field(default=None, max_length=36, description="Resource ID")
    resource_name: Optional[str] = Field(
        default=None, max_length=256, description="Resource name"
    )
    resource_type: Optional[str] = Field(
        default=None, max_length=32, description="Resource type / service ID"
    )
    start: Optional[str] = Field(default=None, description="Pagination start position")
    limit: Optional[str] = Field(default=None, description="Max items per page")
    action: str = Field(
        ..., description="Operation type: filter | count | accurate_query"
    )


class ResourceItem(BaseModel):
    """A resource returned in the query response."""

    region_id: Optional[str] = Field(default=None)
    project_id: Optional[str] = Field(default=None)
    cloud_infra_id: Optional[str] = Field(default=None)
    resource_id: Optional[str] = Field(default=None)
    resource_name: Optional[str] = Field(default=None)
    resource_type: Optional[str] = Field(default=None)
    tags: Optional[list[TagRep]] = Field(default=None)


class QueryResourceTagsResponse(BaseModel):
    """Response for POST /rest/tag/v3.0/tags/resources/action."""

    total: Optional[int] = Field(default=None)
    resources: Optional[list[ResourceItem]] = Field(default=None)


# ── 14.3  Query predefined tags (new) ─────────────────────────────────


class PreDefineTag(BaseModel):
    """A predefined tag entry."""

    key: Optional[str] = Field(default=None, max_length=36, description="Tag key")
    value: Optional[str] = Field(default=None, max_length=43, description="Tag value")
    update_time: Optional[str] = Field(default=None, description="UTC update time")


class PreDefineTagsResponse(BaseModel):
    """Response for GET /v1.0/predefine_tags."""

    marker: Optional[str] = Field(default=None, description="Paging location marker")
    total_count: Optional[int] = Field(default=None, description="Total number of tags")
    tags: Optional[list[PreDefineTag]] = Field(default=None)


# ── 14.5  Query list of tags ──────────────────────────────────────────


class TagRsp(BaseModel):
    """A tag returned from GET /rest/tag/v3.0/tags."""

    id: Optional[str] = Field(default=None, description="Tag ID")
    key: Optional[str] = Field(default=None, description="Tag key")
    value: Optional[str] = Field(default=None, description="Tag value")
    vdc_id: Optional[str] = Field(default=None, description="VDC ID")
    domain_id: Optional[str] = Field(default=None, description="Domain ID")
    update_time: Optional[str] = Field(default=None, description="Update time")
    sourceTotal: Optional[str] = Field(
        default=None, description="Total associated resources"
    )


class ListTagsResponse(BaseModel):
    """Response for GET /rest/tag/v3.0/tags."""

    total: Optional[str] = Field(default=None, description="Total number of tags")
    tags: Optional[list[TagRsp]] = Field(default=None)


# ── 14.6  Create or delete tags in batches ─────────────────────────────


class Tag(BaseModel):
    """Tag for batch create/delete."""

    id: Optional[str] = Field(default=None, description="Tag ID (reserved)")
    key: str = Field(..., max_length=36, description="Tag key")
    value: Optional[str] = Field(default=None, max_length=43, description="Tag value")


class BatchTagRequest(BaseModel):
    """Request body for POST /rest/tag/v3.0/tags (create/delete)."""

    action: str = Field(..., description="Action: create | delete")
    tags: list[Tag] = Field(..., max_length=100, description="Tags (max 100)")


# ── 14.7  Verify permissions on resources ──────────────────────────────


class AuthenTag(BaseModel):
    """Tag for permission verification."""

    key: str = Field(..., max_length=36, description="Tag key")
    value: str = Field(..., max_length=43, description="Tag value")


class VerifyTagPermissionsRequest(BaseModel):
    """Request body for POST /rest/tag/v3.0/tags/authen."""

    user_id: str = Field(..., max_length=36, description="User ID on ManageOne")
    resource_id: Optional[str] = Field(
        default=None, max_length=36, description="Resource ID"
    )
    cloud_infra_id: Optional[str] = Field(
        default=None, max_length=36, description="Resource pool ID"
    )
    region_id: Optional[str] = Field(default=None, max_length=36, description="Region ID")
    project_id: Optional[str] = Field(default=None, max_length=36, description="Project ID")
    bind_tags: Optional[list[AuthenTag]] = Field(
        default=None, description="Tags to associate (max 100)"
    )
    unbind_tags: Optional[list[AuthenTag]] = Field(
        default=None, description="Tags to disassociate (max 100)"
    )
