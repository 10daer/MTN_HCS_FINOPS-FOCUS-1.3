from pydantic import BaseModel, Field


class MetricsQueryRequest(BaseModel):
    """Request body for the metrics query endpoint (SC API pass-through)."""

    region_code: str = Field(
        ..., description="HCS region ID, required (e.g. 'lagos-mtn-1')")
    domain_id: str = Field(
        ..., description="Tenant / VDC domain ID, required")
    start_time: str = Field(
        ..., description="Period start, required (YYYY-MM-DD HH:MM:SS)")
    end_time: str = Field(
        ..., description="Period end, required (YYYY-MM-DD HH:MM:SS)")
    period: str = Field(
        default="daily",
        description="Query period: hourly | daily | monthly")
    time_zone: str = Field(
        default="Africa/Lagos", description="Timezone (e.g. Africa/Lagos)")
    locale: str = Field(
        default="en_US", description="en_US | zh_CN")
    resource_type_code: str | None = Field(
        default=None,
        description="HCS resource type code (e.g. 'hws.resource.type.volume'). "
                    "Omit to query all resource types.",
    )
    limit: int | None = Field(
        default=None, ge=1, le=1000,
        description="Page size (1-1000). Omit to use SC API default of 20.",
    )


class MetricsTransformRequest(MetricsQueryRequest):
    """Request body for the transform endpoint (metrics + FOCUS mapping)."""

    # Optional context for FOCUS account fields
    tenant_name: str = Field(
        default="", description="HCS Tenant Name → FOCUS BillingAccountName")
    tenant_id: str = Field(
        default="", description="HCS Tenant ID → FOCUS BillingAccountId")
    vdc_name: str = Field(
        default="", description="VDC Name → FOCUS SubAccountName")
    vdc_id: str = Field(
        default="", description="VDC ID → FOCUS SubAccountId")


class VDCQueryParams(BaseModel):
    """Query parameters for the VDC list endpoint."""

    limit: int = Field(
        default=1000, ge=1, le=1000, description="Page size (1-1000)")
    level: int | None = Field(
        default=None, ge=1, le=5,
        description="VDC level (1-5). Omit for all levels.")
    is_domain: str | None = Field(
        default=None,
        description="Filter by tenant: '1' = tenants only, '0' = non-tenants only.")
    name: str | None = Field(
        default=None, description="VDC name filter")
    domain_id: str | None = Field(
        default=None, description="Tenant domain ID filter")
